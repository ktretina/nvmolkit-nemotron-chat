# nvMolKit Nemotron Chat

A minimal molecular-analysis chat application with a React interface, FastAPI backend, bounded hosted Nemotron calls, and four deterministic nvMolKit workflows over bundled data.

This is an independent repository, not a continuation or fork of [`ktretina/nvmolkit-brev-notebook`](https://github.com/ktretina/nvmolkit-brev-notebook), which is kept read-only for this project and session. It adapts that project's sample molecule CSV with explicit provenance; see [`data/PROVENANCE.md`](data/PROVENANCE.md).

## What the app does

- Accepts an `NVIDIA_API_KEY` through a masked **Start workspace** field and holds it only in backend memory for an ephemeral session. Starting a workspace stores a nonblank key but does not pre-validate it with the hosted provider.
- Offers four reliable suggested prompts: Morgan fingerprint density, pairwise Tanimoto similarity, similarity-cluster sizes, and optimized representative conformers.
- Allows bounded free-form chat to select exactly one of those same analyses.
- Shows the latest validated Plotly graph or 3Dmol.js conformer view in an adaptive pane. Graphs include descriptive titles, labeled axes, units where applicable, and useful hover text.
- Supports consecutive suggested and free-form tasks within one workspace. **New analysis** clears analysis/chat state while preserving the session token and API key; **End session** deletes the credential-bearing server session and returns to key entry.
- Reports hosted Nemotron availability through fixed, secret-safe categories without displaying raw provider response bodies.

The bundled sample supports a cheminformatics demonstration only. The app does not accept uploads, execute arbitrary tools, persist chats, or make biological, clinical, efficacy, or safety claims.

## Local validation

Backend tests require CPython 3.12 and the test dependencies from `backend/pyproject.toml`:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

Frontend tests and the static production build use the locked npm dependency graph:

```bash
cd frontend
npm ci
npm test -- --run
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

`npm run test:e2e` rebuilds the production bundle and runs the production-CSS Chromium gate. It verifies the desktop and mobile composer/figure layout, inactive conformer visibility, populated conformer selectors, one retained 3D viewer, **New analysis**, and **End session**. JSDOM unit tests alone are not sufficient for these computed-layout behaviors.

`tests/test_gpu_acceptance.py` is intentionally skipped unless `RUN_GPU_TESTS=1`. That opt-in gate imports the real `nvmolkit==0.5.0` runtime, requires `torch==2.7.1+cu128` and CUDA, loads `data/sample_molecules.csv`, runs every `AnalysisKind`, and validates finite visualization payloads. There is no RDKit analysis fallback:

```bash
cd backend
RUN_GPU_TESTS=1 .venv/bin/python -m pytest ../tests/test_gpu_acceptance.py -q
```

## Container and Brev packaging

`deployment/compose.yaml` defines one GPU-enabled application service on port 8000. The multi-stage image runs the locked frontend tests/build and installs `torch==2.7.1+cu128`, `nvmolkit==0.5.0`, and its compatible published CPython 3.12 distribution pin `rdkit==2026.3.1` before serving the static UI through FastAPI as a non-root user. CUDA 12.8 user-space libraries come from the pinned PyTorch/nvMolKit dependency resolution; the target host supplies the compatible NVIDIA driver.

Compose structure can be checked anywhere the Docker Compose CLI is available:

```bash
docker compose -f deployment/compose.yaml config
```

The image build is for Linux x86-64 target-GPU hosts only. ARM64 Macs are unsupported because the published `nvmolkit==0.5.0` wheels are Linux x86-64; emulation has not been tested or qualified.

```bash
docker build -f deployment/Dockerfile -t nvmolkit-nemotron-chat:local .
```

The browser-gated CI Linux/amd64 image build and push succeeded exactly once in GitHub Actions run [`31126921793`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31126921793) from commit `7b82e3722075acad4868896716c1eb66ac642f65`. The immutable OCI index is `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:1911d4eae820fad11b5aac8634fefcc69557ace82194870e2711896c134d2a08`; its Linux/amd64 manifest is `sha256:7141d8c9cba22b473a064846f30f865bed3840a0b53bc386472d8bdb41cc05de`, with 4,201,723,821 compressed layer bytes (3.9131602468 GiB). The workflow verified backend tests, frontend unit tests, typechecking, the production build, and the production-CSS Chromium suite before publishing. Registry metadata, provenance, history, and extracted application/build layers were inspected without executing the image: application layers and NVIDIA-key-shape scans had zero findings, while metadata-only Gitleaks findings were the public `GPG_KEY` fingerprint inherited unchanged from the resolved official Python base image. Confirmed credentials: zero.

This publication evidence qualifies the immutable image build and registry artifact only. The image has not run on an L4, the real GPU acceptance test remains unrun, and hosted Nemotron, Secure Link browser behavior, and a fresh Brev deployment remain pending. See [`docs/acceptance/2026-08-06-live-ux-repair-receipt.md`](docs/acceptance/2026-08-06-live-ux-repair-receipt.md) for the repair evidence and unresolved gates, [`docs/acceptance/demo-ready-receipt.md`](docs/acceptance/demo-ready-receipt.md) for historical evidence, `deployment/launchable-fields.md` for the controller handoff values, and `docs/superpowers/specs/2026-08-04-nvmolkit-nemotron-chat-design.md` for the approved completion boundary.

Passing local backend/frontend tests or producing a static frontend build proves only those local gates. Public repository publication is recorded separately in the acceptance receipt; it does not qualify the CUDA image, scientific outputs on the target GPU, hosted service, Launchable, or live demo. Those acceptance gates remain pending.

Likewise, passing the local Chromium suite does not qualify a published image or Launchable. The corrected immutable image must still pass live L4/CUDA/nvMolKit, hosted Nemotron, Secure Link browser, and secret-scan checks on the confirmed instance. The Brev Launchable must then reference the accepted digest-pinned Compose revision and pass one separately authorized fresh deployment before the repair can be called complete.
