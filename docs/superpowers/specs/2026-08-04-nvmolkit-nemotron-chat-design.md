# nvMolKit Nemotron Chat Design

**Date:** 2026-08-04  
**Status:** Approved in conversation; awaiting written-spec review  
**Repository:** `ktretina/nvmolkit-nemotron-chat`  
**Target:** Demo-ready Brev Launchable

## 1. Objective

Build a compact Brev-hosted molecular-analysis application that transforms the guided workflow in `ktretina/nvmolkit-brev-notebook` into a chat-first web interface. Users interact with a full-height chat pane on the left and an adaptive scientific visualization pane on the right. Hosted Nemotron interprets bounded requests and computed results; deterministic Python code validates and executes all nvMolKit operations.

The project uses only its bundled molecular dataset, keeps each session ephemeral, and stores the user's NVIDIA API key only in server memory. Completion includes a fresh public GitHub repository and one live, clean Brev qualification within a separately approved cost and lifecycle contract.

## 2. Isolation and provenance

- Initialize a fresh repository with Apache-2.0 licensing and no shared Git history, fork relationship, submodule, or worktree with the source notebook.
- Keep `ktretina/nvmolkit-brev-notebook` read-only throughout this project.
- Adapt only the source workflow concepts and necessary code into independently organized modules.
- Preserve dataset and third-party provenance in the new repository.
- Record the exact accepted source commit used for adaptation before copying any source-controlled material.
- Do not copy credentials, notebook outputs, caches, runtime evidence, Git metadata, or unrelated source-project documentation.

## 3. Product scope

### Included

- Bundled molecular dataset only.
- Masked first-run `NVIDIA_API_KEY` entry.
- Four deterministic suggested prompts.
- Bounded free-form chat over the same dataset and allow-listed operations.
- GPU-accelerated nvMolKit fingerprints, similarity, clustering, conformer embedding, and MMFF94 optimization.
- Adaptive Plotly charts and 3Dmol.js molecular rendering.
- Ephemeral chat, result cache, visualization state, and API-key state.
- Docker Compose packaging, Brev Console field instructions, Secure Link access, and live demo qualification.

### Excluded

- File uploads, arbitrary datasets, arbitrary Python execution, or arbitrary tools.
- Accounts, a database, persistent chat history, saved credentials, or cross-session state.
- Local Nemotron weights.
- Binding, activity, ADMET, efficacy, safety, synthesizability, clinical, or experimental-conformation claims.
- Performance claims or release-ready security/scientific qualification.

## 4. User experience

### 4.1 Layout

The application uses a responsive two-pane desktop layout inspired by the provided reference:

- Left pane: product introduction, suggested prompts, chat transcript, status messages, and composer.
- Right pane: latest validated visualization, its title, producing function, view selector, and scientific metadata.
- Suggested prompts remain visible until the first conversation begins and remain recoverable from a compact prompt menu.
- A failed request preserves the previous valid visualization and labels it as belonging to the earlier successful message.
- On narrower screens, the application stacks chat above the viewer without removing functionality.

### 4.2 First-run key entry

- Before chat is enabled, show a masked NVIDIA API key field with a concise explanation of its use.
- Submit the key over the Brev-authenticated Secure Link to the backend.
- Retain it only in backend process memory for the ephemeral session.
- Identify the session with an opaque random token in a `Secure`, `HttpOnly`, `SameSite=Strict` cookie; never place the API key or molecular results in that cookie.
- Expire a session after 60 minutes of inactivity. A backend restart also invalidates every session.
- Clear the browser input immediately after successful submission.
- Never write, return, log, cache to disk, or include the key in an error message.
- Session expiry clears key, chat, computed cache, and viewer state.

### 4.3 Suggested prompts

Each suggested prompt carries a stable prompt ID mapped directly to a deterministic workflow. It does not rely on model-selected routing.

1. **Fingerprint density**  
   “Show the Morgan fingerprint density across the bundled molecules.”
2. **Similarity map**  
   “Map structural similarity across the bundled dataset.”
3. **Cluster sizes**  
   “Cluster the molecules by structural similarity and show the cluster sizes.”
4. **Representative conformers**  
   “Generate and compare optimized 3D conformers for representative molecules.”

The backend reports a suggested prompt as successful only after its expected typed visualization payload passes schema, dimensional, and finite-value validation. Required upstream stages run automatically and unchanged intermediate results are cached in the session.

### 4.4 Free-form chat

