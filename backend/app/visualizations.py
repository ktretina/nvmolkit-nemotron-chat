"""Validated, frontend-neutral scientific visualization payloads."""

from __future__ import annotations

import json
import math
import numbers
from collections.abc import Mapping, Sequence
from typing import Any


def require_finite(value: Any) -> None:
    """Reject non-finite real values anywhere in common nested containers."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            require_finite(key)
            require_finite(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            require_finite(item)
        return
    if isinstance(value, bool):
        return
    if isinstance(value, numbers.Real) and not math.isfinite(float(value)):
        raise ValueError("visualization payload contains a non-finite value")


def build_fingerprint_histogram(
    artifact_or_active_bits: Mapping[str, Any] | Sequence[Any] | None = None,
    molecule_ids: Sequence[Any] | None = None,
    *,
    active_bits: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build a Plotly-compatible histogram from Task 2 fingerprint artifacts."""

    source = _one_source(artifact_or_active_bits, active_bits, "active_bits")
    if isinstance(source, Mapping):
        artifact = source
        counts = _required(artifact, "active_bit_counts")
        ids = _required(artifact, "molecule_ids")
    else:
        counts = source
        ids = molecule_ids
    count_values = _numeric_vector(counts, "active-bit counts", integer=True)
    id_values = _identifiers(ids, "molecule IDs")
    _aligned_nonempty(count_values, id_values, "fingerprint counts and molecule IDs")
    if any(value < 0 for value in count_values):
        raise ValueError("active-bit counts must be nonnegative")

    graph = _plotly_graph(
        kind="fingerprint_density",
        title="Morgan fingerprint density",
        x_title="Active Morgan fingerprint bits per molecule",
        y_title="Molecule count",
        trace={
            "type": "histogram",
            "x": count_values,
            "hovertemplate": (
                "Active Morgan bits: %{x}<br>Molecule count: %{y}<extra></extra>"
            ),
        },
    )
    return _validated_json(graph)


def _sparse_axis_ticks(identifiers: Sequence[str], *, maximum: int = 8) -> list[str]:
    """Return ordered, inclusive, evenly spaced labels for a categorical axis."""

    if len(identifiers) <= maximum:
        return list(identifiers)
    last_index = len(identifiers) - 1
    return [
        identifiers[round(tick_index * last_index / (maximum - 1))]
        for tick_index in range(maximum)
    ]


