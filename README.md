# nvMolKit Nemotron Chat

A minimal molecular-analysis chat application with a React interface, FastAPI backend, bounded hosted Nemotron calls, and four deterministic nvMolKit workflows over bundled data.

This is an independent repository, not a continuation or fork of [`ktretina/nvmolkit-brev-notebook`](https://github.com/ktretina/nvmolkit-brev-notebook), which is kept read-only for this project and session. It adapts that project's sample molecule CSV with explicit provenance; see [`data/PROVENANCE.md`](data/PROVENANCE.md).

## What the app does

- Accepts an `NVIDIA_API_KEY` through a masked first-run field and holds it only in backend memory for an ephemeral session.
- Offers four reliable suggested prompts: Morgan fingerprint density, pairwise Tanimoto similarity, similarity-cluster sizes, and optimized representative conformers.
- Allows bounded free-form chat to select exactly one of those same analyses.
- Shows the latest validated Plotly graph or 3Dmol.js conformer view in an adaptive pane. Graphs include descriptive titles, labeled axes, units where applicable, and useful hover text.

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
npm run build
```

`tests/test_gpu_acceptance.py` is intentionally skipped unless `RUN_GPU_TESTS=1`. That opt-in gate imports the real `nvmolkit==0.5.0` runtime, requires `torch==2.7.1+cu128` and CUDA, loads `data/sample_molecules.csv`, runs every `AnalysisKind`, and validates finite visualization payloads. There is no RDKit analysis fallback:

```bash
cd backend
RUN_GPU_TESTS=1 .venv/bin/python -m pytest ../tests/test_gpu_acceptance.py -q
```

## Container and Brev packaging

`deployment/compose.yaml` defines one GPU-enabled application service on port 8000. The multi-stage image runs the locked frontend tests/build and installs `torch==2.7.1+cu128`, `nvmolkit==0.5.0`, and its compatible published CPython 3.12 distribution pin `rdkit==2026.3.1` before serving the static UI through FastAPI as a non-root user.

Compose structure can be checked anywhere the Docker Compose CLI is available:

```bash
docker compose -f deployment/compose.yaml config
```

The image build is for Linux x86-64 target-GPU hosts only. ARM64 Macs are unsupported because the published `nvmolkit==0.5.0` wheels are Linux x86-64; emulation has not been tested or qualified.

```bash
docker build -f deployment/Dockerfile -t nvmolkit-nemotron-chat:local .
```

The CI Linux/amd64 image build and push succeeded in GitHub Actions run [`31019738589`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31019738589) from commit `0ac0fb00bc1fc49bc23982f1c2a0a2e51db53980` at exact image `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:0931542cde79aa9d64438c7b720aa80adacb8ab328ab585af5b3b717937f5afb`; container execution and history scan remain pending. Real GPU/nvMolKit execution, hosted Nemotron, and browser acceptance also remain pending, and Brev Console and Secure Link acceptance remain unqualified. This CI publication evidence does not qualify the image runtime or live deployment. See [`docs/acceptance/demo-ready-receipt.md`](docs/acceptance/demo-ready-receipt.md) for the historical local evidence and unresolved gates, `deployment/launchable-fields.md` for the pending Brev Console values, and `docs/superpowers/specs/2026-08-04-nvmolkit-nemotron-chat-design.md` for the approved completion boundary.

Passing local backend/frontend tests or producing a static frontend build proves only those local gates. Public repository publication is recorded separately in the acceptance receipt; it does not qualify the CUDA image, scientific outputs on the target GPU, hosted service, Launchable, or live demo. Those acceptance gates remain pending.
