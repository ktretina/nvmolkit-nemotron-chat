from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from app.visualizations import (
    build_cluster_chart,
    build_conformer_bundle,
    build_fingerprint_histogram,
    build_similarity_heatmap,
    require_finite,
)


def _layout_titles(graph):
    return (
        graph["layout"]["title"]["text"],
        graph["layout"]["xaxis"]["title"]["text"],
        graph["layout"]["yaxis"]["title"]["text"],
    )


def _conformer_artifact():
    return {
        "per_conformer_records": [
            {
                "molecule_id": "CHEMBL1",
                "conformer_id": "CHEMBL1:conf-0",
                "conformer_index": 0,
                "relative_energy_kcal_mol": 0.0,
            },
            {
                "molecule_id": "CHEMBL1",
                "conformer_id": "CHEMBL1:conf-1",
                "conformer_index": 1,
                "relative_energy_kcal_mol": 1.25,
            },
        ],
        "renderable_structures": [
            {
                "molecule_id": "CHEMBL1",
                "conformer_id": "CHEMBL1:conf-0",
                "conformer_index": 0,
                "atoms": [{"index": 0, "element": "C"}],
                "bonds": [],
                "coordinates": [[0.0, 0.0, 0.0]],
                "relative_energy_kcal_mol": 0.0,
            },
            {
                "molecule_id": "CHEMBL1",
                "conformer_id": "CHEMBL1:conf-1",
                "conformer_index": 1,
                "atoms": [{"index": 0, "element": "C"}],
                "bonds": [],
                "coordinates": [[1.0, 2.0, 3.0]],
                "relative_energy_kcal_mol": 1.25,
            },
        ],
    }


def test_cluster_chart_has_required_labels_and_hover_context() -> None:
    graph = build_cluster_chart(
        {"cluster_sizes": [3, 1], "representative_molecule_ids": ["CHEMBL1", "CHEMBL2"]}
    )

    assert graph["kind"] == "plotly"
    assert _layout_titles(graph) == (
        "Molecular similarity cluster sizes",
        "Cluster ID",
        "Molecule count",
    )
    assert graph["data"][0]["y"] == [3, 1]
    assert "Cluster size" in graph["data"][0]["hovertemplate"]
    assert "Representative ID" in graph["data"][0]["hovertemplate"]


def test_similarity_heatmap_has_axes_scale_and_aligned_id_hover() -> None:
    graph = build_similarity_heatmap(
        {"molecule_ids": ["CHEMBL1", "CHEMBL2"], "matrix": [[1.0, 0.4], [0.4, 1.0]]}
    )
    trace = graph["data"][0]

    assert _layout_titles(graph) == (
        "Pairwise molecular similarity",
        "Molecule index — bundled ChEMBL set",
        "Molecule index — bundled ChEMBL set",
    )
    assert trace["x"] == ["CHEMBL1", "CHEMBL2"]
    assert trace["y"] == ["CHEMBL1", "CHEMBL2"]
    assert (trace["zmin"], trace["zmax"]) == (0, 1)
    assert trace["colorbar"]["title"]["text"] == "Tanimoto similarity — unitless, 0 to 1"
    assert "%{x}" in trace["hovertemplate"] and "%{y}" in trace["hovertemplate"]


@pytest.mark.parametrize(
    "artifact",
    [
        {"molecule_ids": ["CHEMBL1"], "matrix": [[np.nan]]},
        {"molecule_ids": ["CHEMBL1", "CHEMBL2"], "matrix": [[1.0, 0.2]]},
        {"molecule_ids": ["CHEMBL1"], "matrix": [[1.1]]},
    ],
)
def test_similarity_heatmap_rejects_nonfinite_misaligned_or_out_of_range(artifact) -> None:
    with pytest.raises(ValueError):
        build_similarity_heatmap(artifact)


def test_fingerprint_histogram_has_required_labels_and_aligned_context() -> None:
    graph = build_fingerprint_histogram(
        {"molecule_ids": ["CHEMBL1", "CHEMBL2"], "active_bit_counts": [7, 11]}
    )

    assert _layout_titles(graph) == (
        "Morgan fingerprint density",
        "Active Morgan fingerprint bits per molecule",
        "Molecule count",
    )
    assert graph["data"][0]["customdata"] == ["CHEMBL1", "CHEMBL2"]
    assert "ChEMBL" in graph["data"][0]["hovertemplate"]


