# nvMolKit Nemotron Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and live-qualify a minimal Brev-hosted chat application whose four deterministic nvMolKit workflows produce correctly labeled 2D or 3D molecular visualizations.

**Architecture:** A React/Vite frontend talks to one FastAPI process. The backend holds ephemeral sessions, validates one of four high-level analysis requests, executes deterministic nvMolKit stages on one GPU, and returns typed Plotly or 3Dmol.js payloads; hosted Nemotron only selects a bounded free-form analysis or interprets computed summaries. A single Docker Compose service exposes the application through Brev Secure Link port 8000.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, OpenAI Python client, PyTorch 2.7.1 CUDA 12.8, nvMolKit 0.5.0, RDKit, React, TypeScript, Vite, Plotly.js, 3Dmol.js, Vitest, pytest, Docker Compose, NVIDIA Brev.

---

## File map

```text
backend/
  pyproject.toml                 Python dependencies and test configuration
  app/
    __init__.py
    config.py                    Non-secret model/runtime settings
    models.py                    Request, result, and visualization schemas
    sessions.py                  In-memory session lifecycle
    chemistry.py                 Four deterministic nvMolKit analyses
    visualizations.py            Plotly and 3D payload construction
    nemotron.py                  Hosted client and single-call validation
    main.py                      FastAPI routes and static frontend serving
data/
  sample_molecules.csv           Bundled source dataset
  PROVENANCE.md                  Source commit, upstream source, and boundaries
frontend/
  package.json
  package-lock.json              Locked frontend dependency graph
  vite.config.ts
  tsconfig.json
  index.html
  src/
    api.ts                       Typed HTTP calls
    types.ts                     Backend response types
    App.tsx                      Key gate, chat, prompt routing, viewer state
    AdaptiveViewer.tsx           Plotly/3Dmol.js switch
    styles.css                   Two-pane and stacked layouts
    App.test.tsx                 Critical interaction tests
    AdaptiveViewer.test.tsx      Visualization contract rendering tests
deployment/
  Dockerfile                     Multi-stage frontend/backend GPU image
  compose.yaml                   One GPU-enabled app service
  launchable-fields.md           Exact Brev Console configuration
tests/
  conftest.py                    Deterministic fixtures and fake executor
  test_chemistry.py              Analysis ordering and validation
  test_visualizations.py         Titles, axes, units, hover, finite values
  test_sessions.py               Ephemeral key lifecycle
  test_nemotron.py               Exact single-call and redaction rules
  test_api.py                    Prompt/free-form/error integration
  test_gpu_acceptance.py         Opt-in live nvMolKit GPU gate
README.md                        Setup, boundaries, local tests, Brev use
THIRD_PARTY_NOTICES.md           Adapted-source and dependency notices
```

### Task 1: Establish provenance and the minimal Python package

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `data/sample_molecules.csv`
- Create: `data/PROVENANCE.md`
- Create: `THIRD_PARTY_NOTICES.md`
- Modify: `README.md`

- [ ] **Step 1: Record the source identity without modifying it**

Run:

```bash
git -C ../nvmolkit-brev-notebook rev-parse HEAD
git -C ../nvmolkit-brev-notebook status --short
```

Expected: commit `dd27240` as the short hash, or a newly reviewed successor; only the already-observed untracked `.DS_Store` may appear. If the commit differs, inspect the diff before adapting code and record the accepted 40-character hash.

- [ ] **Step 2: Add the package configuration**

Create `backend/pyproject.toml` with the exact runtime boundary:

```toml
[project]
name = "nvmolkit-nemotron-chat"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
  "fastapi==0.116.1",
  "openai==1.97.1",
  "pandas==2.3.1",
  "pydantic==2.11.7",
  "rdkit==2025.3.3",
  "uvicorn[standard]==0.35.0",
]

[project.optional-dependencies]
test = ["httpx==0.28.1", "pytest==8.4.1", "pytest-asyncio==1.1.0"]

[tool.pytest.ini_options]
addopts = "-q"
pythonpath = ["."]
testpaths = ["../tests"]
```

Keep CUDA wheels in `deployment/Dockerfile`, because platform-specific torch/nvMolKit installation does not belong in the portable package metadata.

- [ ] **Step 3: Add secret-free configuration**

Create `backend/app/config.py`:

```python
from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    nemotron_model: str = "nvidia/nemotron-3-nano-30b-a3b"
    session_idle_seconds: int = 3600
    data_path: str = "/app/data/sample_molecules.csv"


SETTINGS = Settings()
```

Do not add an API-key field or environment-variable default.

- [ ] **Step 4: Adapt the bundled data and provenance**

Use `apply_patch` to create `data/sample_molecules.csv` from the source file at the accepted commit. Create `data/PROVENANCE.md` containing the exact source repository URL, accepted commit, original file path, row count, columns (`molecule_id`, `smiles`), and the statement that the sample supports cheminformatics demonstration only.

Create `THIRD_PARTY_NOTICES.md` with links to nvMolKit, RDKit, Plotly.js, 3Dmol.js, and the source notebook. Do not claim that the source notebook's missing license grants third-party reuse; record that this adaptation is performed by the repository owner.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python3 -c "import csv; rows=list(csv.DictReader(open('data/sample_molecules.csv'))); assert rows and set(rows[0]) == {'molecule_id','smiles'}; print(len(rows))"
git diff --check
```

Expected: a positive row count and no whitespace errors.

Commit:

```bash
git add backend data README.md THIRD_PARTY_NOTICES.md
git commit -m "chore: establish minimal app package and provenance"
```

### Task 2: Implement four deterministic chemistry analyses with TDD

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/chemistry.py`
- Create: `tests/conftest.py`
- Create: `tests/test_chemistry.py`

- [ ] **Step 1: Write failing analysis-contract tests**

Create `tests/test_chemistry.py` with a fake low-level runtime so CPU-local tests prove orchestration without claiming GPU execution:

```python
from app.chemistry import AnalysisEngine, AnalysisKind


def test_cluster_analysis_runs_prerequisites_once(fake_runtime):
    engine = AnalysisEngine(fake_runtime)
    result = engine.run(AnalysisKind.CLUSTERS, {})
    assert fake_runtime.calls == ["load", "fingerprints", "similarity", "clusters"]
    assert result.kind == AnalysisKind.CLUSTERS


def test_conformer_analysis_reuses_cached_prerequisites(fake_runtime):
    engine = AnalysisEngine(fake_runtime)
    engine.run(AnalysisKind.SIMILARITY, {})
    engine.run(AnalysisKind.CONFORMERS, {})
    assert fake_runtime.calls.count("fingerprints") == 1
    assert fake_runtime.calls.count("similarity") == 1
    assert fake_runtime.calls[-3:] == ["clusters", "embed", "optimize"]


def test_rejects_out_of_range_parameters(fake_runtime):
    engine = AnalysisEngine(fake_runtime)
    try:
        engine.run(AnalysisKind.FINGERPRINT_DENSITY, {"fingerprint_radius": 9})
    except ValueError as exc:
        assert "fingerprint_radius" in str(exc)
    else:
        raise AssertionError("invalid radius was accepted")
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_chemistry.py -q
```

Expected: collection fails because `app.chemistry` does not exist.

- [ ] **Step 3: Define the high-level contracts**

Create `backend/app/models.py` and `backend/app/chemistry.py` with these public types:

```python
from enum import StrEnum
from typing import Any, Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field


class AnalysisKind(StrEnum):
    FINGERPRINT_DENSITY = "fingerprint_density"
    SIMILARITY = "similarity"
    CLUSTERS = "clusters"
    CONFORMERS = "conformers"


class AnalysisParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint_radius: Literal[2, 3] = 2
    fingerprint_size: Literal[1024, 2048] = 2048
    cluster_cutoff: float = Field(default=0.50, ge=0.40, le=0.60)
    representative_count: int = Field(default=3, ge=3, le=6)
    conformers_per_molecule: int = Field(default=5, ge=3, le=8)


class AnalysisResult(BaseModel):
    kind: AnalysisKind
    summary: dict[str, Any]
    artifact: dict[str, Any]


class ChemistryRuntime(Protocol):
    def load(self) -> Any:
        raise NotImplementedError

    def fingerprints(self, state: Any, params: AnalysisParameters) -> Any:
        raise NotImplementedError

    def similarity(self, state: Any) -> Any:
        raise NotImplementedError

    def clusters(self, state: Any, params: AnalysisParameters) -> Any:
        raise NotImplementedError

    def embed(self, state: Any, params: AnalysisParameters) -> Any:
        raise NotImplementedError

    def optimize(self, state: Any) -> Any:
        raise NotImplementedError
```

