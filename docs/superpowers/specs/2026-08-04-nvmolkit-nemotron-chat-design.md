# nvMolKit Nemotron Chat Design

**Date:** 2026-08-04  
**Status:** Regenerated for approval
**Repository:** `ktretina/nvmolkit-nemotron-chat`  
**Target:** A demo-ready Brev Launchable

## 1. Guiding principle

Do as much as necessary and as little as possible to achieve the project goals.

This project is one small, reliable web application. It is not a platform. Every component must directly support one of these outcomes:

1. A user can ask about the bundled molecular data.
2. The four suggested prompts reliably produce the expected labeled visualization.
3. Bounded free-form requests can use the same predefined analyses.
4. The app runs through an authenticated Brev Secure Link and passes one live demo qualification.

## 2. Product goal

Turn the guided workflow in `ktretina/nvmolkit-brev-notebook` into a two-pane chat application:

- Chat and suggested prompts on the left.
- The latest validated 2D or 3D result on the right.
- Hosted Nemotron selects or explains an analysis.
- Deterministic Python code executes nvMolKit and creates the actual visualization.

The application uses only the bundled dataset. Conversations, computed results, and API keys are ephemeral.

## 3. Strict scope

### Build

- A React chat interface and adaptive viewer.
- A FastAPI backend.
- Four predefined analysis functions backed by nvMolKit.
- Plotly for graphs and 3Dmol.js for conformers.
- One Docker Compose application service.
- Exact Brev Console instructions and one live qualification.

### Do not build

- Uploads, arbitrary datasets, arbitrary tools, or arbitrary code execution.
- Accounts, a database, saved chats, persistent result storage, or analytics.
- Multiple agents, an MCP server, job queues, or a general workflow engine.
- A locally hosted Nemotron model.
- Download/export features, collaboration, administration, or user preferences.
- Performance claims, production hardening, or release-ready qualification.
- Biological activity, binding, ADMET, efficacy, safety, clinical, or experimental-conformation claims.

## 4. User experience

### 4.1 First run

The app initially shows a masked `NVIDIA_API_KEY` field. The browser sends the key to the backend through the Brev Secure Link, clears the field after acceptance, and never receives the key back.

The backend stores the key only in memory for the current session. An opaque secure cookie identifies the session. Sixty minutes of inactivity or a backend restart clears the key, chat, cached results, and current visualization. No database or disk persistence is used.

### 4.2 Main screen

- Full-height chat pane on the left.
- Adaptive visualization pane on the right.
- Four suggested prompts above the composer until chat begins; a compact prompt menu keeps them available afterward.
- The viewer header identifies the analysis function that produced the visible result.
- A failed request leaves the last valid result visible and labels it as belonging to the earlier successful message.
- On narrow screens, chat stacks above the viewer.

### 4.3 Guaranteed suggested prompts

Each button sends a stable prompt ID directly to a deterministic backend function. Nemotron does not choose the route. A prompt succeeds only after the expected visualization payload validates.

| Suggested prompt | Deterministic function | Required result |
| --- | --- | --- |
| “Show the Morgan fingerprint density across the bundled molecules.” | `analyze_fingerprint_density` | Histogram titled “Morgan fingerprint density”; X: “Active Morgan fingerprint bits per molecule”; Y: “Molecule count.” |
| “Map structural similarity across the bundled dataset.” | `analyze_similarity_map` | Heatmap with X and Y: “Molecule index — bundled ChEMBL set”; color scale: “Tanimoto similarity — unitless, 0 to 1”; hover shows both ChEMBL IDs and exact value. |
| “Cluster the molecules by structural similarity and show the cluster sizes.” | `analyze_cluster_distribution` | Bar chart with X: “Cluster ID”; Y: “Molecule count”; hover shows cluster size and representative ChEMBL ID. |
| “Generate and compare optimized 3D conformers for representative molecules.” | `analyze_representative_conformers` | Interactive molecule/conformer selector with atom legend and XYZ orientation triad; companion graph with X: “Conformer ID” and Y: “Relative MMFF94 energy (kcal/mol).” |

Every graph must include a descriptive title, labeled axes, units or “unitless,” a legend or color scale when applicable, and useful hover text. Payload validation rejects a graph missing required labels.

For a suggested prompt, the validated computation and visualization do not depend on Nemotron returning an interpretation. If interpretation fails after computation, show the figure with a concise “Interpretation unavailable” notice. Free-form routing still requires Nemotron because the model must select the analysis.

### 4.4 Free-form chat

Nemotron may select exactly one of the same four high-level analysis functions with bounded parameters. Each function runs any missing prerequisites in the correct order and returns a complete visualization in the same chat turn.

The backend rejects missing, malformed, multiple, unknown, or out-of-range calls before GPU execution. Unsupported requests explain the available analyses and offer the four prompt buttons.

Nemotron interprets only compact validated summaries. It never receives credentials, tensors, full similarity matrices, molecular coordinates, RDKit objects, or GPU objects. It does not supply numerical graph values or declare execution success.

