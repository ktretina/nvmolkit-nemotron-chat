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

## Deliberately unrun gates

| Gate | Status | Boundary |
| --- | --- | --- |
| Branch push or pull request | `not_run` | Task 9 requires a new explicit external-write approval. |
| Publish workflow dispatch | `not_run` | No GitHub Actions run was requested. |
| Linux x86-64 image build | `not_run` | The local gate did not build the target image. |
| Image digest and container-history scan | `not_run` | No candidate image exists for this repair. |
| GPU/nvMolKit runtime test | `not_run` | The one GPU test remained explicitly skipped; no CUDA hardware was used. |
| Live hosted Nemotron request | `not_run` | No API key was supplied to the repaired candidate. |
| Live Secure Link/browser acceptance | `not_run` | Local intercepted browser tests are not a substitute for a deployed service. |
| Brev instance inspection or modification | `not_run` | No Brev CLI, SSH, Console, or instance action was performed. |
| Launchable update | `not_run` | No Launchable field was read or changed. |
| Fresh Brev deployment | `not_run` | Publication and Launchable phases require separate approval and evidence. |

## Local conclusion

Tasks 0-8 pass their local acceptance criteria at the implementation candidate above. This is not a release, GPU-runtime, hosted-provider, or fresh-deployment qualification. Work stops at the planned approval boundary before Task 9.
