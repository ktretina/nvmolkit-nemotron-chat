"""Static dependency-contract checks for the GPU application image."""

from __future__ import annotations

from copy import deepcopy
import json
import re
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_IMAGE_WORKFLOW = ROOT / ".github" / "workflows" / "publish-image.yml"
APP_IMAGE_BUILD_COMMIT = "aec792aef589adf315ba37c60a3cf145a52c868c"
APP_IMAGE_BUILD_RUN = "31032058838"
IMAGE_BACKED_COMPOSE_COMMIT = "e6130081d421b421e553223375a130b2365d08ab"
APP_IMAGE = (
    "ghcr.io/ktretina/nvmolkit-nemotron-chat@"
    "sha256:3dca44cd15b16526f9f02fcd8df0ea54d67032210ab6ddd49dcb98895bc6c3f2"
)
APP_HEALTHCHECK = {
    "test": [
        "CMD",
        "python",
        "-c",
        "import urllib.request; "
        "urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)",
    ],
    "interval": "10s",
    "timeout": "5s",
    "retries": 12,
}
APP_ENVIRONMENT = {"TRITON_CACHE_DIR": "/tmp/triton-cache"}
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
            r'"\$VIRTUAL_ENV/bin/python" -m pip install\b.*?(?=\s+&&|$)',
            flattened,
        )
        if "nvmolkit==" in command
    )
    assert "torch==2.7.1+cu128" in nvmolkit_install
    assert "/tmp/backend" in nvmolkit_install


def test_runtime_uses_slim_python_base_with_cuda_wheel_dependencies() -> None:
    dockerfile = (ROOT / "deployment" / "Dockerfile").read_text()
    from_lines = re.findall(r"^FROM\s+(.+)$", dockerfile, flags=re.MULTILINE)
    runtime_stages = [line for line in from_lines if line.endswith(" AS runtime")]

    assert runtime_stages == ["python:3.12-slim-bookworm AS runtime"]
    assert not any(line.startswith("nvidia/cuda") for line in from_lines)
    assert "torch==2.7.1+cu128" in dockerfile
    assert "nvmolkit==0.5.0" in dockerfile
    assert "--extra-index-url https://download.pytorch.org/whl/cu128" in dockerfile
    assert "--no-deps" not in dockerfile
    pip_interpreters = re.findall(
        r"&&\s+([^\s]+)\s+-m pip install", dockerfile
    )
    assert pip_interpreters == [
        '"$VIRTUAL_ENV/bin/python"',
        '"$VIRTUAL_ENV/bin/python"',
    ]


def _logical_dockerfile_instructions(source: str) -> list[str]:
    instructions: list[str] = []
    continued: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if not continued and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            continued.append(stripped[:-1].rstrip())
            continue
        continued.append(stripped)
        instructions.append(" ".join(continued))
        continued = []

    assert not continued, "Dockerfile must not end with a continued instruction"
    return instructions


def _runtime_run_commands(source: str) -> list[str]:
    commands: list[str] = []
    in_runtime = False
    for instruction in _logical_dockerfile_instructions(source):
        keyword, separator, argument = instruction.partition(" ")
        if keyword.upper() == "FROM":
            in_runtime = bool(
                re.search(r"\bAS\s+runtime\s*$", argument, flags=re.IGNORECASE)
            )
        elif in_runtime and separator and keyword.upper() == "RUN":
            commands.append(argument)
    return commands


