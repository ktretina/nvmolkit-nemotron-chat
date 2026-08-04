from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.chemistry import AnalysisEngine
from app.models import AnalysisKind, AnalysisParameters


def test_cluster_run_executes_required_stages_once(fake_runtime) -> None:
    result = AnalysisEngine(fake_runtime).run(AnalysisKind.CLUSTERS, {})

    assert fake_runtime.calls == ["load", "fingerprints", "similarity", "clusters"]
    assert result.kind is AnalysisKind.CLUSTERS


def test_similarity_then_conformers_reuses_completed_prerequisites(fake_runtime) -> None:
    engine = AnalysisEngine(fake_runtime)

    engine.run(AnalysisKind.SIMILARITY, {})
    result = engine.run(AnalysisKind.CONFORMERS, {})

    assert fake_runtime.calls == [
        "load",
        "fingerprints",
        "similarity",
        "clusters",
        "embed",
        "optimize",
    ]
    assert result.kind is AnalysisKind.CONFORMERS


def test_invalid_radius_is_rejected_before_runtime_execution(fake_runtime) -> None:
    engine = AnalysisEngine(fake_runtime)

    with pytest.raises(ValidationError, match="fingerprint_radius"):
        engine.run(AnalysisKind.SIMILARITY, {"fingerprint_radius": 9})

    assert fake_runtime.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fingerprint_radius", 1),
        ("fingerprint_size", 4096),
        ("cluster_cutoff", 0.39),
        ("cluster_cutoff", 0.61),
        ("representative_count", 2),
        ("representative_count", 7),
        ("conformers_per_molecule", 2),
        ("conformers_per_molecule", 9),
        ("unexpected", True),
    ],
)
def test_parameter_bounds_and_extra_fields_are_rejected(field, value) -> None:
    with pytest.raises(ValidationError, match=field):
        AnalysisParameters.model_validate({field: value})


@pytest.mark.parametrize(
    ("kind", "terminal_stage"),
    [
        (AnalysisKind.FINGERPRINT_DENSITY, "fingerprints"),
        (AnalysisKind.SIMILARITY, "similarity"),
        (AnalysisKind.CLUSTERS, "clusters"),
        (AnalysisKind.CONFORMERS, "optimize"),
    ],
)
def test_each_analysis_returns_its_terminal_stage_artifacts(
    fake_runtime, kind, terminal_stage
) -> None:
    result = AnalysisEngine(fake_runtime).run(kind, {})

    assert result.summary["terminal_stage"] == terminal_stage
    assert result.artifact["stage"] == terminal_stage


def test_changed_fingerprint_parameters_invalidate_all_descendants(fake_runtime) -> None:
    engine = AnalysisEngine(fake_runtime)
    engine.run(AnalysisKind.CONFORMERS, {})

    engine.run(
        AnalysisKind.CONFORMERS,
        {"fingerprint_radius": 3, "fingerprint_size": 1024},
    )

    assert fake_runtime.calls == [
        "load",
        "fingerprints",
        "similarity",
        "clusters",
        "embed",
        "optimize",
        "fingerprints",
        "similarity",
        "clusters",
        "embed",
        "optimize",
    ]


def test_changed_cluster_cutoff_reuses_compatible_ancestors(fake_runtime) -> None:
    engine = AnalysisEngine(fake_runtime)
    engine.run(AnalysisKind.CONFORMERS, {})

    engine.run(AnalysisKind.CONFORMERS, {"cluster_cutoff": 0.6})

    assert fake_runtime.calls[-3:] == ["clusters", "embed", "optimize"]
    assert fake_runtime.calls.count("fingerprints") == 1
    assert fake_runtime.calls.count("similarity") == 1


def test_changed_conformer_parameters_recompute_embedding_and_optimization(
    fake_runtime,
) -> None:
    engine = AnalysisEngine(fake_runtime)
    engine.run(AnalysisKind.CONFORMERS, {})

    engine.run(
        AnalysisKind.CONFORMERS,
        {"representative_count": 4, "conformers_per_molecule": 6},
    )

    assert fake_runtime.calls[-2:] == ["embed", "optimize"]
    assert fake_runtime.calls.count("clusters") == 1
