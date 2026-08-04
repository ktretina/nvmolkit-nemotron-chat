# Demo readiness receipt

## Status

- Receipt type: non-billable local release preparation
- Verification window: `2026-08-04T20:38:59Z` through `2026-08-04T20:43:12Z`
- Branch: `codex/implement-nvmolkit-chat`
- Verified commit: `6e7ab6c8e8f990c470321412290830ca6234ace2`
- Accepted public source commit: `d10855402f94eebb8811f107ff8dc4f7118312bf`
- Local host: macOS (`Darwin`), `arm64`
- Proof status: local functional tests, frontend typecheck/build, Compose parsing, Python byte-compilation, Ruff, targeted secret scans, and public repository publication passed. A repository-wide ad hoc mypy run did not pass, so this receipt does not assert a clean comprehensive Python typecheck. All container, GPU, hosted-service, Brev, and browser gates remain `not_run`.

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

## GitHub publication

Publication state: **PASS**. GitHub reports the repository was created at `2026-08-04T20:51:07Z` and first pushed at `2026-08-04T20:51:25Z`. A fresh readback at `2026-08-04T20:52:00Z` established:

- Repository: `https://github.com/ktretina/nvmolkit-nemotron-chat`.
- Visibility: `PUBLIC`.
- Default branch: `main`.
- `git ls-remote --heads origin main`: `d10855402f94eebb8811f107ff8dc4f7118312bf`.
- Local `main` tracks `origin/main` at that same commit.

The publication transition was bounded and did not retry creation:

1. `gh repo create ktretina/nvmolkit-nemotron-chat --public --source=. --remote=origin --push` created the public repository, but its SSH push failed with `Permission denied (publickey)`.
2. Creation was not retried. Readback showed the existing repository was `PUBLIC` with no default branch because it was still empty.
3. Only this new repository's `origin` was changed to `https://github.com/ktretina/nvmolkit-nemotron-chat.git`.
4. `git push -u origin main` succeeded.
5. Final `gh repo view` readback reported `PUBLIC` with default branch `main`, and `git ls-remote` matched the accepted commit above.

Commit `d10855402f94eebb8811f107ff8dc4f7118312bf` is the accepted public application source. The commit that adds this publication update is intentionally subsequent and is not asserted here to be pushed. No merge, push, or remote mutation was performed while writing this update.

## Unrun qualification gates

| Gate | Status | Boundary |
| --- | --- | --- |
| Docker image build | `not_run` | No Linux x86-64 image was built in this local gate. |
| Container-history secret scan | `not_run` | Requires a successfully built target image. |
| GPU/nvMolKit acceptance | `not_run` | `RUN_GPU_TESTS=1` was not set; no CUDA hardware was used. |
| Base-image digest pin verification | `not_run` | The Dockerfile's human-readable base tags were not resolved or pinned. |
| Hosted Nemotron | `not_run` | No API key was entered and no hosted request was made. |
| Brev Launchable authoring | `not_run` | No Brev command or Console mutation was performed. |
| Brev deployment and exact hardware readback | `not_run` | No bounded Brev contract was obtained or consumed. |
| Secure Link | `not_run` | No deployment existed. |
| Browser/live demo workflow | `not_run` | Suggested prompts, free-form request, unsupported request, figure retention, axes, hover, and 3D interaction were not live-qualified. |
| Container digest recording | `not_run` | No built or deployed container digest exists. |

## Release conclusion

The application source is published in a public repository with exact commit readback, but it is not yet demo-qualified. The comprehensive ad hoc mypy audit is unresolved, and every target-container, GPU, hosted Nemotron, Launchable, Secure Link, and browser acceptance gate remains `not_run`.