def _shell_segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments: list[list[str]] = []
    current: list[str] = []
    for token in lexer:
        if token and set(token) <= set(";&|"):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _assert_runtime_apt_contract(source: str) -> None:
    runtime_runs = _runtime_run_commands(source)
    assert len(runtime_runs) == 3, "runtime stage must define exactly three RUNs"
    installs: list[tuple[list[list[str]], int, int]] = []
    assignment = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
    for run_command in runtime_runs:
        segments = _shell_segments(run_command)
        for segment_index, segment in enumerate(segments):
            for index, token in enumerate(segment):
                executable = token.rsplit("/", 1)[-1]
                arguments = segment[index + 1 :]
                if executable in {"apt", "apt-get"} and "install" in arguments:
                    installs.append((segments, segment_index, index))

    assert len(installs) == 1, "runtime must execute exactly one apt-get install"
    segments, install_segment_index, install_command_index = installs[0]
    assert len(segments) == 3
    assert install_segment_index == 1
    assert segments[0] == ["apt-get", "update"]
    assert segments[2] == ["rm", "-rf", "/var/lib/apt/lists/*"]
    segment = segments[install_segment_index]
    direct_command_index = 0
    while (
        direct_command_index < len(segment)
        and assignment.fullmatch(segment[direct_command_index])
    ):
        direct_command_index += 1
    assert install_command_index == direct_command_index
    assert segment[install_command_index] == "apt-get"
    arguments = segment[install_command_index + 1 :]
    install_index = arguments.index("install")
    package_tokens = [
        token for token in arguments[install_index + 1 :] if not token.startswith("-")
    ]
    assert "--no-install-recommends" in arguments
    assert len(package_tokens) == 3
    packages = set(package_tokens)
    assert packages == {"ca-certificates", "gcc", "libc6-dev"}
    assert packages.isdisjoint({"build-essential", "g++", "make"})


def test_runtime_installs_only_required_triton_compiler_packages() -> None:
    _assert_runtime_apt_contract(
        (ROOT / "deployment" / "Dockerfile").read_text()
    )


@pytest.mark.parametrize(
    "decoy",
    [
        "echo apt-get install --yes --no-install-recommends "
        "ca-certificates gcc libc6-dev && true",
        'echo "apt-get install --yes --no-install-recommends '
        'ca-certificates gcc libc6-dev" && true',
    ],
)
def test_runtime_apt_validator_rejects_echo_decoy(decoy: str) -> None:
    source = (ROOT / "deployment" / "Dockerfile").read_text()
    run_start = source.index("RUN apt-get update")
    run_end = source.index("\n\nCOPY backend/", run_start)
    mutated = source[:run_start] + f"RUN {decoy}" + source[run_end:]

    with pytest.raises(AssertionError):
        _assert_runtime_apt_contract(mutated)


@pytest.mark.parametrize(
    "install_command",
    [
        "apt-get install -y make",
        "apt-get -y install make",
        "apt-get install --yes make",
        "apt install -y make",
    ],
)
def test_runtime_apt_validator_rejects_second_install(
    install_command: str,
) -> None:
    source = (ROOT / "deployment" / "Dockerfile").read_text()
    mutated = f"{source}\nRUN {install_command}\n"

    with pytest.raises(AssertionError):
        _assert_runtime_apt_contract(mutated)


@pytest.mark.parametrize(
    "install_command",
    [
        "sudo apt-get install -y make",
        "env apt-get install -y make",
        "command apt-get install -y make",
        "/usr/bin/apt-get install -y make",
        "if true; then apt-get install -y make; fi",
    ],
)
def test_runtime_apt_validator_rejects_wrapped_or_conditional_install(
    install_command: str,
) -> None:
    source = (ROOT / "deployment" / "Dockerfile").read_text()
    mutated = f"{source}\nRUN {install_command}\n"

    with pytest.raises(AssertionError):
        _assert_runtime_apt_contract(mutated)


@pytest.mark.parametrize(
    "extra_run",
    [
        "sh -c 'apt-get install -y make'",
        '["apt-get","install","-y","make"]',
    ],
)
def test_runtime_apt_validator_rejects_any_extra_run(extra_run: str) -> None:
    source = (ROOT / "deployment" / "Dockerfile").read_text()
    mutated = f"{source}\nRUN {extra_run}\n"

    with pytest.raises(AssertionError):
        _assert_runtime_apt_contract(mutated)


