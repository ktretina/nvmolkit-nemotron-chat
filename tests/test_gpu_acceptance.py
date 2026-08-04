"""Opt-in acceptance gate for the real nvMolKit CUDA runtime."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.chemistry import AnalysisEngine, NvMolKitRuntime
from app.models import AnalysisKind
from app.visualizations import (
    build_cluster_chart,
    build_conformer_bundle,
    build_fingerprint_histogram,
    build_similarity_heatmap,
    require_finite,
)


_BUILDERS = {
    AnalysisKind.FINGERPRINT_DENSITY: build_fingerprint_histogram,
    AnalysisKind.SIMILARITY: build_similarity_heatmap,
    AnalysisKind.CLUSTERS: build_cluster_chart,
    AnalysisKind.CONFORMERS: build_conformer_bundle,
}


@pytest.fixture
def live_engine() -> AnalysisEngine:
    data_path = Path(__file__).resolve().parents[1] / "data" / "sample_molecules.csv"
    runtime = NvMolKitRuntime(data_path)
    assert type(runtime) is NvMolKitRuntime
    return AnalysisEngine(runtime)


@pytest.mark.skipif(
    os.getenv("RUN_GPU_TESTS") != "1",
    reason="requires explicit GPU acceptance",
)
def test_all_four_analyses_on_cuda(live_engine: AnalysisEngine) -> None:
    import nvmolkit
    import torch

    assert nvmolkit.__version__ == "0.5.0"
    assert torch.__version__ == "2.7.1+cu128"
    assert torch.cuda.is_available()

    for kind in AnalysisKind:
        result = live_engine.run(kind, {})
        assert result.kind is kind
        require_finite(result.model_dump(mode="json"))

        visualization = _BUILDERS[kind](result.artifact)
        assert visualization["kind"] == kind.value
        require_finite(visualization)
