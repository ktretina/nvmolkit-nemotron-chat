# nvMolKit Nemotron Chat

A minimal molecular-analysis chat application intended to combine a React interface, a FastAPI backend, a bounded hosted Nemotron interaction layer, and deterministic RDKit/nvMolKit workflows.

This is an independent repository, not a continuation or fork of [`ktretina/nvmolkit-brev-notebook`](https://github.com/ktretina/nvmolkit-brev-notebook), which is kept read-only for this project and session. It adapts that project's sample molecule CSV with explicit provenance; see [`data/PROVENANCE.md`](data/PROVENANCE.md).

The current design is recorded in [`docs/superpowers/specs/2026-08-04-nvmolkit-nemotron-chat-design.md`](docs/superpowers/specs/2026-08-04-nvmolkit-nemotron-chat-design.md). The intended scope is a small Brev-oriented demo, not a general-purpose chemistry platform.

Implementation status: provenance, sample data, and minimal Python package metadata/configuration are established. The application, container runtime, and deployment are not yet implemented or validated.