def test_runtime_apt_validator_rejects_split_install_lifecycle() -> None:
    source = (ROOT / "deployment" / "Dockerfile").read_text()
    run_start = source.index("RUN apt-get update")
    run_end = source.index("\n\nCOPY backend/", run_start)
    split_lifecycle = """RUN apt-get update
RUN apt-get install --yes --no-install-recommends ca-certificates gcc libc6-dev
RUN rm -rf /var/lib/apt/lists/*"""
    mutated = source[:run_start] + split_lifecycle + source[run_end:]

    with pytest.raises(AssertionError):
        _assert_runtime_apt_contract(mutated)


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
        f"{IMAGE_BACKED_COMPOSE_COMMIT}/deployment/compose.yaml"
    ) in launchable
    assert "repository-root build context" not in launchable_lower
    assert "console compose parse" in launchable_lower
    assert "pending" in launchable_lower
    assert "unqualified" in launchable_lower

    readme = (ROOT / "README.md").read_text()
    assert "Linux x86-64 target-GPU hosts only" in readme
    assert "ARM64 Macs are unsupported" in readme
    assert "emulation has not been tested" in readme
    assert APP_IMAGE_BUILD_RUN in readme
    assert APP_IMAGE_BUILD_COMMIT in readme
    assert APP_IMAGE in readme
    assert "CI Linux/amd64 image build and push succeeded" in readme
    assert "The Docker build" not in readme
    assert "container execution and history scan remain pending" in readme
    assert "Brev Console and Secure Link acceptance remain unqualified" in readme


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
        "sha256:3dca44cd15b16526f9f02fcd8df0ea54d67032210ab6ddd49dcb98895bc6c3f2",
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


def _assert_authored_compose_contract(config: dict[str, Any]) -> None:
    services = config.get("services")
    assert isinstance(services, dict), "services must be a mapping"
    assert set(services) == {"app"}, (
        "Compose must define exactly one service named app"
    )

    _assert_digest_pinned_app_image(config)
    _assert_brev_gpu_reservation(config)

    app = services["app"]
    assert app.get("environment") == APP_ENVIRONMENT, (
        "services.app.environment must set only "
        "TRITON_CACHE_DIR=/tmp/triton-cache"
    )
    assert app.get("ports") == ["8000:8000"], (
        "services.app.ports must be exactly ['8000:8000']"
    )
    assert app.get("healthcheck") == APP_HEALTHCHECK, (
        "services.app.healthcheck must be exactly the authored readiness probe"
    )


def test_authored_compose_matches_complete_single_service_contract() -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )

    _assert_authored_compose_contract(config)


def test_authored_contract_rejects_extra_build_backed_mutable_service() -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )
    config["services"]["worker"] = {
        "build": {"context": "."},
        "image": "ghcr.io/ktretina/nvmolkit-nemotron-chat:latest",
    }

    with pytest.raises(AssertionError, match="exactly one service named app"):
        _assert_authored_compose_contract(config)


@pytest.mark.parametrize(
    "environment",
    [None, {"TRITON_CACHE_DIR": "/tmp/changed-triton-cache"}],
)
def test_authored_contract_rejects_missing_or_changed_triton_cache_dir(
    environment: dict[str, str] | None,
) -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )
    if environment is None:
        config["services"]["app"].pop("environment", None)
    else:
        config["services"]["app"]["environment"] = environment

    with pytest.raises(AssertionError, match="TRITON_CACHE_DIR"):
        _assert_authored_compose_contract(config)


@pytest.mark.parametrize("ports", [None, ["9000:8000"]])
def test_authored_contract_rejects_missing_or_changed_port(
    ports: list[str] | None,
) -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )
    if ports is None:
        config["services"]["app"].pop("ports")
    else:
        config["services"]["app"]["ports"] = ports

    with pytest.raises(AssertionError, match="ports must be exactly"):
        _assert_authored_compose_contract(config)


@pytest.mark.parametrize("healthcheck", [None, {"retries": 11}])
def test_authored_contract_rejects_missing_or_changed_healthcheck(
    healthcheck: dict[str, Any] | None,
) -> None:
    config = _load_authored_compose(
        (ROOT / "deployment" / "compose.yaml").read_text()
    )
    if healthcheck is None:
        config["services"]["app"].pop("healthcheck")
    else:
        changed_healthcheck = deepcopy(
            config["services"]["app"]["healthcheck"]
        )
        changed_healthcheck.update(healthcheck)
        config["services"]["app"]["healthcheck"] = changed_healthcheck

    with pytest.raises(AssertionError, match="healthcheck must be exactly"):
        _assert_authored_compose_contract(config)


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
