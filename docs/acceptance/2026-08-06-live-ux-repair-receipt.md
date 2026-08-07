# Live UX repair acceptance receipt

## Status

- Receipt type: cumulative local, publication, existing-instance GPU, and targeted Secure Link acceptance.
- Local verification window: `2026-08-06T19:19:06Z` through `2026-08-06T19:22:26Z`.
- Existing-instance qualification window: `2026-08-07T12:28:48Z` through `2026-08-07T12:47:51Z`.
- Branch: `codex/fix-live-nvmolkit-ux-20260806`.
- Accepted implementation candidate: `287e907ded4ba68e6c5db829da9e6e07357f60bb`.
- Base commit: `e879390` (`main` and `origin/main` at the time of this receipt).
- Local host: macOS, Apple arm64.
- Scope result: **PASS** for the local backend, frontend unit, frontend type, frontend production-build, Chromium UI, Compose parsing, byte-compilation, repository-diff, and credential-scan gates described below.
- External-write boundary: no branch was pushed, no workflow was dispatched, no image was built or published, and no Brev resource or Launchable was read or modified during Tasks 0-8.
- Latest publication result: **PASS** for browser-gated GitHub Actions run `31137134719` and immutable registry readback from the accepted similarity-readability commit.
- Existing-instance result: **PASS** for immutable-image startup, CUDA/nvMolKit readiness, all four deterministic GPU analyses, and the targeted Secure Link similarity-heatmap check. Full nine-step browser acceptance, Launchable correction, and fresh-deployment qualification remain pending.

This receipt contains no NVIDIA API key or raw credential-bearing request. Local browser tests use intercepted API responses; the separately identified Secure Link evidence comes from the live existing instance.

## Accepted behavior

The local candidate implements and tests the following behavior:

- `New analysis` clears the active analysis and figure while preserving the in-memory authenticated session and API key.
- `End session` deletes that session and returns the application to the API-key gate.
- Backend provider failures are classified into a bounded, safe status contract; raw hosted-provider response text is not sent to the browser.
- Deterministic suggested workflows retain their computed figures when optional Nemotron interpretation is unavailable.
- Free-form requests fail closed when routing is unavailable and do not execute an unselected chemistry workflow.
- The composer remains available after authentication and supports consecutive tasks.
- Molecule and conformer selectors are populated for 3D results, rendering style changes are selectable, and selectors are absent from non-3D results.
- The desktop layout keeps the composer and result in the bounded viewport with independently scrollable panes; the mobile layout remains usable.
- One 3D canvas is retained across 3D-to-2D-to-3D transitions instead of accumulating hidden viewers.

## Tool identities

| Tool | Version |
| --- | --- |
| CPython | `3.12.12` |
| Node.js | `v24.18.0` |
| npm | `11.16.0` |
| Playwright | `1.62.1` |
| Docker Engine client | `29.4.2`, build `055a478` |
| Docker Compose | `v5.1.3` |
| Gitleaks | `8.30.1` |

Node.js was selected explicitly from `/Users/ktretina/.nvm/versions/node/v24.18.0/bin` because the machine's default Node.js 25 release is outside jsdom's supported range. Chromium `1234` for Playwright 1.62.1 was installed in the isolated local cache `/private/tmp/codex-playwright-1.62.1`.

## Local gate evidence

All commands were run from the repository root. `PATH` began with `/Users/ktretina/.nvm/versions/node/v24.18.0/bin` for frontend commands; the E2E command also set `PLAYWRIGHT_BROWSERS_PATH=/private/tmp/codex-playwright-1.62.1`.