- Nemotron may select exactly one of four high-level, allow-listed analysis functions and a bounded parameter set: `analyze_fingerprint_density`, `analyze_similarity_map`, `analyze_cluster_distribution`, or `analyze_representative_conformers`.
- Each high-level function is a deterministic orchestrator that runs any missing low-level prerequisites in the correct order and returns the requested terminal visualization bundle in the same chat turn.
- The high-level interface prevents the model from directly invoking or reordering raw workflow stages such as host transfer, synchronization, representative selection, or optimization-result reconciliation.
- The backend rejects missing, malformed, multiple, unexpected, or invalid function calls before GPU execution.
- Unsupported requests receive a concise explanation and links to the four available prompt actions.
- Nemotron may interpret validated results but may not supply graph values, coordinates, or execution success.

## 5. Architecture

### 5.1 Components

- **React/Vite frontend:** chat, key-entry gate, prompt controls, result state, Plotly, and 3Dmol.js.
- **FastAPI backend:** session lifecycle, request validation, prompt routing, health endpoints, and typed responses.
- **Nemotron adapter:** hosted inference client, four high-level allow-listed analysis schemas, strict single-call response validation, and secret-safe errors.
- **Chemistry executor:** deterministic workflow state machine for bundled-data inspection, fingerprints, similarity, fused Butina clustering, representative selection, ETKDG conformer embedding, and MMFF94 optimization.
- **Visualization builders:** convert validated scientific results into typed Plotly or 3D payloads without asking the model to invent values.
- **In-memory session store:** API key, workflow state, chat transcript, latest visualization, and cached results with explicit expiry.

### 5.2 Request flow

1. The frontend sends either a stable suggested-prompt ID or free-form message with its opaque session identifier.
2. The backend checks session validity and API-key availability.
3. Suggested prompts take the deterministic route. Free-form requests go through bounded Nemotron selection of exactly one high-level analysis function.
4. The chemistry executor validates workflow eligibility and parameters before invoking nvMolKit.
5. GPU outputs synchronize before host reads and are converted to schema-checked, finite typed results.
6. A visualization builder creates the chart or 3D payload.
7. Nemotron receives only a compact JSON-safe result summary and returns a bounded interpretation.
8. The backend atomically promotes the successful chat response and visualization. A failure promotes neither partial result.

Nemotron never receives credentials, tensors, full similarity matrices, coordinates, RDKit molecule objects, or raw GPU objects.

## 6. Visualization contract

Every graph must have a descriptive title, labeled X and Y axes, explicit units or “unitless,” a legend or color scale when applicable, and accessible hover text. Payload validation rejects a graph that omits required labels.

| Result | Required visualization contract |
| --- | --- |
| Morgan fingerprint density | Histogram titled “Morgan fingerprint density”; X: “Active Morgan fingerprint bits per molecule”; Y: “Molecule count.” |
| Pairwise similarity | Heatmap with both axes labeled “Molecule index — bundled ChEMBL set”; color scale “Tanimoto similarity — unitless, 0 to 1”; hover includes both ChEMBL IDs and exact value. |
| Cluster distribution | Bar chart; X: “Cluster ID”; Y: “Molecule count”; hover includes cluster size and representative ChEMBL ID. |
| Conformer embedding | Bar chart; X: “Molecule ID”; Y: “Generated conformers”; hover includes requested and generated counts. |
| MMFF94 optimization | Energy chart; X: “Conformer ID”; Y: “Relative MMFF94 energy (kcal/mol)”; convergence state is visible and accessible. |
| Interactive conformer | Molecule/conformer selector, atom legend, rendering-style controls, and labeled XYZ orientation triad with ångström coordinate context. |

The interface must state that fingerprint similarity and clustering are structural computations, while ETKDGv3/MMFF94 outputs are sampled force-field conformers rather than experimental or globally optimal structures.

## 7. Failure behavior

- **Missing or rejected API key:** show a masked authentication error and run no analysis.
- **Unsupported free-form request:** describe the bounded capabilities and offer working prompt actions.
- **Invalid Nemotron call:** reject before execution with no partial workflow promotion.
- **CUDA, GPU, or nvMolKit failure:** show runtime-readiness failure; do not silently substitute RDKit.
- **Invalid dimensions or non-finite values:** reject the result and visualization.
- **Partial conformer failure:** identify affected records and distinguish partial generation or non-convergence from success.
- **Session expiry:** clear all session data and require key re-entry.
- **Logging:** use structured, redacted events with no prompt bodies by default and no credentials under any mode.

## 8. Repository structure

