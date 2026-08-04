from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

import app.chemistry as chemistry
from app.chemistry import AnalysisEngine
from app.models import AnalysisKind, AnalysisParameters, AnalysisResult


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


def test_cached_results_are_deeply_isolated_from_caller_mutation(fake_runtime) -> None:
    engine = AnalysisEngine(fake_runtime)
    first = engine.run(AnalysisKind.SIMILARITY, {})
    calls = list(fake_runtime.calls)

    first.summary["nested"]["values"].append("caller-summary")
    first.artifact["nested"]["values"].append("caller-artifact")
    second = engine.run(AnalysisKind.SIMILARITY, {})

    assert fake_runtime.calls == calls
    assert second.summary["nested"]["values"] == ["similarity"]
    assert second.artifact["nested"]["values"] == ["similarity"]


def test_runtime_result_kind_must_match_terminal_stage(fake_runtime) -> None:
    def wrong_kind(state):
        return AnalysisResult(
            kind=AnalysisKind.CLUSTERS,
            summary={},
            artifact={},
        )

    fake_runtime.similarity = wrong_kind

    with pytest.raises(RuntimeError, match="similarity.*kind"):
        AnalysisEngine(fake_runtime).run(AnalysisKind.SIMILARITY, {})


class _Buffer:
    def __init__(self, values) -> None:
        self.values = np.asarray(values)

    def torch(self):
        return self.values


class _MoleculeCounts:
    def __init__(self, conformer_count: int, atom_count: int = 2) -> None:
        self.conformer_count = conformer_count
        self.atom_count = atom_count

    def GetNumConformers(self) -> int:
        return self.conformer_count

    def GetNumAtoms(self) -> int:
        return self.atom_count


def _optimization_result(
    *, energies=(1.0, 2.0), converged=(1, 0), mol_indices=(0, 0), conf_indices=(0, 1)
):
    return SimpleNamespace(
        energies=_Buffer(energies),
        converged=_Buffer(converged),
        mol_indices=_Buffer(mol_indices),
        conf_indices=_Buffer(conf_indices),
    )


def _representatives():
    return [{"molecule_id": "mol-1", "cluster_id": 0}]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"converged": (1, 0.5)}, "convergence.*exact integers"),
        ({"converged": (1, np.nan)}, "convergence.*finite"),
        ({"converged": (1, 2)}, "convergence.*binary"),
        ({"mol_indices": (0, -1)}, "molecule indices.*nonnegative"),
        ({"mol_indices": (0, 0.5)}, "molecule indices.*exact integers"),
        ({"conf_indices": (0, -1)}, "conformer indices.*nonnegative"),
        ({"conf_indices": (0, 1.5)}, "conformer indices.*exact integers"),
        ({"conf_indices": (0, 2)}, "conformer indices.*out of range"),
        ({"energies": (1.0, np.nan)}, "energies.*non-finite"),
    ],
)
def test_optimization_buffers_fail_closed_before_integer_coercion(
    monkeypatch, overrides, message
) -> None:
    monkeypatch.setattr(chemistry, "_host_array", np.asarray)
    result = _optimization_result(**overrides)

    with pytest.raises(RuntimeError, match=message):
        chemistry._optimization_records(
            result, [_MoleculeCounts(2)], _representatives()
        )


def test_optimization_pairs_must_be_complete_and_unique(monkeypatch) -> None:
    monkeypatch.setattr(chemistry, "_host_array", np.asarray)
    result = _optimization_result(conf_indices=(0, 0))

    with pytest.raises(RuntimeError, match="incomplete or duplicated"):
        chemistry._optimization_records(
            result, [_MoleculeCounts(2)], _representatives()
        )


@pytest.mark.parametrize(
    ("coordinates", "message"),
    [
        ([np.zeros((3, 3)), np.zeros((2, 3))], "wrong shape"),
        ([np.array([[0.0, 0.0, 0.0], [np.nan, 0.0, 0.0]]), np.zeros((2, 3))], "non-finite"),
    ],
)
def test_coordinate_updates_validate_shape_and_finiteness(
    monkeypatch, coordinates, message
) -> None:
    monkeypatch.setattr(chemistry, "_host_array", np.asarray)
    result = SimpleNamespace(per_molecule=lambda: [coordinates])

    with pytest.raises(RuntimeError, match=message):
        chemistry._coordinate_updates(
            result, [_MoleculeCounts(2)], [(0, 0), (0, 1)]
        )