| Gate | Exact command | Result |
| --- | --- | --- |
| Source identity | `git rev-parse HEAD` | PASS: `03d5b5464bc444666e3ef2f3ba955ccf02668b1f` on `codex/fix-live-nvmolkit-ux-20260806` before this receipt-only commit. |
| Backend tests | `backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra` | PASS: 239 passed and 1 explicitly skipped GPU test in 1.69 seconds. |
| Python byte-compilation | `backend/.venv/bin/python -m compileall -q backend/app tests` | PASS. |
| Frontend unit/component tests | `npm --prefix frontend test -- --run` | PASS: 2 files and 22 tests. |
| Frontend typecheck | `npm --prefix frontend run typecheck` | PASS. |
| Frontend production build | `npm --prefix frontend run build` | PASS. Vite emitted existing upstream warnings for direct `eval` in 3Dmol.js and a large output chunk; neither was a build failure. |
| Chromium UI acceptance | `npm --prefix frontend run test:e2e` | PASS: 3 tests in 4.7 seconds, including the production build executed by the script. |
| Compose parse | `docker compose -f deployment/compose.yaml config --quiet` | PASS. |
| Repository diff | `git diff --check` | PASS. |
| Repository state | `git status --short --branch` | PASS: clean feature branch before creating this receipt. |
| Full-history secret scan | `/opt/homebrew/bin/gitleaks git --redact --no-banner --no-color --report-format json --report-path /private/tmp/nvmolkit-gitleaks.json .` | PASS: 61 commits and approximately 660 KB scanned; 0 leaks found and 0 JSON findings. |

### Chromium coverage

The three acceptance tests run in real Chromium against a Vite production preview with mocked, non-secret API traffic:

1. At `1563x1103`, the composer and a generated 2D similarity figure are in the viewport, the document does not acquire page-level scrolling, and the inactive conformer pane is hidden.
2. At `1563x1103`, a two-molecule 3D response populates molecule and conformer options; the style selector changes; the energy plot and 3D canvas render; the same canvas survives 3D-to-2D-to-3D transitions; `New analysis` retains authentication; and `End session` returns to the key gate.
3. At `390x844`, the composer is initially visible and the scientific-viewer region can scroll to a rendered 2D result without exposing 3D selectors.

### Credential-scan accounting

In addition to the redacted Gitleaks scan, count-only NVIDIA-key-shape scans were run without printing values:

- Tracked files: 1 matching token occurrence/path.
- Reachable-history commit/path matches: 46.
- Unique matching values across all reachable history: 1.
- Generated `frontend/dist` matches: 0.
- NVIDIA API-key assignment matches: 0.

Path-only and exact-fixture checks established that every nonzero shape match is the single synthetic test fixture `nvapi-secret-that-must-never-leak` in `tests/test_api.py`, repeated through its commit history. Confirmed credentials: **0**. Gitleaks independently reported zero findings. No matching value was printed during the scans.

## Phase A publication and registry evidence

The reviewed branch `codex/fix-live-nvmolkit-ux-20260806` was pushed at exact source commit `7b82e3722075acad4868896716c1eb66ac642f65`. Exactly one manual publication workflow was dispatched. GitHub Actions run [`31126921793`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31126921793) ran from `2026-08-06T19:30:05Z` through `2026-08-06T19:39:24Z` and concluded `success`. Its `verify` job passed backend tests, frontend units, typechecking, the production build, Chromium installation, and all three production browser tests before the `publish` job could run.

| Evidence | Result |
| --- | --- |
| Source commit | `7b82e3722075acad4868896716c1eb66ac642f65` |
| Workflow | `31126921793`, attempt 1, `success` |
| OCI index | `sha256:1911d4eae820fad11b5aac8634fefcc69557ace82194870e2711896c134d2a08` |
| Linux/amd64 manifest | `sha256:7141d8c9cba22b473a064846f30f865bed3840a0b53bc386472d8bdb41cc05de` |
| Attestation manifest | `sha256:b027d539f078988c21a2b8003462ec86e8d97d70315aa3fa06898c025eb9deb9` |
| Compressed Linux/amd64 layers | 12 layers; 4,201,723,821 bytes (3.9131602468 GiB) |
| Image configuration | Linux/amd64; non-root user `app`; working directory `/app/backend`; port `8000/tcp`; Uvicorn command on `0.0.0.0:8000`; no `NVIDIA_API_KEY` environment entry |
| Provenance | SLSA provenance binds run attempt 1, source repository, source commit, Linux/amd64 manifest, and the resolved Node and Python base-image indexes |

