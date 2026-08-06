# Brev Console fields

The corrected browser-gated application image is published and pinned by a local immutable Compose anchor. Live runtime, GPU acceptance, hosted Nemotron, Secure Link browser acceptance, and a separately authorized fresh deployment remain pending.

- **Name:** `nvMolKit Nemotron Chat`.
- **Description:** A GPU molecular-analysis chat demo with four bounded nvMolKit workflows, hosted Nemotron interpretation, and labeled 2D/3D visuals over bundled data.
- **Runtime mode:** Docker Compose.
- **Public repository:** `https://github.com/ktretina/nvmolkit-nemotron-chat`.
- **Image-build run:** GitHub Actions run [`31126921793`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31126921793), attempt 1, `success`.
- **Image-build commit:** `7b82e3722075acad4868896716c1eb66ac642f65`.
- **Application image:** `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:1911d4eae820fad11b5aac8634fefcc69557ace82194870e2711896c134d2a08`.
- **Linux/amd64 manifest:** `sha256:7141d8c9cba22b473a064846f30f865bed3840a0b53bc386472d8bdb41cc05de`; compressed layer payload: 4,201,723,821 bytes (3.9131602468 GiB).
- **Compose source/resource:** After the approved Phase B push and exact remote readback, use `https://github.com/ktretina/nvmolkit-nemotron-chat/blob/80157583aeb19e6b20f4bb259336806d9a2e3fc1/deployment/compose.yaml`. Commit `80157583aeb19e6b20f4bb259336806d9a2e3fc1` is the local immutable Compose anchor; the file is image-backed and does not build from a checked-out repository. Do not use the URL until that commit is confirmed on the remote.
- **Architecture:** Linux x86-64 (`linux/amd64`).
- **Hardware:** Exactly one NVIDIA L4 GPU.
- **Disk:** 50 GiB.
- **Secure Link:** Port `8000`; access `Anyone with the link`.
- **Public ports:** No public TCP or UDP ports.
- **API key:** No Launchable variable or environment default. The user enters `NVIDIA_API_KEY` in the app's masked first-run field; the backend keeps it only in memory for the ephemeral session.
- **Authoring surface:** Author in the Brev Console unless a supported, callable, policy-compliant Launchable-authoring interface is verified. Do not reverse-engineer or call private Console endpoints.

## Qualification status

- **Image build and immutable registry identity:** PASS.
- **Local browser-gated CI verification:** PASS.
- **Live runtime qualification:** PENDING.
- **GPU acceptance on the exact L4 deployment:** PENDING.
- **Hosted Nemotron qualification:** PENDING.
- **Browser/UI acceptance through the Secure Link:** PENDING.
- **Fresh deployment qualification:** PENDING.
- **Immutable deployment qualification:** PENDING.

**Blocking acceptance gate:** After the Phase B commits are separately approved, pushed, and read back, the controller must use the exact immutable Compose anchor above for the confirmed Launchable. A separately authorized fresh instance must then prove the resolved organization, Launchable ID, instance ID, provider, L4 SKU, image index and Linux/amd64 manifest, CUDA/nvMolKit runtime, all four deterministic analyses, hosted Nemotron routing/interpretation, session reset/end behavior, populated conformer controls, visible figures, Secure Link browser behavior, and zero confirmed credentials in submitted configuration, runtime logs, and evidence artifacts.

Until those gates pass, the new artifact is **UNQUALIFIED** as a live deployment. Do not copy a credential into the repository, Compose file, Launchable defaults, logs, screenshots, or acceptance receipt. Local handoff metadata is not a Brev Console or platform mutation.