Implement `AnalysisEngine.run()` as the only public orchestrator. It validates with `AnalysisParameters.model_validate`, advances only through the required ordered stages, caches stage state on the engine, and returns one `AnalysisResult` for the requested kind.

- [ ] **Step 4: Adapt the nvMolKit runtime**

Port only the needed source logic from `chemistry_workflow.py`: CSV/RDKit parsing, `MorganFingerprintGenerator`, `crossTanimotoSimilarity`, `fused_butina`, `EmbedMolecules`, `MMFFOptimizeMoleculesConfs`, CUDA synchronization before host reads, and authoritative `(molecule_index, conformer_index)` coordinate reconciliation.

Preserve these fail-closed checks in code and tests:

```python
if tuple(fingerprints.torch().shape) != (molecule_count, params.fingerprint_size // 32):
    raise RuntimeError("unexpected packed fingerprint shape")
if not numpy.isfinite(similarity_matrix).all():
    raise RuntimeError("similarity matrix contains non-finite values")
if len(set(result_pairs)) != len(result_pairs):
    raise RuntimeError("duplicate molecule/conformer result pairs")
```

- [ ] **Step 5: Run GREEN and commit**

Run:

```bash
PYTHONPATH=backend python3 -m pytest tests/test_chemistry.py -q
```

Expected: all chemistry orchestration tests pass; no claim about GPU execution.

Commit:

```bash
git add backend/app/models.py backend/app/chemistry.py tests/conftest.py tests/test_chemistry.py
git commit -m "feat: add deterministic nvMolKit analysis engine"
```

### Task 3: Enforce labeled visualization payloads

**Files:**
- Create: `backend/app/visualizations.py`
- Create: `tests/test_visualizations.py`

- [ ] **Step 1: Write failing visualization tests**

Create `tests/test_visualizations.py`:

```python
import math
from app.visualizations import build_cluster_chart, build_similarity_heatmap


def test_cluster_chart_has_required_labels():
    payload = build_cluster_chart([4, 2], ["CHEMBL1", "CHEMBL2"])
    assert payload["layout"]["title"]["text"] == "Molecular similarity cluster sizes"
    assert payload["layout"]["xaxis"]["title"]["text"] == "Cluster ID"
    assert payload["layout"]["yaxis"]["title"]["text"] == "Molecule count"
    assert payload["data"][0]["hovertemplate"]


def test_similarity_heatmap_rejects_nonfinite_values():
    try:
        build_similarity_heatmap([[1.0, math.nan], [math.nan, 1.0]], ["A", "B"])
    except ValueError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("non-finite heatmap accepted")
```

- [ ] **Step 2: Run RED**

Run `PYTHONPATH=backend python3 -m pytest tests/test_visualizations.py -q`.

Expected: import failure for `app.visualizations`.

- [ ] **Step 3: Implement only four payload builders**

Create these four builders:

```python
def build_fingerprint_histogram(active_bits: list[int]) -> dict:
    payload = {
        "kind": "fingerprint_density",
        "data": [{"type": "histogram", "x": active_bits, "hovertemplate": "%{x} active bits<extra></extra>"}],
        "layout": {
            "title": {"text": "Morgan fingerprint density"},
            "xaxis": {"title": {"text": "Active Morgan fingerprint bits per molecule"}},
            "yaxis": {"title": {"text": "Molecule count"}},
        },
    }
    require_finite(payload)
    return payload


def build_similarity_heatmap(matrix: list[list[float]], molecule_ids: list[str]) -> dict:
    if len(matrix) != len(molecule_ids) or any(len(row) != len(molecule_ids) for row in matrix):
        raise ValueError("similarity matrix and molecule IDs must be square and aligned")
    custom = [[f"{left} × {right}" for right in molecule_ids] for left in molecule_ids]
    payload = {
        "kind": "similarity",
        "data": [{
            "type": "heatmap", "z": matrix, "customdata": custom, "zmin": 0, "zmax": 1,
            "colorbar": {"title": {"text": "Tanimoto similarity — unitless, 0 to 1"}},
            "hovertemplate": "%{customdata}<br>Similarity: %{z:.3f}<extra></extra>",
        }],
        "layout": {
            "title": {"text": "Pairwise molecular similarity"},
            "xaxis": {"title": {"text": "Molecule index — bundled ChEMBL set"}},
            "yaxis": {"title": {"text": "Molecule index — bundled ChEMBL set"}},
        },
    }
    require_finite(payload)
    return payload


def build_cluster_chart(cluster_sizes: list[int], representative_ids: list[str]) -> dict:
    if len(cluster_sizes) != len(representative_ids):
        raise ValueError("cluster sizes and representatives must align")
    payload = {
        "kind": "clusters",
        "data": [{
            "type": "bar", "x": list(range(len(cluster_sizes))), "y": cluster_sizes,
            "customdata": representative_ids,
            "hovertemplate": "Cluster %{x}<br>Molecules: %{y}<br>Representative: %{customdata}<extra></extra>",
        }],
        "layout": {
            "title": {"text": "Molecular similarity cluster sizes"},
            "xaxis": {"title": {"text": "Cluster ID"}},
            "yaxis": {"title": {"text": "Molecule count"}},
        },
    }
    require_finite(payload)
    return payload


def build_conformer_bundle(records: list[dict], structures: list[dict]) -> dict:
    if not records or len(records) != len(structures):
        raise ValueError("conformer records and structures must be nonempty and aligned")
    payload = {
        "kind": "conformers",
        "viewer": {"structures": structures, "atom_legend": True, "xyz_triad": True},
        "energy_plot": {
            "data": [{
                "type": "bar",
                "x": [row["conformer_id"] for row in records],
                "y": [row["relative_energy_kcal_mol"] for row in records],
                "hovertemplate": "%{x}<br>Relative energy: %{y:.3f} kcal/mol<extra></extra>",
            }],
            "layout": {
                "title": {"text": "Sampled conformer energies"},
                "xaxis": {"title": {"text": "Conformer ID"}},
                "yaxis": {"title": {"text": "Relative MMFF94 energy (kcal/mol)"}},
            },
        },
    }
    require_finite(payload)
    return payload
```

Each Plotly payload must set `layout.title.text`, `layout.xaxis.title.text`, `layout.yaxis.title.text`, and a non-empty `hovertemplate`. The heatmap must set a colorbar title of `Tanimoto similarity — unitless, 0 to 1`. The conformer bundle must contain atom/bond data, conformer selector labels, an atom legend, an XYZ triad marker, and an energy Plotly payload labeled `Relative MMFF94 energy (kcal/mol)`.

Add one shared finite-number walker:

```python
def require_finite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("visualization values must be finite")
    if isinstance(value, dict):
        for item in value.values():
            require_finite(item)
    if isinstance(value, (list, tuple)):
        for item in value:
            require_finite(item)
```

- [ ] **Step 4: Run GREEN and commit**

Run `PYTHONPATH=backend python3 -m pytest tests/test_visualizations.py -q`.

Expected: all visualization tests pass.

Commit:

```bash
git add backend/app/visualizations.py tests/test_visualizations.py
git commit -m "feat: add validated scientific visualization payloads"
```

### Task 4: Add ephemeral sessions and bounded Nemotron calls

**Files:**
- Create: `backend/app/sessions.py`
- Create: `backend/app/nemotron.py`
- Create: `tests/test_sessions.py`
- Create: `tests/test_nemotron.py`

- [ ] **Step 1: Write failing session tests**

```python
def test_expired_session_removes_key(session_store, clock):
    token = session_store.create("nvapi-test")
    clock.advance(3601)
    assert session_store.get(token) is None


def test_session_repr_never_contains_key(session_store):
    token = session_store.create("nvapi-secret")
    assert "nvapi-secret" not in repr(session_store.get(token))
```

Run `PYTHONPATH=backend python3 -m pytest tests/test_sessions.py -q`.

Expected: import/fixture failure.

- [ ] **Step 2: Implement the smallest in-memory store**

Use a random 32-byte URL-safe token, a `Session` dataclass with `repr=False` on the key, monotonic last-access time, and `create/get/delete` methods. No background cleanup service is needed; prune expired entries on each public method.

```python
@dataclass
class Session:
    api_key: str = field(repr=False)
    touched_at: float
    engine: AnalysisEngine
    latest_visualization: dict | None = None
```

- [ ] **Step 3: Write failing Nemotron validation tests**

Cover exactly one call, correct name, valid JSON arguments, forbidden extras, and redacted API errors:

```python
def test_rejects_multiple_tool_calls(fake_completion):
    fake_completion.tool_calls = [tool_call("analyze_similarity_map", {}), tool_call("analyze_cluster_distribution", {})]
    with pytest.raises(NemotronProtocolError, match="exactly one"):
        parse_analysis_call(fake_completion)


def test_api_error_does_not_echo_key(fake_client):
    with pytest.raises(NemotronError) as error:
        select_analysis(fake_client, "nvapi-secret", "map similarity")
    assert "nvapi-secret" not in str(error.value)
```

- [ ] **Step 4: Implement four high-level tool schemas**

Map tool names one-to-one to `AnalysisKind`. Parse with strict Pydantic models and reject zero or multiple calls. Send only the user's free-form text, four tool schemas, and a brief bounded system instruction. For result interpretation, send only `AnalysisResult.summary` and the visualization label metadata; never send `artifact` coordinates or matrices.

If interpretation fails after a deterministic suggested prompt, return `None` and let the API preserve the computed figure.

- [ ] **Step 5: Run GREEN and commit**

Run:

```bash
PYTHONPATH=backend python3 -m pytest tests/test_sessions.py tests/test_nemotron.py -q
```

Expected: all session and Nemotron protocol tests pass.

Commit:

```bash
git add backend/app/sessions.py backend/app/nemotron.py tests/test_sessions.py tests/test_nemotron.py
git commit -m "feat: add ephemeral sessions and bounded Nemotron adapter"
```

### Task 5: Expose the minimal FastAPI contract

**Files:**
- Create: `backend/app/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Cover only the required endpoints:

```python
def test_suggested_prompt_bypasses_model(client, fake_executor, fake_nemotron):
    authenticate(client)
    response = client.post("/api/chat", json={"prompt_id": "similarity"})
    assert response.status_code == 200
    assert response.json()["visualization"]["kind"] == "similarity"
    assert fake_nemotron.selection_calls == 0


def test_failed_request_preserves_prior_visual(client, fake_executor):
    authenticate(client)
    first = client.post("/api/chat", json={"prompt_id": "clusters"}).json()
    fake_executor.fail_next = True
    failed = client.post("/api/chat", json={"prompt_id": "similarity"})
    assert failed.status_code == 422
    current = client.get("/api/session").json()
    assert current["visualization"] == first["visualization"]
```

- [ ] **Step 2: Run RED**

Run `PYTHONPATH=backend python3 -m pytest tests/test_api.py -q`.

Expected: import failure for `app.main`.

- [ ] **Step 3: Implement five routes**

Implement:

```text
POST   /api/session/key   accept masked first-run key, set Secure/HttpOnly/SameSite=Strict cookie
GET    /api/session       return chat-safe state, never the key
DELETE /api/session       clear session and cookie
POST   /api/chat          accept exactly one of prompt_id or message
GET    /api/health        return process plus cached CUDA/PyTorch/nvMolKit readiness
```

Use this request constraint:

```python
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_id: Literal["fingerprints", "similarity", "clusters", "conformers"] | None = None
    message: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def exactly_one_input(self):
        if (self.prompt_id is None) == (self.message is None):
            raise ValueError("provide exactly one of prompt_id or message")
        return self
```

Suggested prompts map directly to `AnalysisKind`; free-form requests call Nemotron selection. Build the visualization before asking for interpretation. Promote session state only after validation. Return secret-safe error codes and user-facing messages.

- [ ] **Step 4: Run GREEN and commit**

Run `PYTHONPATH=backend python3 -m pytest tests/test_api.py -q`.

Expected: all API tests pass.

Commit:

```bash
git add backend/app/main.py tests/test_api.py
git commit -m "feat: expose bounded chat API"
```

### Task 6: Build the two-pane React experience

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/AdaptiveViewer.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/App.test.tsx`
- Create: `frontend/src/AdaptiveViewer.test.tsx`

- [ ] **Step 1: Scaffold only required dependencies**

Create `frontend/package.json` with the current reviewed pins:

```json
{
  "name": "nvmolkit-nemotron-chat-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest"
  },
  "dependencies": {
    "3dmol": "2.5.5",
    "plotly.js": "3.7.0",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-plotly.js": "4.1.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "7.0.0",
    "@testing-library/dom": "10.4.1",
    "@testing-library/react": "16.3.2",
    "@types/react": "19.2.18",
    "@types/react-dom": "19.2.4",
    "@types/react-plotly.js": "2.6.4",
    "@vitejs/plugin-react": "6.0.5",
    "jsdom": "30.0.1",
    "typescript": "7.0.2",
    "vite": "8.2.0",
    "vitest": "4.1.10"
  }
}
```