def test_coordinate_updates_follow_authoritative_flat_pair_order(monkeypatch) -> None:
    monkeypatch.setattr(chemistry, "_host_array", np.asarray)
    first = np.full((2, 3), 1.0)
    second = np.full((2, 3), 2.0)
    result = SimpleNamespace(per_molecule=lambda: [[first, second]])

    updates = chemistry._coordinate_updates(
        result, [_MoleculeCounts(2)], [(0, 1), (0, 0)]
    )

    assert [conformer_index for _, conformer_index, _ in updates] == [1, 0]
    assert np.array_equal(updates[0][2], first)
    assert np.array_equal(updates[1][2], second)


def test_coordinate_updates_reject_duplicate_authoritative_pairs(monkeypatch) -> None:
    monkeypatch.setattr(chemistry, "_host_array", np.asarray)
    result = SimpleNamespace(
        per_molecule=lambda: [[np.zeros((2, 3)), np.zeros((2, 3))]]
    )

    with pytest.raises(RuntimeError, match="coordinate pairs"):
        chemistry._coordinate_updates(
            result, [_MoleculeCounts(2)], [(0, 0), (0, 0)]
        )


def test_fingerprint_artifact_aligns_active_bits_to_molecule_ids() -> None:
    artifact = chemistry._fingerprint_artifact(
        np.array([4, 7]), [{"id": "a"}, {"id": "b"}]
    )

    assert artifact["molecule_ids"] == ["a", "b"]
    assert artifact["active_bit_counts"] == [4, 7]
    assert len(artifact["histogram_edges"]) == len(artifact["histogram_counts"]) + 1


def test_similarity_artifact_contains_aligned_finite_matrix() -> None:
    artifact = chemistry._similarity_artifact(
        np.array([[1.0, 0.2], [0.2, 1.0]]), [{"id": "a"}, {"id": "b"}]
    )

    assert artifact == {
        "molecule_ids": ["a", "b"],
        "matrix": [[1.0, 0.2], [0.2, 1.0]],
    }


def test_cluster_artifact_contains_sizes_and_representative_ids() -> None:
    groups = [
        {"members": [{"molecule_id": "a"}]},
        {"members": [{"molecule_id": "c"}]},
    ]

    artifact = chemistry._cluster_artifact([[0, 1], [2]], groups)

    assert artifact["cluster_sizes"] == [2, 1]
    assert artifact["representative_molecule_ids"] == ["a", "c"]


def test_conformer_artifact_is_json_safe_and_renderable() -> None:
    class Atom:
        def __init__(self, index, symbol):
            self.index, self.symbol = index, symbol

        def GetIdx(self):
            return self.index

        def GetSymbol(self):
            return self.symbol

    class Bond:
        def GetBeginAtomIdx(self):
            return 0

        def GetEndAtomIdx(self):
            return 1

        def GetBondTypeAsDouble(self):
            return 1.0

    class Position:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    class Conformer:
        def __init__(self, conformer_id):
            self.conformer_id = conformer_id

        def GetAtomPosition(self, atom_index):
            return Position(float(atom_index), float(self.conformer_id), 0.0)

    class Molecule:
        def GetAtoms(self):
            return [Atom(0, "C"), Atom(1, "O")]

        def GetBonds(self):
            return [Bond()]

        def GetConformer(self, conformer_id):
            return Conformer(conformer_id)

        def GetNumAtoms(self):
            return 2


    molecule = Molecule()
    records = [
        {
            "molecule_id": "mol-1",
            "cluster_id": 0,
            "conformer_index": 0,
            "energy_kcal_mol": 4.0,
            "converged": True,
            "optimization_molecule_index": 0,
        },
        {
            "molecule_id": "mol-1",
            "cluster_id": 0,
            "conformer_index": 1,
            "energy_kcal_mol": 5.5,
            "converged": True,
            "optimization_molecule_index": 0,
        },
    ]

    selected = [{**records[0], "selected_conformer_id": "mol-1:conf-0"}]
    artifact = chemistry._conformer_artifact([molecule], records, selected)

    assert [record["relative_energy_kcal_mol"] for record in artifact["per_conformer_records"]] == [0.0, 1.5]
    assert artifact["per_conformer_records"][0]["conformer_id"] == "mol-1:conf-0"
    assert artifact["selected_conformer_records"][0]["relative_energy_kcal_mol"] == 0.0
    structure = artifact["renderable_structures"][0]
    assert structure["conformer_id"] == "mol-1:conf-0"
    assert structure["molecule_id"] == "mol-1"
    assert structure["conformer_index"] == 0
    assert structure["relative_energy_kcal_mol"] == 0.0
    assert structure["atoms"][0] == {"index": 0, "element": "C"}
    assert {"begin", "end", "order"} == set(structure["bonds"][0])
    assert len(structure["coordinates"]) == molecule.GetNumAtoms()
    import json

    json.dumps(artifact, allow_nan=False)
