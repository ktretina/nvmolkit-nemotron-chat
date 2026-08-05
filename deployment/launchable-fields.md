# Brev Console fields

The application image is published, but Brev Console parsing and live qualification remain pending.

- **Name:** `nvMolKit Nemotron Chat`
- **Description:** A GPU molecular-analysis chat demo with four bounded nvMolKit workflows, hosted Nemotron interpretation, and labeled 2D/3D visuals over bundled data.
- **Runtime mode:** Docker Compose.
- **Public repository:** `https://github.com/ktretina/nvmolkit-nemotron-chat`.
- **Image-build commit:** `0ac0fb00bc1fc49bc23982f1c2a0a2e51db53980` (`linux/amd64`).
- **Application image:** `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:0931542cde79aa9d64438c7b720aa80adacb8ab328ab585af5b3b717937f5afb`.
- **Compose source/resource:** In Brev Console, use the commit-pinned GitHub blob URL `https://github.com/ktretina/nvmolkit-nemotron-chat/blob/0ac0fb00bc1fc49bc23982f1c2a0a2e51db53980/deployment/compose.yaml`. The Compose file is image-backed and requires no source-repository build context. Brev Console Compose parse is **PENDING**; this URL is not yet claimed accepted.
- **Architecture:** Linux x86-64.
- **Hardware:** One NVIDIA GPU with compute capability 7.0 or newer and a host driver that supports the CUDA 12.8 container runtime.
- **Disk:** 50 GiB.
- **Secure Link:** Port `8000`; access `Anyone with the link`.
- **Public ports:** No public TCP or UDP ports.
- **API key:** No Launchable variable or environment default. The user enters `NVIDIA_API_KEY` in the app's masked first-run field; the backend keeps it only in memory for the ephemeral session.
- **Authoring surface:** Author in the Brev Console unless a supported callable Launchable-authoring interface is verified. Do not reverse-engineer private Console endpoints.

**Blocking acceptance gate:** Before any deployment, confirm that the Console successfully parses the commit-pinned Compose resource and resolves the exact digest-pinned image above.

The Launchable and its Secure Link remain unqualified until that Console gate and a live acceptance run. Do not copy a credential into the repository, Compose file, Launchable defaults, logs, screenshots, or acceptance receipt.
