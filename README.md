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

The latest browser-gated CI Linux/amd64 image build and push succeeded in GitHub Actions run [`31137134719`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31137134719) from commit `287e907ded4ba68e6c5db829da9e6e07357f60bb`. The immutable OCI index is `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:278d4dacdedfae6c05d7effb28fa9c1d745262424a88e85696c363e17bba0afe`; its Linux/amd64 manifest is `sha256:756654333de037ab093cc6e12063469a9cdea8f32ae6ce1f388fd53246f753d9`. The workflow verified backend tests, frontend unit tests, typechecking, the production build, and the production-CSS Chromium suite before publishing. The application and count-only live-log evidence recorded in the acceptance receipt contains zero confirmed NVIDIA credentials.

The exact image has passed immutable deployment and GPU acceptance on the existing pinned L4 instance: CUDA/nvMolKit readiness and all four deterministic analyses passed. The repaired similarity figure also passed targeted Secure Link browser acceptance. Full hosted Nemotron qualification, the complete nine-step browser flow, the Brev Launchable update, and a fresh deployment remain pending. See [`docs/acceptance/2026-08-06-live-ux-repair-receipt.md`](docs/acceptance/2026-08-06-live-ux-repair-receipt.md) for the bounded evidence and unresolved gates, [`docs/acceptance/demo-ready-receipt.md`](docs/acceptance/demo-ready-receipt.md) for historical evidence, `deployment/launchable-fields.md` for the controller handoff values, and `docs/superpowers/specs/2026-08-04-nvmolkit-nemotron-chat-design.md` for the approved completion boundary.

Passing local backend/frontend tests or producing a static frontend build proves only those local gates. The acceptance receipt separately records publication, existing-instance CUDA/scientific-output qualification, and targeted live-browser evidence. It does not qualify the unchanged Launchable or a fresh Launchable-generated deployment.

Likewise, passing the local Chromium suite does not qualify a published image or Launchable. The existing instance has passed the recorded L4/CUDA/nvMolKit and targeted similarity checks, while full hosted Nemotron and browser/UI acceptance remain partial. The Brev Launchable must reference an approved digest-pinned Compose revision and pass one separately authorized fresh deployment before the repair can be called complete.
