"""Static dependency-contract checks for the GPU application image."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest


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


def _valid_compose_config() -> dict[str, object]:
    return {
        "services": {
            "app": {
                "deploy": {
                    "resources": {
                        "reservations": {
                            "devices": [
                                {
                                    "driver": "nvidia",
                                    "count": 1,
                                    "capabilities": ["gpu"],
                                }
                            ]
                        }
                    }
                }
            }
        }
    }


def _assert_brev_gpu_reservation(config: dict[str, object]) -> None:
    services = config.get("services")
    assert isinstance(services, dict), "services must be a mapping"

    app = services.get("app")
    assert isinstance(app, dict), "services.app must be a mapping"
    assert "gpus" not in app, "services.app.gpus is not accepted by Brev"

    deploy = app.get("deploy")
    assert isinstance(deploy, dict), "services.app.deploy must be a mapping"
    resources = deploy.get("resources")
    assert isinstance(resources, dict), (
        "services.app.deploy.resources must be a mapping"
    )
    reservations = resources.get("reservations")
    assert isinstance(reservations, dict), (
        "services.app.deploy.resources.reservations must be a mapping"
    )
    devices = reservations.get("devices")
    assert isinstance(devices, list), (
        "services.app.deploy.resources.reservations.devices must be a list"
    )
    assert len(devices) == 1, "services.app must reserve exactly one GPU device"

    device = devices[0]
    assert isinstance(device, dict), "the GPU device reservation must be a mapping"
    assert device.get("driver") == "nvidia", (
        "the GPU device reservation driver must be nvidia"
    )
    count = device.get("count")
    assert type(count) is int and count == 1, (  # bool is not a valid count
        "the GPU device reservation count must be the integer 1"
    )
    assert device.get("capabilities") == ["gpu"], (
        "the GPU device reservation capabilities must be exactly ['gpu']"
    )


def test_compose_uses_one_brev_compatible_nvidia_gpu_reservation() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "deployment/compose.yaml",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    _assert_brev_gpu_reservation(json.loads(result.stdout))


def test_gpu_validator_rejects_original_service_level_gpus() -> None:
    config = {"services": {"app": {"gpus": "all"}}}

    with pytest.raises(AssertionError, match="services.app.gpus"):
        _assert_brev_gpu_reservation(config)


def test_gpu_validator_rejects_missing_reservation() -> None:
    config = {"services": {"app": {}}}

    with pytest.raises(AssertionError, match="services.app.deploy"):
        _assert_brev_gpu_reservation(config)


def test_gpu_validator_rejects_wrong_gpu_count() -> None:
    config = _valid_compose_config()
    config["services"]["app"]["deploy"]["resources"]["reservations"][
        "devices"
    ][0]["count"] = 2

    with pytest.raises(AssertionError, match="count must be the integer 1"):
        _assert_brev_gpu_reservation(config)


def test_gpu_validator_rejects_missing_gpu_capability() -> None:
    config = _valid_compose_config()
    config["services"]["app"]["deploy"]["resources"]["reservations"][
        "devices"
    ][0]["capabilities"] = ["compute"]

    with pytest.raises(AssertionError, match="capabilities must be exactly"):
        _assert_brev_gpu_reservation(config)


def test_gpu_validator_ignores_decoy_reservation_outside_app() -> None:
    config = _valid_compose_config()
    app = config["services"]["app"]
    config["services"] = {"app": {}, "worker": copy.deepcopy(app)}

    with pytest.raises(AssertionError, match="services.app.deploy"):
        _assert_brev_gpu_reservation(config)
