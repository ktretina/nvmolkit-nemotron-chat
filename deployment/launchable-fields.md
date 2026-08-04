# Brev Console fields

Publication-dependent values are deliberately not presented as final yet. Task 8 must first publish and accept a commit in the new public repository.

- **Name:** `nvMolKit Nemotron Chat`
- **Description:** A GPU molecular-analysis chat demo with four bounded nvMolKit workflows, hosted Nemotron interpretation, and labeled 2D/3D visuals over bundled data.
- **Runtime mode:** Docker Compose.
- **Public repository:** `https://github.com/ktretina/nvmolkit-nemotron-chat` (expected destination; publication is pending Task 8).
- **Accepted commit:** `PENDING_TASK_8_PUBLICATION_AND_ACCEPTANCE`.
- **Compose source/resource:** `PENDING_TASK_8_CONSOLE_CONFIRMATION`. The supported field value must preserve a full accepted repository checkout because `deployment/compose.yaml` builds with repository-root context. A raw Compose YAML URL alone is not accepted: `raw.githubusercontent.com/.../deployment/compose.yaml` does not supply that build context. The Console-supported full-repository resource syntax is unverified and intentionally not invented here.
- **Architecture:** Linux x86-64.
- **Hardware:** One NVIDIA GPU with compute capability 7.0 or newer and a host driver that supports the CUDA 12.8 container runtime.
- **Disk:** 50 GiB.
- **Secure Link:** Port `8000`; access `Anyone with the link`.
- **Public ports:** No public TCP or UDP ports.
- **API key:** No Launchable variable or environment default. The user enters `NVIDIA_API_KEY` in the app's masked first-run field; the backend keeps it only in memory for the ephemeral session.
- **Authoring surface:** Author in the Brev Console unless a supported callable Launchable-authoring interface is verified. Do not reverse-engineer private Console endpoints.

**Blocking acceptance gate:** Before any deployment, Task 8 must confirm that the Console successfully parses the selected Compose resource, then read back that it resolves the full accepted repository checkout and exact accepted commit. Stop if the supported Console field cannot preserve repository-root build context.

The Launchable and its Secure Link remain unqualified until that Console gate and the Task 8 live acceptance run. Do not copy a credential into the repository, Compose file, Launchable defaults, logs, screenshots, or acceptance receipt.
