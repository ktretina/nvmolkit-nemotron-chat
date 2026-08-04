"""Static dependency-contract checks for the GPU application image."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _exact_pin(dependencies: list[str], package: str) -> str:
    match = next(
        (item for item in dependencies if item.partition("==")[0].lower() == package),
        None,
    )
    assert match is not None, f"{package} must have an exact project dependency pin"
    name, separator, version = match.partition("==")
    assert name.lower() == package and separator and version
    return version


def test_nvmolkit_and_rdkit_distribution_pins_are_compatible() -> None:
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]
    rdkit_version = _exact_pin(dependencies, "rdkit")

    dockerfile = (ROOT / "deployment" / "Dockerfile").read_text()
    nvmolkit_match = re.search(r"\bnvmolkit==([^\s\\]+)", dockerfile)
    assert nvmolkit_match is not None, "Dockerfile must exactly pin nvmolkit"

    compatible_rdkit = {"0.5.0": "2026.3.1"}
    assert rdkit_version == compatible_rdkit[nvmolkit_match.group(1)]
    assert "--no-deps" not in dockerfile

    flattened = dockerfile.replace("\\\n", " ")
    nvmolkit_install = next(
        command
        for command in re.findall(
            r"python -m pip install\b.*?(?=\s+&&|$)", flattened
        )
        if "nvmolkit==" in command
    )
    assert "torch==2.7.1+cu128" in nvmolkit_install
    assert "/tmp/backend" in nvmolkit_install


def test_deployment_docs_preserve_repository_context_and_architecture_limits() -> None:
    launchable = (ROOT / "deployment" / "launchable-fields.md").read_text()
    launchable_lower = launchable.lower()
    assert "- **compose url" not in launchable_lower
    assert "raw compose yaml url alone is not accepted" in launchable_lower
    assert "full accepted repository checkout" in launchable_lower
    assert "blocking acceptance gate" in launchable_lower

    readme = (ROOT / "README.md").read_text()
    assert "Linux x86-64 target-GPU hosts only" in readme
    assert "ARM64 Macs are unsupported" in readme
    assert "emulation has not been tested" in readme