## 5. Minimal architecture

```text
Browser
  ├─ React chat and prompt buttons
  └─ Plotly or 3Dmol.js viewer
           │
           ▼
FastAPI application
  ├─ in-memory session
  ├─ deterministic prompt router
  ├─ bounded Nemotron client
  ├─ four analysis functions
  └─ typed visualization responses
           │
           ▼
nvMolKit + bundled molecular data on one NVIDIA GPU
```

One backend process is sufficient. Use a few focused Python modules for sessions, Nemotron validation, chemistry, and visualization; do not introduce services or abstractions until a concrete requirement needs them.

The four analysis functions may reuse these low-level stages from the source workflow: data validation, Morgan fingerprints, Tanimoto similarity, fused Butina clustering, representative selection, ETKDG conformer embedding, and MMFF94 optimization. Intermediate results are cached only within the current session.

The backend promotes a chat response and visualization only after the full requested analysis validates. Partial results are not shown as successful.

## 6. Failure behavior

- Missing or rejected key: show a masked authentication error and run nothing.
- Unsupported request: explain the four available analyses.
- Invalid Nemotron call: reject before GPU execution.
- Nemotron interpretation failure after a suggested-prompt computation: keep the validated figure and mark only the interpretation unavailable.
- Missing CUDA, GPU, or nvMolKit: show a readiness error; do not silently substitute RDKit.
- Invalid dimensions or non-finite values: reject the result.
- Partial conformer generation or non-convergence: identify it explicitly and show only valid conformers.
- Any error: redact the key and preserve the previous valid visualization.

## 7. Repository and provenance

Create a fresh public Apache-2.0 repository with no fork relationship, shared Git history, worktree, or submodule with `ktretina/nvmolkit-brev-notebook`. Keep the source repository read-only.

Adapt only the data and workflow code needed by the four analyses. Record the exact source commit and dataset provenance. Do not copy credentials, outputs, caches, Git metadata, runtime evidence, or unrelated documentation.

Minimal repository shape:

```text
frontend/       React application
backend/        FastAPI, Nemotron validation, chemistry, visualization
data/           bundled sample and provenance
deployment/     Dockerfile, compose.yaml, Brev field instructions
tests/          focused backend, frontend, and integration checks
docs/           design and implementation plan
```

## 8. Packaging and Brev

Use a multi-stage Dockerfile to build React and serve its static files from the FastAPI container. Compose defines one service, one GPU reservation, one health check, and port `8000`.

Begin compatibility work from the source pins: CPython 3.12, `torch==2.7.1+cu128`, and `nvmolkit==0.5.0`. Pin the accepted base image by digest after it builds and runs successfully.

Brev configuration:

- Docker Compose runtime.
- Linux x86-64, one compatible NVIDIA GPU, and at least 50 GiB disk.
- Exact accepted commit from the new public repository.
- Secure Link on port `8000`.
- “Anyone with the link” access.
- No public TCP or UDP ports.
- No API key in the repository, image, Compose defaults, Launchable defaults, logs, screenshots, or receipts.

The app exposes one health endpoint that reports process and cached CUDA/PyTorch/nvMolKit readiness without sensitive details.

The repository provides the exact Console fields. If no supported callable Launchable-authoring interface is available, the user performs only the Console creation step and returns the Launchable ID or URL. The CLI may then deploy the existing Launchable.

## 9. Minimum verification necessary

Before publication:

1. Run focused backend tests for the four routes, bounded function validation, workflow ordering, result validation, and secret redaction.
2. Run focused frontend tests for key entry, prompt buttons, error state, and switching among graph and 3D views.
3. Build the production frontend and container; validate Compose and the health check.
4. Run a targeted tracked-file and container-history secret scan.

For live qualification:

1. Obtain a bounded authorization for one named Brev instance, organization, allowed hardware and maximum hourly price, provisioning-attempt limit, and stop-after-test permission.
2. Record the exact Launchable, instance, provider/SKU, repository commit, and container digest.
3. Through the Secure Link, run all four suggested prompts and verify the expected labeled visualization for each.
4. Run one supported free-form request and one unsupported request.
5. Confirm no credential appears in logs or the redacted receipt.
6. Stop the instance.

Do not add SBOM generation, exhaustive benchmarks, restart qualification, penetration testing, or independent review to the demo-critical path. Do not claim those gates passed.

## 10. Completion boundary

The project is complete when the new public repository contains the verified application and deployment instructions, and one fresh Brev deployment passes the six live-qualification steps above.

This establishes a working demo only. It does not establish production readiness or scientific validity beyond the exact computed outputs.

## 11. Public references

- Source launchable: https://github.com/ktretina/nvmolkit-brev-notebook
- NVIDIA nvMolKit: https://github.com/NVIDIA-BioNeMo/nvMolKit
- nvMolKit documentation: https://nvidia-bionemo.github.io/nvMolKit/
- NVIDIA Brev Launchables: https://docs.nvidia.com/brev/concepts/launchables