def build_similarity_heatmap(
    artifact_or_matrix: Mapping[str, Any] | Sequence[Any] | None = None,
    molecule_ids: Sequence[Any] | None = None,
    *,
    matrix: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build a Plotly-compatible heatmap from Task 2 similarity artifacts."""

    source = _one_source(artifact_or_matrix, matrix, "matrix")
    if isinstance(source, Mapping):
        artifact = source
        matrix_values = _required(artifact, "matrix")
        ids = _required(artifact, "molecule_ids")
    else:
        matrix_values = source
        ids = molecule_ids
    id_values = _identifiers(ids, "molecule IDs")
    if not id_values:
        raise ValueError("similarity molecule IDs must not be empty")
    rows = _sequence(matrix_values, "similarity matrix")
    if len(rows) != len(id_values):
        raise ValueError("similarity matrix must be square and molecule-aligned")
    values: list[list[float]] = []
    for row in rows:
        row_values = _numeric_vector(row, "similarity matrix row")
        if len(row_values) != len(id_values):
            raise ValueError("similarity matrix must be square and molecule-aligned")
        if any(value < 0.0 or value > 1.0 for value in row_values):
            raise ValueError("Tanimoto similarities must be between 0 and 1")
        values.append(row_values)

    tick_values = _sparse_axis_ticks(id_values)
    graph = _plotly_graph(
        kind="similarity",
        title="Pairwise molecular similarity",
        x_title="Bundled ChEMBL molecule",
        y_title="Bundled ChEMBL molecule",
        trace={
            "type": "heatmap",
            "z": values,
            "x": id_values,
            "y": id_values,
            "zmin": 0,
            "zmax": 1,
            "colorbar": {
                "title": {"text": "Tanimoto<br>similarity", "side": "top"},
                "tickmode": "array",
                "tickvals": [0, 0.5, 1],
                "ticktext": ["0", "0.5", "1"],
                "x": 0.84,
                "xanchor": "left",
                "xpad": 8,
                "y": 0.5,
                "yanchor": "middle",
                "len": 0.76,
                "thickness": 18,
            },
            "hovertemplate": (
                "ChEMBL row %{y}<br>ChEMBL column %{x}<br>"
                "Tanimoto similarity: %{z:.3f}<extra></extra>"
            ),
        },
    )
    graph["layout"].update(
        margin={"l": 104, "r": 96, "t": 58, "b": 112, "pad": 4},
        xaxis={
            "title": {"text": "Bundled ChEMBL molecule"},
            "tickmode": "array",
            "tickvals": tick_values,
            "ticktext": tick_values,
            "tickangle": -45,
            "automargin": True,
            "constrain": "domain",
            "domain": [0, 0.8],
        },
        yaxis={
            "title": {"text": "Bundled ChEMBL molecule"},
            "tickmode": "array",
            "tickvals": tick_values,
            "ticktext": tick_values,
            "automargin": True,
            "scaleanchor": "x",
            "scaleratio": 1,
            "constrain": "domain",
        },
    )
    return _validated_json(graph)


def build_cluster_chart(
    artifact_or_sizes: Mapping[str, Any] | Sequence[Any] | None = None,
    representative_molecule_ids: Sequence[Any] | None = None,
    *,
    sizes: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build a Plotly-compatible bar chart from Task 2 cluster artifacts."""

    source = _one_source(artifact_or_sizes, sizes, "sizes")
    if isinstance(source, Mapping):
        artifact = source
        size_source = _required(artifact, "cluster_sizes")
        representatives = _required(artifact, "representative_molecule_ids")
    else:
        size_source = source
        representatives = representative_molecule_ids
    size_values = _numeric_vector(size_source, "cluster sizes", integer=True)
    representative_values = _identifiers(
        representatives, "representative molecule IDs"
    )
    _aligned_nonempty(
        size_values, representative_values, "cluster sizes and representatives"
    )
    if any(value <= 0 for value in size_values):
        raise ValueError("cluster sizes must be positive")

    graph = _plotly_graph(
        kind="clusters",
        title="Molecular similarity cluster sizes",
        x_title="Cluster ID",
        y_title="Molecule count",
        trace={
            "type": "bar",
            "x": list(range(len(size_values))),
            "y": size_values,
            "customdata": representative_values,
            "hovertemplate": (
                "Cluster ID: %{x}<br>Cluster size: %{y}<br>"
                "Representative ID: %{customdata}<extra></extra>"
            ),
        },
    )
    return _validated_json(graph)


def build_conformer_bundle(
    artifact_or_records: Mapping[str, Any] | Sequence[Any] | None = None,
    structures: Sequence[Any] | None = None,
    *,
    records: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build aligned Plotly-energy and 3Dmol.js-ready conformer dictionaries."""

    source = _one_source(artifact_or_records, records, "records")
    if isinstance(source, Mapping):
        artifact = source
        record_source = _required(artifact, "per_conformer_records")
        viewer_structures = _required(artifact, "renderable_structures")
    else:
        record_source = source
        viewer_structures = structures
    record_values = _mapping_sequence(record_source, "conformer records")
    structure_values = _mapping_sequence(viewer_structures, "viewer structures")
    _aligned_nonempty(record_values, structure_values, "conformer records and structures")

    normalized_records = [_normalize_conformer_record(record) for record in record_values]
    normalized_structures = [
        _normalize_structure(structure) for structure in structure_values
    ]
    record_identities = [_identity(record) for record in normalized_records]
    structure_identities = [_identity(structure) for structure in normalized_structures]
    if record_identities != structure_identities:
        raise ValueError("conformer records and structures are not identity-aligned")
    if any(
        normalized_records[index]["relative_energy_kcal_mol"]
        != normalized_structures[index].get("relative_energy_kcal_mol")
        for index in range(len(normalized_records))
    ):
        raise ValueError("conformer records and structures are not energy-aligned")
    if len({item[1] for item in record_identities}) != len(record_identities):
        raise ValueError("conformer identifiers must be unique")

    conformer_ids = [item[1] for item in record_identities]
    molecule_ids = [item[0] for item in record_identities]
    energies = [record["relative_energy_kcal_mol"] for record in normalized_records]
    energy_plot = _plotly_graph(
        kind="plotly",
        title="Sampled conformer energies",
        x_title="Conformer ID",
        y_title="Relative MMFF94 energy (kcal/mol)",
        trace={
            "type": "scatter",
            "mode": "markers",
            "x": conformer_ids,
            "y": energies,
            "customdata": molecule_ids,
            "hovertemplate": (
                "Molecule %{customdata}<br>Conformer %{x}<br>"
                "Exact relative energy: %{y} kcal/mol<extra></extra>"
            ),
        },
    )
    unique_molecule_ids = list(dict.fromkeys(molecule_ids))
    conformers_by_molecule = {
        molecule_id: [
            conformer_id
            for current_molecule, conformer_id, _ in record_identities
            if current_molecule == molecule_id
        ]
        for molecule_id in unique_molecule_ids
    }
    bundle = {
        "kind": "conformers",
        "energy_plot": energy_plot,
        "viewer": {
            "kind": "3dmol",
            "structures": normalized_structures,
            "atom_legend": True,
            "xyz_triad": True,
        },
        "selectors": {
            "molecule_ids": unique_molecule_ids,
            "conformer_ids_by_molecule": conformers_by_molecule,
        },
        "identities": [
            {
                "molecule_id": molecule_id,
                "conformer_id": conformer_id,
                "conformer_index": conformer_index,
            }
            for molecule_id, conformer_id, conformer_index in record_identities
        ],
    }
    return _validated_json(bundle)


def _plotly_graph(
    *, kind: str, title: str, x_title: str, y_title: str, trace: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": kind,
        "data": [trace],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": x_title}},
            "yaxis": {"title": {"text": y_title}},
        },
    }


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"visualization artifact requires {key!r}")
    return mapping[key]


def _one_source(positional: Any, named: Any, name: str) -> Any:
    if positional is not None and named is not None:
        raise ValueError(f"provide either an artifact/positional value or {name}, not both")
    source = positional if named is None else named
    if source is None:
        raise ValueError(f"an artifact or {name} is required")
    return source


def _sequence(value: Any, name: str) -> list[Any]:
    if value is None or isinstance(value, (str, bytes, bytearray, Mapping)):
        raise ValueError(f"{name} must be a sequence")
    try:
        return list(value)
    except TypeError as error:
        raise ValueError(f"{name} must be a sequence") from error


def _mapping_sequence(value: Any, name: str) -> list[Mapping[str, Any]]:
    values = _sequence(value, name)
    if not all(isinstance(item, Mapping) for item in values):
        raise ValueError(f"{name} must contain objects")
    return values


def _identifiers(value: Any, name: str) -> list[str]:
    identifiers = _sequence(value, name)
    if any(not isinstance(item, str) or not item.strip() for item in identifiers):
        raise ValueError(f"{name} must contain nonempty strings")
    normalized = [str(item) for item in identifiers]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be unique")
    return normalized


def _numeric_vector(value: Any, name: str, *, integer: bool = False) -> list[Any]:
    values = _sequence(value, name)
    normalized: list[Any] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, numbers.Real):
            raise ValueError(f"{name} must contain numeric values")
        require_finite(item)
        number = float(item)
        if integer:
            if not number.is_integer():
                raise ValueError(f"{name} must contain exact integers")
            normalized.append(int(number))
        else:
            normalized.append(number)
    return normalized


def _aligned_nonempty(first: Sequence[Any], second: Sequence[Any], name: str) -> None:
    if not first or not second:
        raise ValueError(f"{name} must not be empty")
    if len(first) != len(second):
        raise ValueError(f"{name} must be aligned")


def _normalize_conformer_record(record: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _json_primitives(record)
    molecule_id, conformer_id, conformer_index = _validated_identity(normalized)
    energy = _numeric_field(normalized, "relative_energy_kcal_mol")
    normalized.update(
        molecule_id=molecule_id,
        conformer_id=conformer_id,
        conformer_index=conformer_index,
        relative_energy_kcal_mol=energy,
    )
    return normalized


def _normalize_structure(structure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(_required(structure, "atoms"), list):
        raise ValueError("atoms must be a list")
    if not isinstance(_required(structure, "bonds"), list):
        raise ValueError("bonds must be a list")
    normalized = _json_primitives(structure)
    molecule_id, conformer_id, conformer_index = _validated_identity(normalized)
    coordinates = _sequence(_required(normalized, "coordinates"), "coordinates")
    if not coordinates:
        raise ValueError("coordinates must not be empty")
    normalized_coordinates = [
        _numeric_vector(point, "coordinate", integer=False) for point in coordinates
    ]
    if any(len(point) != 3 for point in normalized_coordinates):
        raise ValueError("each coordinate must contain exactly x, y, and z")
    atoms = _normalize_atoms(_required(normalized, "atoms"))
    if len(atoms) != len(normalized_coordinates):
        raise ValueError("atom and coordinate counts must be aligned")
    bonds = _normalize_bonds(_required(normalized, "bonds"), len(atoms))
    normalized.update(
        molecule_id=molecule_id,
        conformer_id=conformer_id,
        conformer_index=conformer_index,
        atoms=atoms,
        bonds=bonds,
        coordinates=normalized_coordinates,
    )
    if "relative_energy_kcal_mol" in normalized:
        normalized["relative_energy_kcal_mol"] = _numeric_field(
            normalized, "relative_energy_kcal_mol"
        )
    return normalized


def _normalize_atoms(value: Any) -> list[dict[str, Any]]:
    atoms = _mapping_sequence(value, "atoms")
    if not atoms:
        raise ValueError("atoms must not be empty")
    normalized: list[dict[str, Any]] = []
    for atom in atoms:
        item = atom
        index = _exact_nonnegative_integer(_required(item, "index"), "atom index")
        element = _required(item, "element")
        if not isinstance(element, str) or not element.strip():
            raise ValueError("atom element must be a nonempty string")
        item.update(index=index, element=str(element))
        normalized.append(item)
    if [atom["index"] for atom in normalized] != list(range(len(normalized))):
        raise ValueError("atom indices must be unique, contiguous, and aligned")
    return normalized


def _normalize_bonds(value: Any, atom_count: int) -> list[dict[str, Any]]:
    bonds = _mapping_sequence(value, "bonds")
    normalized: list[dict[str, Any]] = []
    endpoints_seen: set[tuple[int, int]] = set()
    for bond in bonds:
        item = bond
        begin = _exact_nonnegative_integer(_required(item, "begin"), "bond begin")
        end = _exact_nonnegative_integer(_required(item, "end"), "bond end")
        if begin == end:
            raise ValueError("bond endpoints must be distinct")
        if begin >= atom_count or end >= atom_count:
            raise ValueError("bond endpoints must reference atom indices")
        endpoints = tuple(sorted((begin, end)))
        if endpoints in endpoints_seen:
            raise ValueError("duplicate bond endpoints are not allowed")
        endpoints_seen.add(endpoints)
        order = _positive_numeric(_required(item, "order"), "bond order")
        item.update(begin=begin, end=end, order=order)
        normalized.append(item)
    return normalized


def _exact_nonnegative_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ValueError(f"{name} must be an exact integer")
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} must be nonnegative")
    return normalized


def _positive_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be numeric")
    require_finite(value)
    normalized = float(value)
    if normalized <= 0.0:
        raise ValueError(f"{name} must be positive")
    return normalized


def _validated_identity(mapping: Mapping[str, Any]) -> tuple[str, str, int]:
    molecule_id = _required(mapping, "molecule_id")
    conformer_id = _required(mapping, "conformer_id")
    conformer_index = _required(mapping, "conformer_index")
    if not isinstance(molecule_id, str) or not molecule_id.strip():
        raise ValueError("molecule_id must be a nonempty string")
    if not isinstance(conformer_id, str) or not conformer_id.strip():
        raise ValueError("conformer_id must be a nonempty string")
    if (
        isinstance(conformer_index, bool)
        or not isinstance(conformer_index, numbers.Integral)
        or int(conformer_index) < 0
    ):
        raise ValueError("conformer_index must be a nonnegative integer")
    return molecule_id, conformer_id, int(conformer_index)


def _numeric_field(mapping: Mapping[str, Any], key: str) -> float:
    value = _required(mapping, key)
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{key} must be numeric")
    require_finite(value)
    return float(value)


def _identity(mapping: Mapping[str, Any]) -> tuple[str, str, int]:
    return (
        mapping["molecule_id"],
        mapping["conformer_id"],
        mapping["conformer_index"],
    )


def _validated_json(value: Any) -> Any:
    require_finite(value)
    _require_string_keys(value)
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("visualization payload must be JSON-safe") from error
    return value


def _require_string_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON mappings require exact string keys")
            _require_string_keys(item)
    elif isinstance(value, list):
        for item in value:
            _require_string_keys(item)


def _json_primitives(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON mappings require string keys")
            normalized[str(key)] = _json_primitives(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_json_primitives(item) for item in value]
    if value is None or type(value) in {str, int, float, bool}:
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value)
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        listed = tolist()
        if listed is not value:
            return _json_primitives(listed)
    item = getattr(value, "item", None)
    if callable(item):
        shape = getattr(value, "shape", ())
        if shape not in (None, ()):
            raise ValueError("array-like values must support list conversion")
        try:
            scalar = item()
        except (TypeError, ValueError) as error:
            raise ValueError("scalar-like value could not be normalized") from error
        if scalar is not value:
            return _json_primitives(scalar)
    return value
