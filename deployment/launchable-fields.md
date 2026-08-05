# Brev Console fields

The compiler-equipped application image is published, but its immutable deployment and GPU acceptance remain pending.

- **Name:** `nvMolKit Nemotron Chat`
- **Description:** A GPU molecular-analysis chat demo with four bounded nvMolKit workflows, hosted Nemotron interpretation, and labeled 2D/3D visuals over bundled data.
- **Runtime mode:** Docker Compose.
- **Public repository:** `https://github.com/ktretina/nvmolkit-nemotron-chat`.
- **Image-build run:** GitHub Actions run [`31048410625`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31048410625).
- **Image-build commit:** `572241e9bc9cf49f2614f8ef5a2566f54b831645` (`linux/amd64`).
- **Application image:** `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:10c8297827ed96bce8f413986cec13e77b2b266555527c1f21e425082d0fec88`.
- **Linux/amd64 manifest:** `sha256:a3e69c03c8eda6ee3d5dbc92af4284b46ab671ecb915fa3d744ccd79a475c61e`; compressed layer payload: 4,201,741,858 bytes (3.9131770451 GiB).
- **Compose source/resource:** In Brev Console, use the immutable Phase A GitHub blob URL `https://github.com/ktretina/nvmolkit-nemotron-chat/blob/6d05a76c93ea22aa62fcfc92af61b1421e02a1d7/deployment/compose.yaml`. The Compose file is image-backed and requires no source-repository build context.
- **Architecture:** Linux x86-64.
- **Hardware:** One NVIDIA GPU with compute capability 7.0 or newer and a host driver that supports the CUDA 12.8 container runtime.
- **Disk:** 50 GiB.
- **Secure Link:** Port `8000`; access `Anyone with the link`.
- **Public ports:** No public TCP or UDP ports.
- **API key:** No Launchable variable or environment default. The user enters `NVIDIA_API_KEY` in the app's masked first-run field; the backend keeps it only in memory for the ephemeral session.
- **Authoring surface:** Author in the Brev Console unless a supported callable Launchable-authoring interface is verified. Do not reverse-engineer private Console endpoints.

**Blocking acceptance gate:** The controller must deploy the exact digest-pinned image above from the Phase A Compose revision, then complete GPU acceptance without modifying the running container. Until that succeeds, immutable deployment and GPU acceptance are **PENDING** and the new artifact is **UNQUALIFIED**.

The new immutable deployment and its Secure Link remain unqualified until that live acceptance run. Hosted Nemotron qualification and browser/UI acceptance also remain **PENDING**. Do not copy a credential into the repository, Compose file, Launchable defaults, logs, screenshots, or acceptance receipt.