@pytest.mark.parametrize(
    "artifact",
    [
        {"molecule_ids": [], "active_bit_counts": []},
        {"molecule_ids": ["CHEMBL1"], "active_bit_counts": [1, 2]},
    ],
)
def test_fingerprint_histogram_rejects_empty_or_misaligned_inputs(artifact) -> None:
    with pytest.raises(ValueError):
        build_fingerprint_histogram(artifact)


def test_cluster_chart_rejects_mismatched_sizes_and_representatives() -> None:
    with pytest.raises(ValueError):
        build_cluster_chart(
            {"cluster_sizes": [2, 1], "representative_molecule_ids": ["CHEMBL1"]}
        )


def test_conformer_bundle_has_energy_labels_viewer_flags_and_selectors() -> None:
    bundle = build_conformer_bundle(_conformer_artifact())
    graph = bundle["energy_chart"]

    assert _layout_titles(graph) == (
        "Sampled conformer energies",
        "Conformer ID",
        "Relative MMFF94 energy (kcal/mol)",
    )
    assert "Exact relative energy" in graph["data"][0]["hovertemplate"]
    assert bundle["viewer"]["atom_legend"] is True
    assert bundle["viewer"]["xyz_triad"] is True
    assert bundle["selectors"]["molecule_ids"] == ["CHEMBL1"]
    assert bundle["selectors"]["conformer_ids_by_molecule"] == {
        "CHEMBL1": ["CHEMBL1:conf-0", "CHEMBL1:conf-1"]
    }
    assert bundle["identities"][1] == {
        "molecule_id": "CHEMBL1",
        "conformer_id": "CHEMBL1:conf-1",
        "conformer_index": 1,
    }
    json.dumps(bundle, allow_nan=False)


@pytest.mark.parametrize(
    "mutation", ["nonfinite", "misaligned", "missing_coordinates", "energy_mismatch"]
)
def test_conformer_bundle_rejects_invalid_inputs(mutation) -> None:
    artifact = _conformer_artifact()
    if mutation == "nonfinite":
        artifact["per_conformer_records"][0]["relative_energy_kcal_mol"] = np.inf
    elif mutation == "misaligned":
        artifact["renderable_structures"].pop()
    elif mutation == "missing_coordinates":
        artifact["renderable_structures"][0].pop("coordinates")
    else:
        artifact["renderable_structures"][0]["relative_energy_kcal_mol"] = 0.5

    with pytest.raises(ValueError):
        build_conformer_bundle(artifact)


def test_require_finite_walks_nested_containers_and_allows_bool() -> None:
    require_finite({"a": [1.0, (np.float32(2.0), True)], "b": "unchanged"})

    with pytest.raises(ValueError, match="non-finite"):
        require_finite({"a": [1.0, (np.float64(np.nan),)]})


def test_builders_do_not_share_mutable_state_with_inputs_or_outputs() -> None:
    artifact = _conformer_artifact()
    original = copy.deepcopy(artifact)
    bundle = build_conformer_bundle(artifact)

    bundle["viewer"]["structures"][0]["coordinates"][0][0] = 99.0
    artifact["renderable_structures"][1]["coordinates"][0][0] = 88.0

    assert original == _conformer_artifact()
    assert bundle["viewer"]["structures"][1]["coordinates"][0][0] == 1.0
    assert artifact["renderable_structures"][0]["coordinates"][0][0] == 0.0


def test_builders_accept_named_task_2_components_without_artifact_wrappers() -> None:
    fingerprint = build_fingerprint_histogram(
        active_bits=[4], molecule_ids=["CHEMBL1"]
    )
    similarity = build_similarity_heatmap(
        matrix=[[1.0]], molecule_ids=["CHEMBL1"]
    )
    clusters = build_cluster_chart(
        sizes=[1], representative_molecule_ids=["CHEMBL1"]
    )
    conformers = _conformer_artifact()
    bundle = build_conformer_bundle(
        records=conformers["per_conformer_records"],
        structures=conformers["renderable_structures"],
    )

    assert fingerprint["kind"] == similarity["kind"] == clusters["kind"] == "plotly"
    assert bundle["kind"] == "conformer_bundle"
