"""Static dependency-contract checks for the GPU application image."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_IMAGE_WORKFLOW = ROOT / ".github" / "workflows" / "publish-image.yml"
APP_IMAGE_BUILD_COMMIT = "0ac0fb00bc1fc49bc23982f1c2a0a2e51db53980"
APP_IMAGE = (
    "ghcr.io/ktretina/nvmolkit-nemotron-chat@"
    "sha256:0931542cde79aa9d64438c7b720aa80adacb8ab328ab585af5b3b717937f5afb"
)
APPROVED_PUBLISH_ACTION_SHAS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "docker/login-action": "dbcb813823bdd20940b903addbd779551569679f",
    "docker/setup-buildx-action": "bb05f3f5519dd87d3ba754cc423b652a5edd6d2c",
    "docker/build-push-action": "53b7df96c91f9c12dcc8a07bcb9ccacbed38856a",
}


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


def test_safe_yaml_parser_is_pinned_as_a_test_dependency() -> None:
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    test_dependencies = project["project"]["optional-dependencies"]["test"]

    assert _exact_pin(test_dependencies, "pyyaml") == "6.0.3"


def _load_publish_image_workflow(source: str) -> dict[str, Any]:
    workflow = yaml.safe_load(source)
    assert isinstance(workflow, dict), "the image workflow must be a mapping"
    return workflow


def _assert_publish_image_workflow(source: str) -> None:
    workflow = _load_publish_image_workflow(source)
    triggers = workflow.get("on")

    assert set(workflow) == {"name", "on", "permissions", "jobs"}, (
        "workflow must use the literal string trigger key 'on'"
    )
    assert workflow["name"] == "Publish container image"
    assert triggers == {"workflow_dispatch": None}
    assert workflow.get("permissions") == {
        "contents": "read",
        "packages": "write",
    }
    assert set(workflow.get("jobs", {})) == {"publish"}
    publish = workflow["jobs"]["publish"]
    steps = publish["steps"]

    assert set(publish) == {"runs-on", "outputs", "steps"}
    assert publish.get("runs-on") == "ubuntu-latest"
    assert publish.get("outputs") == {
        "digest": "${{ steps.build.outputs.digest }}"
    }

    secret_matches = re.findall(
        r"secrets(?:\.([A-Za-z_][A-Za-z0-9_]*)|"
        r"\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\])",
        source,
    )
    secret_references = {dot or bracket for dot, bracket in secret_matches}
    assert secret_references == {"GITHUB_TOKEN"}, (
        "only GITHUB_TOKEN may be referenced"
    )

    action_uses = {
        action: f"{action}@{sha}"
        for action, sha in APPROVED_PUBLISH_ACTION_SHAS.items()
    }
    assert all(
        re.fullmatch(r"[0-9a-f]{40}", sha)
        for sha in APPROVED_PUBLISH_ACTION_SHAS.values()
    )
    expected_steps = [
        {
            "name": "Check out repository",
            "uses": action_uses["actions/checkout"],
            "with": {"persist-credentials": False},
        },
        {
            "name": "Log in to GHCR",
            "uses": action_uses["docker/login-action"],
            "with": {
                "registry": "ghcr.io",
                "username": "${{ github.actor }}",
                "password": "${{ secrets.GITHUB_TOKEN }}",
            },
        },
        {
            "name": "Set up Docker Buildx",
            "uses": action_uses["docker/setup-buildx-action"],
        },
        {
            "name": "Build and push image",
            "id": "build",
            "uses": action_uses["docker/build-push-action"],
            "with": {
                "context": ".",
                "file": "./deployment/Dockerfile",
                "platforms": "linux/amd64",
                "push": True,
                "tags": "ghcr.io/ktretina/nvmolkit-nemotron-chat:${{ github.sha }}",
            },
        },
        {
            "name": "Report immutable image reference",
            "env": {
                "IMAGE": "ghcr.io/ktretina/nvmolkit-nemotron-chat",
                "DIGEST": "${{ steps.build.outputs.digest }}",
            },
            "run": 'echo "Image: ${IMAGE}@${DIGEST}" >> "$GITHUB_STEP_SUMMARY"',
        },
    ]
    assert steps == expected_steps, (
        "steps must match the ordered workflow step contract"
    )

    assert ":latest" not in source
    assert "NVIDIA_API_KEY" not in source
    assert "brev" not in source.lower()


def _replace_workflow_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, f"expected one workflow fragment: {old!r}"
    return source.replace(old, new, 1)


def test_publish_image_workflow_matches_secure_publication_contract() -> None:
    _assert_publish_image_workflow(PUBLISH_IMAGE_WORKFLOW.read_text())


@pytest.mark.parametrize("trigger_key", ["1", "true"])
def test_publish_image_validator_rejects_non_string_trigger_key(
    trigger_key: str,
) -> None:
    source = _replace_workflow_once(
        PUBLISH_IMAGE_WORKFLOW.read_text(),
        '"on":\n',
        f"{trigger_key}:\n",
    )

    with pytest.raises(AssertionError, match="literal string trigger key"):
        _assert_publish_image_workflow(source)


def test_publish_image_validator_rejects_extra_mutable_tag_push_step() -> None:
    source = _replace_workflow_once(
        PUBLISH_IMAGE_WORKFLOW.read_text(),
        "      - name: Report immutable image reference\n",
        """      - name: Push mutable candidate tag
        run: docker push ghcr.io/ktretina/nvmolkit-nemotron-chat:candidate

      - name: Report immutable image reference