Registry inspection was read-only and did not pull or execute the 3.913 GiB image. The four small application/build layers containing the backend application, bundled data, built frontend, and final ownership metadata were streamed directly from GHCR and scanned with redacted Gitleaks: 0 findings across approximately 11.1 MB. NVIDIA-key-shaped value counts were 0 in those layers, the image configuration/history, and the provenance payload.

Redacted Gitleaks reported two `generic-api-key` findings in image configuration/history and three in provenance, all with field context `GPG_KEY=<redacted>`. A value-equality check established that the candidate's field exactly matches the resolved official Python Linux/amd64 base image. It is an inherited public signing-key fingerprint, not an application or NVIDIA credential. Confirmed image credentials: **0**.

This phase establishes build and registry identity only. It does not establish that the image starts, can see CUDA, imports nvMolKit on an L4, produces valid scientific outputs on the target runtime, reaches hosted Nemotron, or works through a Brev Secure Link.

## Phase B local deployment metadata

Local commit `80157583aeb19e6b20f4bb259336806d9a2e3fc1` is the immutable Compose anchor for the corrected OCI index. Its only Compose change replaces the prior image reference with `ghcr.io/ktretina/nvmolkit-nemotron-chat@sha256:1911d4eae820fad11b5aac8634fefcc69557ace82194870e2711896c134d2a08`; `TRITON_CACHE_DIR`, port `8000`, the single NVIDIA GPU reservation, and the health check are unchanged.

After a separate push approval and exact remote readback, the intended immutable Compose resource is `https://github.com/ktretina/nvmolkit-nemotron-chat/blob/80157583aeb19e6b20f4bb259336806d9a2e3fc1/deployment/compose.yaml`. Until that readback succeeds, the URL is a local handoff target rather than confirmed remote state. The accompanying Launchable metadata requires Linux/amd64, exactly one NVIDIA L4, 50 GiB storage, a Secure Link on port 8000, and no public TCP or UDP ports. It defines no Launchable or Compose API-key default.

This local metadata update did not call Brev, inspect an instance, authenticate, refresh shared credentials, edit a Console Launchable, create a deployment, or incur cloud cost.

## Phase C similarity-readability publication and existing-instance qualification

