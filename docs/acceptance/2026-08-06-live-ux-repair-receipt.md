# Live UX repair local acceptance receipt

## Status

- Receipt type: local-only acceptance for Tasks 0-8 of the live UX repair plan.
- Verification window: `2026-08-06T19:19:06Z` through `2026-08-06T19:22:26Z`.
- Branch: `codex/fix-live-nvmolkit-ux-20260806`.
- Accepted implementation candidate: `03d5b5464bc444666e3ef2f3ba955ccf02668b1f`.
- Base commit: `e879390` (`main` and `origin/main` at the time of this receipt).
- Local host: macOS, Apple arm64.
- Scope result: **PASS** for the local backend, frontend unit, frontend type, frontend production-build, Chromium UI, Compose parsing, byte-compilation, repository-diff, and credential-scan gates described below.
- External-write boundary: no branch was pushed, no workflow was dispatched, no image was built or published, and no Brev resource or Launchable was read or modified during Tasks 0-8.
- Phase A publication result: **PASS** for one browser-gated GitHub Actions run and immutable registry readback from the accepted repair commit; runtime, GPU, hosted-provider, Secure Link, and Brev gates remain pending.

This receipt contains no NVIDIA API key, raw credential-bearing request, or hosted-model response. The browser tests use intercepted local API responses and therefore establish frontend behavior, not live hosted-provider availability.

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

## Deliberately unrun gates

| Gate | Status | Boundary |
| --- | --- | --- |
| Pull request or default-branch merge | `not_run` | Only the reviewed feature branch was pushed. |
| Phase B metadata push | `not_run` | The digest-pinned Compose and handoff metadata require separate review and approval. |
| GPU/nvMolKit runtime test | `not_run` | The one GPU test remained explicitly skipped; no CUDA hardware was used. |
| Live hosted Nemotron request | `not_run` | No API key was supplied to the repaired candidate. |
| Live Secure Link/browser acceptance | `not_run` | Local intercepted browser tests are not a substitute for a deployed service. |
| Brev instance inspection or modification | `not_run` | No Brev CLI, SSH, Console, or instance action was performed. |
| Brev Launchable definition update | `not_run` | Local handoff metadata are not a Console or platform mutation. |
| Fresh Brev deployment | `not_run` | Publication and Launchable phases require separate approval and evidence. |

## Local conclusion

Tasks 0-8 pass their local acceptance criteria and Task 9 produced one immutable, browser-gated Linux/amd64 registry artifact from the reviewed repair commit. The artifact is not yet GPU-runtime, hosted-provider, Secure Link, or fresh-deployment qualified. Phase B metadata remains local until separately reviewed and approved for push; no Brev access or mutation has occurred.