""",
    )

    with pytest.raises(AssertionError, match="ordered workflow step contract"):
        _assert_publish_image_workflow(source)


def test_publish_image_validator_rejects_changed_action_sha() -> None:
    source = _replace_workflow_once(
        PUBLISH_IMAGE_WORKFLOW.read_text(),
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/checkout@0000000000000000000000000000000000000000",
    )

    with pytest.raises(AssertionError, match="ordered workflow step contract"):
        _assert_publish_image_workflow(source)


def test_publish_image_validator_rejects_altered_digest_report() -> None:
    source = _replace_workflow_once(
        PUBLISH_IMAGE_WORKFLOW.read_text(),
        'echo "Image: ${IMAGE}@${DIGEST}" >> "$GITHUB_STEP_SUMMARY"',
        'echo "Digest unavailable" >> "$GITHUB_STEP_SUMMARY"',
    )

    with pytest.raises(AssertionError, match="ordered workflow step contract"):
        _assert_publish_image_workflow(source)


def test_publish_image_validator_rejects_alternate_secret_syntax() -> None:
    source = _replace_workflow_once(
        PUBLISH_IMAGE_WORKFLOW.read_text(),
        "          persist-credentials: false\n",
        """          persist-credentials: false
          token: ${{ secrets['PACKAGE_TOKEN'] }}
""",
    )

    with pytest.raises(AssertionError, match="only GITHUB_TOKEN"):
        _assert_publish_image_workflow(source)


def test_deployment_docs_pin_image_source_and_preserve_architecture_limits() -> None:
    launchable = (ROOT / "deployment" / "launchable-fields.md").read_text()
    launchable_lower = launchable.lower()
    assert APP_IMAGE_BUILD_COMMIT in launchable
    assert APP_IMAGE in launchable
    assert (
        f"https://github.com/ktretina/nvmolkit-nemotron-chat/blob/"
        f"{APP_IMAGE_BUILD_COMMIT}/deployment/compose.yaml"
    ) in launchable
    assert "repository-root build context" not in launchable_lower
    assert "console compose parse" in launchable_lower
    assert "pending" in launchable_lower
    assert "unqualified" in launchable_lower

    readme = (ROOT / "README.md").read_text()
    assert "Linux x86-64 target-GPU hosts only" in readme
    assert "ARM64 Macs are unsupported" in readme
    assert "emulation has not been tested" in readme


def _valid_compose_config() -> dict[str, Any]:
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


def _load_authored_compose(source: str) -> dict[str, Any]:
    config = yaml.safe_load(source)
    assert isinstance(config, dict), "the authored Compose file must be a mapping"
    return config


def _assert_digest_pinned_app_image(config: dict[str, Any]) -> None:
    services = config.get("services")
    assert isinstance(services, dict), "services must be a mapping"

    app = services.get("app")
    assert isinstance(app, dict), "services.app must be a mapping"
    assert "build" not in app, "services.app must not define a build context"
    assert app.get("image") == APP_IMAGE, (
        "services.app.image must use the exact published digest"
    )


def test_authored_compose_uses_exact_published_image_without_build_context() -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )

    _assert_digest_pinned_app_image(config)


def test_image_validator_rejects_build_context_with_decoy_pinned_image() -> None:
    config = _load_authored_compose(
        f"""services:
  app:
    image: {APP_IMAGE}
    build:
      context: ..