Do not add a state library, router, component framework, or CSS framework.

Run `npm install --package-lock-only` once to create `frontend/package-lock.json`, then use `npm ci` for every subsequent install and build.

- [ ] **Step 2: Write failing interaction tests**

```tsx
it("requires a key before showing chat", () => {
  render(<App />)
  expect(screen.getByLabelText(/nvidia api key/i)).toHaveAttribute("type", "password")
  expect(screen.queryByRole("button", { name: /map structural similarity/i })).not.toBeInTheDocument()
})

it("renders all four suggested prompts after authentication", async () => {
  mockAuthenticatedSession()
  render(<App />)
  expect(await screen.findAllByTestId("suggested-prompt")).toHaveLength(4)
})
```

Run `npm test -- --run` in `frontend`.

Expected: tests fail because components do not exist.

- [ ] **Step 3: Implement key gate and chat**

Keep state local to `App`: session status, messages, request state, error, and latest visualization. Clear the key input immediately after successful `POST /api/session/key`. Prompt buttons send only stable IDs; free-form text sends only `message`.

The chat must show computation status, interpretation-unavailable status, errors, and scientific boundary text without displaying raw tool JSON.

- [ ] **Step 4: Implement the adaptive viewer**

`AdaptiveViewer` switches only on the four typed visualization kinds. Pass Plotly payloads directly to `react-plotly.js`. For conformers, create one 3Dmol viewer, replace its model when the selection changes, expose molecule/conformer and rendering-style controls, render the atom legend, and keep the accompanying labeled energy graph visible.

Add tests that assert graph axis-title strings are passed to Plotly and that conformer controls appear only for `kind="conformers"`.

- [ ] **Step 5: Add the approved layout**

Use CSS Grid with `minmax(320px, 38%) 1fr`, full viewport height, dark neutral surfaces, NVIDIA green only for active controls/status, and a single-column media query below 800 px. Do not add menus, dashboards, animations beyond loading feedback, or visual settings.

- [ ] **Step 6: Run GREEN, build, and commit**

Run:

```bash
npm test -- --run
npm run build
```

Expected: all Vitest tests pass and Vite produces `dist/`.

Commit:

```bash
git add frontend
git commit -m "feat: add chat and adaptive molecular viewer"
```

### Task 7: Package one GPU-enabled application service

**Files:**
- Create: `deployment/Dockerfile`
- Create: `deployment/compose.yaml`
- Create: `deployment/launchable-fields.md`
- Create: `tests/test_gpu_acceptance.py`
- Modify: `README.md`

- [ ] **Step 1: Add the opt-in GPU acceptance test**

```python
import os
import pytest
import torch

from app.chemistry import AnalysisKind
from app.visualizations import require_finite


@pytest.mark.skipif(os.getenv("RUN_GPU_TESTS") != "1", reason="requires explicit GPU acceptance")
def test_all_four_analyses_on_cuda(live_engine):
    assert torch.cuda.is_available()
    for kind in AnalysisKind:
        result = live_engine.run(kind, {})
        assert result.kind == kind
        require_finite(result.model_dump())
```

The fixture must load the bundled data and real nvMolKit runtime; it must not fall back to RDKit.

- [ ] **Step 2: Build one container**

Create a multi-stage Dockerfile:

1. Node stage runs `npm ci`, tests, and `npm run build`.
2. Python/CUDA stage uses a reviewed CUDA-compatible base, installs CPython 3.12, `torch==2.7.1+cu128`, `nvmolkit==0.5.0`, and `backend/pyproject.toml` dependencies.
3. Copy frontend `dist/`, backend, and data.
4. Run as a non-root application user when compatible with GPU access.
5. Start `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

Pin the base by digest only after a successful build and GPU run; record the human-readable tag in a comment.

- [ ] **Step 3: Add one-service Compose**

```yaml
services:
  app:
    build:
      context: ..
      dockerfile: deployment/Dockerfile
    ports:
      - "8000:8000"
    gpus: all
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 12
```

Do not add volumes, databases, API-key environment variables, or extra services.

- [ ] **Step 4: Write exact Brev fields**

Document Docker Compose mode, public repository and accepted commit, Compose URL, one compatible NVIDIA GPU, Linux x86-64, 50 GiB disk, Secure Link port 8000, “Anyone with the link,” and no public TCP/UDP. State that the key is entered in-app and the Launchable is authored in Console unless a supported callable authoring interface is verified.

- [ ] **Step 5: Verify locally and commit**

Run:

```bash
docker compose -f deployment/compose.yaml config
docker build -f deployment/Dockerfile -t nvmolkit-nemotron-chat:local .
docker history --no-trunc nvmolkit-nemotron-chat:local
```

Expected: Compose validates, the image builds, and history contains no credential. On a non-GPU Mac, explicitly record GPU run as not run.

Commit:

```bash
git add deployment tests/test_gpu_acceptance.py README.md
git commit -m "feat: package Brev GPU web application"
```

### Task 8: Verify, publish, and live-qualify the demo

**Files:**
- Create: `docs/acceptance/demo-ready-receipt.md`
- Modify: `README.md`

- [ ] **Step 1: Run the complete local gate**

Run fresh:

```bash
PYTHONPATH=backend python3 -m pytest tests -m "not gpu" -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
docker compose -f deployment/compose.yaml config
git grep -n -E 'nvapi-[A-Za-z0-9_-]{10,}|NVIDIA_API_KEY=' -- . ':!docs/superpowers'
git status --short
```

Expected: tests and build pass, Compose validates, secret grep returns no credential, and only intended acceptance/documentation changes remain.

- [ ] **Step 2: Create the public GitHub repository**

Verify `ktretina/nvmolkit-nemotron-chat` is still absent, then run:

```bash
gh repo create ktretina/nvmolkit-nemotron-chat --public --source=. --remote=origin --push
gh repo view ktretina/nvmolkit-nemotron-chat --json nameWithOwner,visibility,url,defaultBranchRef
```

Expected: visibility `PUBLIC`, default branch `main`, and the accepted local commits pushed. Do not configure GitHub Actions unless separately requested.

- [ ] **Step 3: Obtain the bounded Brev contract**

Before billable or shared-state mutation, record and obtain approval for: exact organization, task label, instance name, exclusive ownership, allowed provider/SKU or GPU types, maximum hourly price, total budget, one-instance concurrency, provisioning-attempt limit, permitted hosted requests, lifecycle actions, idle timeout, expiry, artifact retention, and stop-after-test behavior. Do not run `brev set`, `brev org set`, `brev refresh`, or `brev login` without separate serialized authorization.

- [ ] **Step 4: Author or receive the Launchable ID**

Use the supported Brev Console builder with `deployment/launchable-fields.md`. If this task lacks a supported authenticated authoring surface, ask the user to perform that single Console step and return the Launchable ID or URL. Do not reverse-engineer private Console endpoints.

- [ ] **Step 5: Deploy exactly one authorized instance**

Re-check `/opt/homebrew/bin/brev --version` and `/opt/homebrew/bin/brev create --help`. Deploy the exact Launchable within the approved contract, read back the exact organization, Launchable, instance ID, provider, and SKU, and reject a mismatch. Prevent duplicate creates after an ambiguous response.

- [ ] **Step 6: Run live acceptance through Secure Link**

Enter a dedicated limited-scope key in the masked field without recording it. Run all four suggested prompts and verify the expected visualization, title, axes, units, hover content, and scientific boundary. Run one supported free-form request and one unsupported request. Verify the latest valid figure remains after the unsupported request.

Run the opt-in GPU test on the instance:

```bash
RUN_GPU_TESTS=1 PYTHONPATH=backend python3 -m pytest tests/test_gpu_acceptance.py -v
```

Expected: the four real nvMolKit analyses pass on CUDA.

- [ ] **Step 7: Write the redacted receipt and stop**

Record exact identities, timestamps, commands, pass/fail counts, visualization checks, and secret-scan result in `docs/acceptance/demo-ready-receipt.md`. Record unrun gates as `not_run`. Never record the key or raw credential-bearing requests.

Stop the exact instance under the approved lifecycle contract. Delete it only if deletion was explicitly authorized.

- [ ] **Step 8: Commit and push the receipt**

```bash
git add README.md docs/acceptance/demo-ready-receipt.md
git commit -m "docs: record live Brev demo qualification"
git push origin main
```

Expected: public repository main contains the redacted acceptance receipt and no secret; the task-owned instance is stopped.