Commit `287e907ded4ba68e6c5db829da9e6e07357f60bb` adds the approved sparse-axis and compact-colorbar repair without changing the 256 by 256 similarity matrix, molecule ordering, hover fidelity, or scientific claim boundary. GitHub Actions run [`31137134719`](https://github.com/ktretina/nvmolkit-nemotron-chat/actions/runs/31137134719) completed successfully and published OCI index `sha256:278d4dacdedfae6c05d7effb28fa9c1d745262424a88e85696c363e17bba0afe`; its Linux/amd64 manifest is `sha256:756654333de037ab093cc6e12063469a9cdea8f32ae6ce1f388fd53246f753d9`.

### Existing Brev instance identity and rollback

The accepted target was organization `agents-in-ls`, instance `nvmolkit-nemotron-chat-72c7f3` (`he8b2ekuh`), Compose project `workspace`, service `app`, container `workspace-app-1`, and port `8000`. The instance remained `RUNNING`, shell `READY`, and health `HEALTHY` on one NVIDIA L4 throughout the replacement.

Before replacement, `/home/ubuntu/workspace/docker-compose.yaml` was copied to `/home/ubuntu/workspace/docker-compose.pre-287e907.yaml`; both had SHA-256 `e25400c9b05b4c56858fe0b5d2f79c8b76ca95d717fe10464002305069f62f29`. The staged replacement Compose had SHA-256 `f5e35fd7633129e7a1f8dab00a6c712413fa14b2f6fdf84f5eeb7d4aaf9caba0`, passed `docker compose config --quiet`, and differed from the rollback file only in the image digest. Only service `app` was force-recreated. The prior Compose backup and prior image remain available for rollback; no instance lifecycle, Launchable, unrelated service, or broad Docker-cleanup action was performed.

### Runtime and real GPU acceptance

The recreated container was `1f07b655dac986a7996ec211c1c868bdeea042c925d5cb70db8c52b5a3c8eabb`, ran as image user `app` (UID `10001`), exposed host port `8000`, and resolved the exact OCI index above with Compose image label `sha256:756654333de037ab093cc6e12063469a9cdea8f32ae6ce1f388fd53246f753d9`. It reported `running|healthy`, zero restarts, and start time `2026-08-07T12:34:26.447949163Z`.

`GET http://127.0.0.1:8000/api/health` returned process ready, dependency ready, and positive CUDA, PyTorch, and nvMolKit checks before and after GPU acceptance. Host GPU identity was `NVIDIA L4`, UUID `GPU-f3bcc9e5-ad0a-02f2-be68-0f2be40c9b08`. Inside the exact container, PyTorch `2.7.1+cu128`, nvMolKit `0.5.0`, CUDA availability, and device name `NVIDIA L4` were read back successfully.

The packaged equivalent of `tests/test_gpu_acceptance.py` ran inside that immutable container and passed every `AnalysisKind`: `fingerprint_density`, `similarity`, `clusters`, and `conformers`. Each result and its visualization payload passed the repository's finite-value validator. The temporary test copies were removed after the run. A count-only scan of container logs from the qualification window found zero lines matching `traceback|exception|error|fatal` and zero lines containing `nvapi-`; no log value or credential was captured in this receipt.

### Targeted Secure Link browser evidence

At `2026-08-07T12:47:51Z`, the user confirmed the live similarity result through the Secure Link and supplied screenshot `Screenshot 2026-08-07 at 8.47.51 AM.png`. The screenshot establishes:

- the `analyze_similarity_map` workflow completed and the workspace returned to `Ready`;
- the 256 by 256 heatmap was visible as a square matrix;
- each axis showed the intended eight sparse ChEMBL IDs without static overlap;
- the compact `Tanimoto similarity` colorbar sat immediately beside the matrix with visible `0`, `0.5`, and `1` ticks;
- full row ID, column ID, and similarity value remained available in hover detail;
- the composer remained visible after the analysis; and
- a substantive similarity interpretation was visible with no provider error shown.

This is targeted acceptance of the repaired similarity presentation on the existing instance. It is not evidence that all four figures, conformer interactions, free-form Nemotron routing, unsupported-request handling, `New analysis`, and `End session` were re-run on this image in one browser session.

## Remaining and deliberately unrun gates

| Gate | Status | Boundary |
| --- | --- | --- |
| Pull request or default-branch merge | `not_run` | Only the reviewed feature branch was pushed. |
| Latest digest-pinned metadata commit/push | `not_run` | The local Compose and handoff update require separate review and approval. |
| Full live hosted Nemotron qualification | `partial` | A suggested similarity interpretation was visible; free-form routing and safe unsupported-request behavior were not re-run. |
| Full Secure Link/browser acceptance | `partial` | The repaired similarity view passed; the complete nine-step flow was not re-run on this image. |
| Brev Launchable definition update | `not_run` | Local handoff metadata are not a Console or platform mutation. |
| Fresh Brev deployment | `not_run` | Publication and Launchable phases require separate approval and evidence. |

## Local conclusion

The similarity-readability artifact passes local tests, immutable publication, existing-instance L4 runtime/GPU acceptance, and the targeted live Secure Link presentation check. The existing instance is therefore accepted for the recorded scope. The repository metadata update remains local, the Launchable definition has not been changed, the complete nine-step browser flow remains partial, and no fresh Launchable deployment has been qualified.