"""
    )

    with pytest.raises(AssertionError, match="must not define a build context"):
        _assert_digest_pinned_app_image(config)


@pytest.mark.parametrize(
    "image",
    [
        "ghcr.io/ktretina/nvmolkit-nemotron-chat:latest",
        f"ghcr.io/ktretina/nvmolkit-nemotron-chat:{APP_IMAGE_BUILD_COMMIT}",
        "ghcr.io/decoy/nvmolkit-nemotron-chat@"
        "sha256:0931542cde79aa9d64438c7b720aa80adacb8ab328ab585af5b3b717937f5afb",
        "ghcr.io/ktretina/nvmolkit-nemotron-chat@"
        "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    ],
)
def test_image_validator_rejects_mutable_or_decoy_image(image: str) -> None:
    config = {"services": {"app": {"image": image}}}

    with pytest.raises(AssertionError, match="exact published digest"):
        _assert_digest_pinned_app_image(config)


def test_image_validator_ignores_decoy_image_outside_app() -> None:
    config = {
        "services": {
            "app": {},
            "decoy": {"image": APP_IMAGE},
        }
    }

    with pytest.raises(AssertionError, match="exact published digest"):
        _assert_digest_pinned_app_image(config)


def _assert_brev_gpu_reservation(config: dict[str, Any]) -> None:
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


def test_authored_compose_uses_one_brev_compatible_nvidia_gpu_reservation() -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )

    _assert_brev_gpu_reservation(config)


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="Docker CLI is unavailable; normalized Compose compatibility not checked",
)
def test_docker_compose_accepts_and_preserves_gpu_reservation() -> None:
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
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        unsupported_markers = (
            "unknown flag: --format",
            "unknown command \"compose\"",
            "is not a docker command",
        )
        if any(marker in detail.lower() for marker in unsupported_markers):
            pytest.skip(
                "Docker Compose config --format json is unavailable: "
                f"{detail or 'no diagnostic emitted'}"
            )
        pytest.fail(
            "Docker Compose rejected deployment/compose.yaml: "
            f"{detail or 'no diagnostic emitted'}"
        )

    try:
        config = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        pytest.fail(
            "Docker Compose config --format json did not emit valid JSON: "
            f"{error}"
        )

    assert isinstance(config, dict), "normalized Compose config must be a mapping"
    _assert_brev_gpu_reservation(config)


def test_gpu_validator_rejects_original_service_level_gpus() -> None:
    config: dict[str, Any] = {"services": {"app": {"gpus": "all"}}}

    with pytest.raises(AssertionError, match="services.app.gpus"):
        _assert_brev_gpu_reservation(config)


def test_gpu_validator_rejects_missing_reservation() -> None:
    config: dict[str, Any] = {"services": {"app": {}}}

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
    config = _load_authored_compose(
        """services:
  app: {}
  worker:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
"""
    )

    with pytest.raises(AssertionError, match="services.app.deploy"):
        _assert_brev_gpu_reservation(config)


@pytest.mark.parametrize("count_source", ['"1"', "${GPU_COUNT:-1}"])
def test_authored_gpu_count_rejects_strings_and_interpolation(
    count_source: str,
) -> None:
    config = _load_authored_compose(
        f"""services:
  app:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: {count_source}
              capabilities: [gpu]
"""
    )

    with pytest.raises(AssertionError, match="count must be the integer 1"):
        _assert_brev_gpu_reservation(config)