```text
nvmolkit-nemotron-chat/
├── frontend/
├── backend/
│   ├── api/
│   ├── agent/
│   ├── chemistry/
│   └── visualization/
├── data/
├── deployment/
│   ├── Dockerfile
│   ├── compose.yaml
│   └── launchable-fields.md
├── docs/
├── tests/
├── LICENSE
└── README.md
```

The implementation should keep modules small and explicit: session state, model selection, scientific execution, visualization serialization, and transport must not be collapsed into a single application file.

## 9. Packaging and Brev configuration

- Use a multi-stage Docker build: compile the React frontend, then serve the static assets and FastAPI API from one GPU-enabled application container.
- Use Docker Compose as the Brev runtime contract with one application service, one GPU reservation, one health check, and application port `8000`.
- Begin dependency validation from CPython 3.12, `torch==2.7.1+cu128`, and `nvmolkit==0.5.0`, matching the source notebook. Pin the accepted container base by immutable digest after compatibility testing.
- Require Linux x86-64, one compatible NVIDIA GPU, and at least 50 GiB disk.
- Configure a Secure Link for port `8000`, no public TCP/UDP exposure, and “Anyone with the link” Launchable access.
- Use the exact accepted public-repository commit as Launchable source.
- Provide `/api/health` for application/process readiness and a distinct GPU preflight for CUDA, PyTorch, and nvMolKit readiness.
- Make no restart-survival claim until a stop/start test proves it.
- Put no API key in repository files, Compose defaults, Launchable defaults, image history, logs, screenshots, or evidence bundles.

The repository supplies exact Console field instructions. Launchable definition creation remains a Brev Console action unless a supported, callable, authenticated authoring interface is verified at execution time. The installed CLI may deploy an existing Launchable, but its `create` command is not treated as a Launchable-authoring interface.

## 10. Verification

### 10.1 Local gates

- Backend unit tests for prompt routing, tool schemas, parameter bounds, dependency ordering, caching, session expiry, atomic promotion, and redaction.
- Visualization contract tests for title, axes, units, color scales or legends, hover metadata, dimensional consistency, and finite values.
- Frontend tests for key entry, prompt actions, free-form input, loading and error states, adaptive viewer switching, retained prior visual after failure, and stacked responsive layout.
- Integration tests with mocked Nemotron responses and deterministic scientific fixtures.
- Static type checks, linting, production frontend build, and container configuration validation.
- Targeted repository and image-history secret scans with zero confirmed credentials.

### 10.2 GPU and hosted-inference gates

- Prove CUDA availability and record GPU, driver, PyTorch, CUDA runtime, and nvMolKit identities.
- Execute all four suggested prompts against the bundled dataset.
- Assert the expected visualization kind and full labeling contract for every prompt.
- Verify a supported free-form request and a safe unsupported request.
- Verify hosted Nemotron interpretation uses the computed summary and makes no unsupported scientific claim.

### 10.3 Fresh Brev demo qualification

- Obtain a separate bounded authorization naming the organization, exact task and instance name, provider/SKU allowlist, maximum hourly price, total budget, one-instance concurrency, provisioning-attempt limit, allowed inference requests, lifecycle permission, idle timeout, expiry, artifact retention, and stop-after-test behavior.
- Create or deploy exactly one task-owned instance only within that contract.
- Record the exact organization, Launchable ID, instance ID, provider, SKU, repository commit, container digest, and Secure Link.
- Enter a dedicated limited-scope API key through the app without recording it.
- Run the complete GPU and hosted-inference acceptance sequence through the Secure Link.
- Retain a concise, redacted acceptance receipt and targeted secret-scan result.
- Stop the instance after qualification; deletion requires separate explicit authority unless included in the bounded contract.

## 11. Acceptance boundary

The project is **demo-ready** only when the fresh Brev deployment, all four deterministic prompt workflows, adaptive visualizations, hosted interpretation, redaction checks, and teardown path pass against exact recorded identities.

Demo-ready does not mean production-ready, exhaustively scientifically validated, benchmarked, secure for regulated data, or suitable for medical or experimental decision-making. Release-ready hardening remains outside this scope.

## 12. Public references

- Source launchable: https://github.com/ktretina/nvmolkit-brev-notebook
- NVIDIA nvMolKit repository: https://github.com/NVIDIA-BioNeMo/nvMolKit
- NVIDIA nvMolKit documentation: https://nvidia-bionemo.github.io/nvMolKit/
- NVIDIA Brev Launchables documentation: https://docs.nvidia.com/brev/concepts/launchables
