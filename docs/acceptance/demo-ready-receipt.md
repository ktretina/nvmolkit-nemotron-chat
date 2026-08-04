# Demo readiness receipt

## Status

- Receipt type: non-billable local release preparation
- Verification window: `2026-08-04T20:38:59Z` through `2026-08-04T20:43:12Z`
- Branch: `codex/implement-nvmolkit-chat`
- Verified commit: `6e7ab6c8e8f990c470321412290830ca6234ace2`
- Local host: macOS (`Darwin`), `arm64`
- Proof status: local functional tests, frontend typecheck/build, Compose parsing, Python byte-compilation, Ruff, and targeted secret scans passed. A repository-wide ad hoc mypy run did not pass, so this receipt does not assert a clean comprehensive Python typecheck. All container, GPU, hosted-service, Brev, and browser gates remain `not_run`.

This receipt contains no API key, raw credential-bearing request, hosted response, or Brev state. No billable or shared Brev command was run.

## Architecture under test

The repository packages one React/Vite frontend and one FastAPI backend into a single Docker Compose application service on port 8000. The backend holds ephemeral in-memory sessions, exposes four bounded deterministic nvMolKit analysis workflows over the bundled 256-row molecule CSV, and returns validated Plotly or 3Dmol.js payloads. Hosted Nemotron is limited to selecting or interpreting those predefined workflows; it is not the source of the computed molecular artifacts.

The local host is Apple ARM64. The target image and nvMolKit wheels are Linux x86-64 GPU artifacts, so the local checks below do not qualify the target runtime.

## Local gate evidence

All commands were run from the repository root using the clean implementation worktree unless stated otherwise.

| Gate | Exact command | Result |
| --- | --- | --- |
| Identity | `git rev-parse --verify HEAD` and `git branch --show-current` | `6e7ab6c8e8f990c470321412290830ca6234ace2` on `codex/implement-nvmolkit-chat` |
| Backend tests | `PYTHONPATH=backend backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra` | PASS: 172 collected, 171 passed, 1 skipped. The GPU file was collected and skipped by its explicit `RUN_GPU_TESTS=1` guard; it was not deselected by the marker expression. |
| Frontend tests | `npm --prefix frontend test -- --run` | PASS: 2 files, 19 tests |
| Frontend typecheck | `npm --prefix frontend run typecheck` | PASS |
| Frontend production build | `npm --prefix frontend run build` | PASS: 22 modules transformed. Vite also emitted dependency warnings for direct `eval` inside 3Dmol.js and a 5.43 MB chunk; these were warnings, not failures. |
| Compose parse | `docker compose -f deployment/compose.yaml config --quiet` | PASS with Docker Compose `v5.1.3` |
| Python compile | `backend/.venv/bin/python -m compileall -q backend/app tests` | PASS |
| Ruff | `ruff check backend/app tests` | PASS with Ruff `0.15.0` |
| Scoped mypy | `PYTHONPATH=backend backend/.venv/bin/python -m mypy backend/app/main.py` | PASS with mypy `2.3.0` |
| Repository-wide mypy audit | `PYTHONPATH=backend backend/.venv/bin/python -m mypy backend/app tests` | FAIL: 59 errors across 6 files. The repository has no checked-in mypy configuration. Findings include missing third-party stubs/modules in this non-GPU environment and real annotation mismatches in visualization, session, and test code. |
| Tracked-content secret scan | `git grep` for an NVIDIA key-shaped token or an API-key environment assignment outside design documents, with results counted rather than printed | PASS after fixture review: 0 non-fixture matching files and 0 assignment matches. Two test files contain deliberately synthetic key-shaped fixtures. |
| Git-history secret scan | Each commit from `git rev-list --all` scanned with `git grep` for the same patterns, with results counted rather than printed | PASS after fixture review: 0 non-fixture matches. Only the same synthetic fixture paths appeared. |
| Worktree state before receipt edits | `git status --short` | PASS: no changes |

Tool identities recorded during the gate: CPython `3.12.12`, Node.js `v25.6.1`, npm `11.9.0`, Docker `29.4.2`, Docker Compose `v5.1.3`, GitHub CLI `2.95.0`.

## Source-project isolation

The source notebook repository was inspected read-only at `/Users/ktretina/Desktop/BioNeMo Platform Meta Skill/projects/nvmolkit-brev-notebook`.

- Current local source HEAD: `c3f7a822720e10ed93269bfe6209386911762f39`.
- Accepted data provenance commit: `dd27240e67dfe906412258dd6fafd2262eebd26e`.
- Tracked source working tree: clean.
- Untracked source state: pre-existing `.DS_Store` only.
- The accepted source CSV and this repository's bundled CSV both have SHA-256 `7063a5d8eded837e3e648c44894fbe742d5863a0929bb5765b1c6330722fb034`.

No source-repository file or ref was changed by this release-preparation task. The local source HEAD contains later documentation commits, but the bundled data remains pinned byte-for-byte to the accepted provenance commit.

## GitHub and publication preflight

Read-only checks established:

- `gh auth status --hostname github.com`: authenticated as `ktretina`; credential output remained masked.
- `gh repo view ktretina/nvmolkit-nemotron-chat --json nameWithOwner,visibility,url,defaultBranchRef`: repository not found, so the intended public destination was absent at verification time.
- `git remote -v`: no remote configured.
- `git rev-list --left-right --count main...HEAD`: `0 20` before this receipt commit. The implementation branch was a strict descendant of clean local `main` at merge base `5d042f2d2e2c5b700a872ba629281fd94709cbb7`.

Recommended safe publication sequence:

1. Decide whether the repository-wide mypy findings are a release blocker; fix them or explicitly define and check a supported mypy scope.
2. Re-run the complete local gate and independently review the implementation plus this receipt.
3. Fast-forward clean local `main` to the reviewed implementation branch; do not rewrite either history.
4. Create `ktretina/nvmolkit-nemotron-chat` as a public repository from the accepted local `main`, push once, then read back visibility, default branch, and exact commit.
5. Only after publication, obtain the separately approved bounded Brev contract and perform the Launchable/live qualification steps. Do not infer that authorization from this local receipt.

## Unrun qualification gates

| Gate | Status | Boundary |
| --- | --- | --- |
| Docker image build | `not_run` | No Linux x86-64 image was built in this local gate. |
| Container-history secret scan | `not_run` | Requires a successfully built target image. |
| GPU/nvMolKit acceptance | `not_run` | `RUN_GPU_TESTS=1` was not set; no CUDA hardware was used. |
| Base-image digest pin verification | `not_run` | The Dockerfile's human-readable base tags were not resolved or pinned. |
| Hosted Nemotron | `not_run` | No API key was entered and no hosted request was made. |
| Public GitHub repository creation/push | `not_run` | Destination was confirmed absent; no remote mutation was authorized for this subtask. |
| Brev Launchable authoring | `not_run` | No Brev command or Console mutation was performed. |
| Brev deployment and exact hardware readback | `not_run` | No bounded Brev contract was obtained or consumed. |
| Secure Link | `not_run` | No deployment existed. |
| Browser/live demo workflow | `not_run` | Suggested prompts, free-form request, unsupported request, figure retention, axes, hover, and 3D interaction were not live-qualified. |
| Container digest recording | `not_run` | No built or deployed container digest exists. |

## Release conclusion

The repository has fresh local functional evidence, but it is not yet demo-qualified. The comprehensive ad hoc mypy audit is unresolved, and every target-container, GPU, hosted Nemotron, public-repository, Launchable, Secure Link, and browser acceptance gate remains `not_run`.
