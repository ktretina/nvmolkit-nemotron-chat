# Brev Console fields

The corrected similarity-heatmap image is published and has passed runtime, GPU, and targeted Secure Link acceptance on the existing pinned L4 instance. The local Compose now names that immutable image. The Brev Launchable definition, full nine-step browser flow, and a separately authorized fresh deployment remain pending.

- **Name:** `nvMolKit Nemotron Chat`.
- **Description:** A GPU molecular-analysis chat demo with four bounded nvMolKit workflows, hosted Nemotron interpretation, and labeled 2D/3D visuals over bundled data.
- **Runtime mode:** Docker Compose.
- **Public repository:** `https://github.com/ktretina/nvmolkit-nemotron-chat`.
- **Image-build run:** GitHub Actions run [`31137134719`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31137134719), attempt 1, `success`.
- **Image-build commit:** `287e907ded4ba68e6c5db829da9e6e07357f60bb`.
- **Application image:** `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:278d4dacdedfae6c05d7effb28fa9c1d745262424a88e85696c363e17bba0afe`.
- **Linux/amd64 manifest:** `sha256:756654333de037ab093cc6e12063469a9cdea8f32ae6ce1f388fd53246f753d9`.
- **Compose source/resource:** Commit this local digest update only after approval, push that exact commit, verify its remote SHA, and then use its commit-pinned `deployment/compose.yaml` URL. The file is image-backed and does not build from a checked-out repository. No immutable URL is claimed before the metadata commit exists remotely.
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
- **Live runtime qualification on existing instance `he8b2ekuh`:** PASS.
- **GPU acceptance on that exact L4 deployment:** PASS for all four deterministic analyses.
- **Hosted Nemotron qualification:** PARTIAL; the suggested similarity workflow returned a substantive interpretation, but free-form routing remains pending.
- **Targeted similarity browser acceptance through the Secure Link:** PASS.
- **Full nine-step browser/UI acceptance:** PENDING.
- **Fresh deployment qualification:** PENDING.
- **Launchable-generated immutable deployment qualification:** PENDING.

**Blocking acceptance gate:** After this metadata change is separately approved, committed, pushed, and read back, the controller must use that exact immutable Compose anchor for Launchable `env-3HVH6EJJaIzVc6RYjBqUoYmw1gu`. A separately authorized fresh instance must then prove the resolved organization, Launchable ID, instance ID, provider, L4 SKU, image index and Linux/amd64 manifest, CUDA/nvMolKit runtime, all four deterministic analyses, hosted Nemotron routing/interpretation, session reset/end behavior, populated conformer controls, visible figures, Secure Link browser behavior, and zero confirmed credentials in submitted configuration, runtime logs, and evidence artifacts.

Until those gates pass, the existing manually updated instance is qualified only for the recorded runtime/GPU and targeted similarity checks; the Launchable remains **UNQUALIFIED** as a reproducible fresh deployment. Do not copy a credential into the repository, Compose file, Launchable defaults, logs, screenshots, or acceptance receipt. Local handoff metadata is not a Brev Console or platform mutation.
