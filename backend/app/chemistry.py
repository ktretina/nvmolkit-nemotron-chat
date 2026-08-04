"""Deterministic analysis orchestration and lazy nvMolKit runtime adaptation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

import numpy as np

from .models import AnalysisKind, AnalysisParameters, AnalysisResult


class ChemistryRuntime(Protocol):
    def load(self) -> object: ...

    def fingerprints(
        self, state: object, params: AnalysisParameters
    ) -> AnalysisResult: ...

    def similarity(self, state: object) -> AnalysisResult: ...

    def clusters(self, state: object, params: AnalysisParameters) -> AnalysisResult: ...

    def embed(self, state: object, params: AnalysisParameters) -> AnalysisResult: ...

    def optimize(self, state: object) -> AnalysisResult: ...


_STAGES = ("load", "fingerprints", "similarity", "clusters", "embed", "optimize")
_TERMINAL_STAGE = {
    AnalysisKind.FINGERPRINT_DENSITY: "fingerprints",
    AnalysisKind.SIMILARITY: "similarity",
    AnalysisKind.CLUSTERS: "clusters",
    AnalysisKind.CONFORMERS: "optimize",
}


class AnalysisEngine:
    """Advance one cached runtime state only through the requested terminal stage."""

    def __init__(self, runtime: ChemistryRuntime) -> None:
        self.runtime = runtime
        self.state: object | None = None
        self._results: dict[str, AnalysisResult] = {}
        self._signatures: dict[str, tuple[Any, ...]] = {}

    def run(
        self,
        kind: AnalysisKind | str,
        raw_params: Mapping[str, Any] | AnalysisParameters | None,
    ) -> AnalysisResult:
        analysis_kind = AnalysisKind(kind)
        params = (
            raw_params
            if isinstance(raw_params, AnalysisParameters)
            else AnalysisParameters.model_validate(raw_params or {})
        )
        self._invalidate_incompatible(params)
        terminal = _TERMINAL_STAGE[analysis_kind]
        terminal_index = _STAGES.index(terminal)

        for stage in _STAGES[: terminal_index + 1]:
            if stage == "load":
                if self.state is None:
                    self.state = self.runtime.load()
                continue
            if stage in self._results:
                continue
            if self.state is None:  # pragma: no cover - guarded by the ordered loop
                raise RuntimeError("chemistry runtime state was not loaded")
            if stage == "fingerprints":
                result = self.runtime.fingerprints(self.state, params)
                self._signatures[stage] = self._fingerprint_signature(params)
            elif stage == "similarity":
                result = self.runtime.similarity(self.state)
            elif stage == "clusters":
                result = self.runtime.clusters(self.state, params)
                self._signatures[stage] = self._cluster_signature(params)
            elif stage == "embed":
                result = self.runtime.embed(self.state, params)
                self._signatures[stage] = self._embed_signature(params)
            else:
                result = self.runtime.optimize(self.state)
            if not isinstance(result, AnalysisResult):
                raise TypeError(f"runtime stage {stage!r} did not return AnalysisResult")
            self._results[stage] = result

        result = self._results[terminal]
        if result.kind is analysis_kind:
            return result
        return result.model_copy(update={"kind": analysis_kind})

    @staticmethod
    def _fingerprint_signature(params: AnalysisParameters) -> tuple[int, int]:
        return params.fingerprint_radius, params.fingerprint_size

    @staticmethod
    def _cluster_signature(params: AnalysisParameters) -> tuple[float]:
        return (params.cluster_cutoff,)

    @staticmethod
    def _embed_signature(params: AnalysisParameters) -> tuple[int, int]:
        return params.representative_count, params.conformers_per_molecule

    def _invalidate_incompatible(self, params: AnalysisParameters) -> None:
        comparisons = (
            ("fingerprints", self._fingerprint_signature(params)),
            ("clusters", self._cluster_signature(params)),
            ("embed", self._embed_signature(params)),
        )
        for stage, signature in comparisons:
            if stage in self._signatures and self._signatures[stage] != signature:
                self._invalidate_from(stage)
                break

    def _invalidate_from(self, stage: str) -> None:
        first = _STAGES.index(stage)
        for descendant in _STAGES[first:]:
            self._results.pop(descendant, None)
            self._signatures.pop(descendant, None)


@dataclass
class _NvMolKitState:
    records: list[dict[str, Any]] = field(default_factory=list)
    molecules: list[Any] = field(default_factory=list)
    fingerprints: Any = None
    similarity: Any = None
    clusters: list[list[int]] = field(default_factory=list)
    representatives: list[dict[str, Any]] = field(default_factory=list)
    conformer_molecules: list[Any] = field(default_factory=list)
    optimization_result: Any = None


class NvMolKitRuntime:
    """Real runtime; nvMolKit, Torch, pandas, and RDKit load only on demand."""

    def __init__(self, data_path: str | Path, expected_rows: int = 256) -> None:
        self.data_path = Path(data_path)
        self.expected_rows = expected_rows

    def load(self) -> _NvMolKitState:
        import pandas as pd
        from rdkit import Chem

        table = pd.read_csv(self.data_path)
        identifier = "molecule_id" if "molecule_id" in table.columns else "id"
        if identifier not in table.columns or "smiles" not in table.columns:
            raise ValueError("input library requires id and smiles columns")
        if len(table) != self.expected_rows:
            raise ValueError(
                f"input library expected {self.expected_rows} rows; found {len(table)}"
            )
        state = _NvMolKitState()
        invalid_ids: list[str] = []
        for source_row, row in table.iterrows():
            molecule_id = str(row[identifier])
            smiles = str(row["smiles"])
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is None:
                invalid_ids.append(molecule_id)
                continue
            state.records.append(
                {"id": molecule_id, "smiles": smiles, "source_row": int(source_row)}
            )
            state.molecules.append(molecule)
        if not state.molecules:
            raise ValueError("input library produced zero valid molecules")
        state.records_metadata = {  # type: ignore[attr-defined]
            "raw_count": int(len(table)),
            "valid_count": len(state.molecules),
            "invalid_count": len(invalid_ids),
            "invalid_ids": invalid_ids,
        }
        return state

    def fingerprints(
        self, state: object, params: AnalysisParameters
    ) -> AnalysisResult:
        current = _require_state(state)
        from nvmolkit.fingerprints import MorganFingerprintGenerator

        generator = MorganFingerprintGenerator(
            radius=params.fingerprint_radius, fpSize=params.fingerprint_size
        )
        fingerprints = generator.GetFingerprints(current.molecules)
        _synchronize_cuda()
        tensor = fingerprints.torch()
        expected_shape = (len(current.molecules), params.fingerprint_size // 32)
        if tuple(tensor.shape) != expected_shape:
            raise RuntimeError(
                "packed Morgan fingerprint shape must match molecule count and size"
            )
        packed = _host_array(tensor)
        if packed.shape != expected_shape:
            raise RuntimeError("packed Morgan fingerprint shape changed on host transfer")
        unsigned = (packed.astype(np.int64, copy=False) & 0xFFFFFFFF).astype(np.uint32)
        active_bits = np.unpackbits(unsigned.view(np.uint8), axis=1).sum(
            axis=1, dtype=np.int64
        )
        current.fingerprints = fingerprints
        histogram_counts, histogram_edges = np.histogram(
            active_bits, bins=min(20, max(1, len(active_bits)))
        )
        return AnalysisResult(
            kind=AnalysisKind.FINGERPRINT_DENSITY,
            summary={
                "entry_point": "MorganFingerprintGenerator",
                "fingerprint_radius": params.fingerprint_radius,
                "fingerprint_size": params.fingerprint_size,
                "molecule_count": len(current.molecules),
                "packed_shape": list(expected_shape),
                "active_bits_min": int(active_bits.min()),
                "active_bits_median": float(np.median(active_bits)),
                "active_bits_max": int(active_bits.max()),
                "cuda_device": str(tensor.device),
            },
            artifact={
                "histogram_counts": histogram_counts.astype(int).tolist(),
                "histogram_edges": histogram_edges.astype(float).tolist(),
            },
        )

    def similarity(self, state: object) -> AnalysisResult:
        current = _require_state(state)
        if current.fingerprints is None:
            raise RuntimeError("fingerprints are required before similarity")
        if len(current.molecules) < 2:
            raise RuntimeError("Tanimoto comparison requires at least two molecules")
        from nvmolkit.similarity import crossTanimotoSimilarity

        similarity = crossTanimotoSimilarity(current.fingerprints)
        matrix = _host_array(similarity.torch())
        molecule_count = len(current.molecules)
        expected_shape = (molecule_count, molecule_count)
        if matrix.shape != expected_shape:
            raise RuntimeError("all-pairs Tanimoto matrix must be square and aligned")
        if not np.isfinite(matrix).all():
            raise RuntimeError("Tanimoto matrix contains non-finite values")
        if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-7):
            raise RuntimeError("Tanimoto matrix is not symmetric")
        if np.any((matrix < 0.0) | (matrix > 1.0)):
            raise RuntimeError("Tanimoto values must remain between zero and one")
        if not np.allclose(np.diag(matrix), 1.0, rtol=0.0, atol=1e-7):
            raise RuntimeError("Tanimoto matrix diagonal must equal one")
        rows, columns = np.triu_indices(molecule_count, k=1)
        values = matrix[rows, columns]
        maximum = int(np.argmax(values))
        current.similarity = similarity
        return AnalysisResult(
            kind=AnalysisKind.SIMILARITY,
            summary={
                "entry_point": "crossTanimotoSimilarity",
                "matrix_shape": list(expected_shape),
                "q1": float(np.quantile(values, 0.25)),
                "median": float(np.median(values)),
                "q3": float(np.quantile(values, 0.75)),
                "p90": float(np.quantile(values, 0.90)),
                "max": float(values[maximum]),
                "most_similar_nonidentical_pair": {
                    "molecule_ids": [
                        current.records[int(rows[maximum])]["id"],
                        current.records[int(columns[maximum])]["id"],
                    ],
                    "similarity": float(values[maximum]),
                },
            },
            artifact={"matrix": matrix.astype(float).tolist()},
        )

    def clusters(
        self, state: object, params: AnalysisParameters
    ) -> AnalysisResult:
        current = _require_state(state)
        if current.fingerprints is None or current.similarity is None:
            raise RuntimeError("fingerprints and similarity are required before clustering")
        from nvmolkit.clustering import fused_butina

        result = fused_butina(
            current.fingerprints.torch(), cutoff=params.cluster_cutoff
        )
        _synchronize_cuda()
        clusters = [[int(index) for index in cluster] for cluster in result[0]]
        molecule_count = len(current.molecules)
        assigned = [index for cluster in clusters for index in cluster]
        if len(assigned) != molecule_count or sorted(assigned) != list(
            range(molecule_count)
        ):
            raise RuntimeError("every molecule must be assigned to exactly one cluster")
        current.clusters = clusters
        groups = _eligibility_groups(current)
        sizes = [len(cluster) for cluster in clusters]
        singleton_count = sum(size == 1 for size in sizes)
        return AnalysisResult(
            kind=AnalysisKind.CLUSTERS,
            summary={
                "entry_point": "fused_butina",
                "cluster_cutoff": params.cluster_cutoff,
                "molecule_count": molecule_count,
                "cluster_count": len(clusters),
                "singleton_count": singleton_count,
                "singleton_fraction": singleton_count / molecule_count,
                "largest_cluster_sizes": sorted(sizes, reverse=True)[:15],
                "assignment_count": len(assigned),
                "mmff94_eligible_cluster_count": len(groups),
            },
            artifact={
                "clusters": clusters,
                "eligible_representatives_by_cluster": groups,
            },
        )

    def embed(self, state: object, params: AnalysisParameters) -> AnalysisResult:
        current = _require_state(state)
        if not current.clusters:
            raise RuntimeError("clusters are required before conformer embedding")
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from nvmolkit.embedMolecules import EmbedMolecules

        groups = _eligibility_groups(current)
        if len(groups) < 3:
            raise RuntimeError("at least 3 MMFF94-eligible distinct clusters are required")
        selected = [dict(group["members"][0]) for group in groups[: params.representative_count]]
        shortfall = params.representative_count - len(selected)
        molecules = [
            Chem.AddHs(Chem.Mol(current.molecules[item["molecule_index"]]))
            for item in selected
        ]
        parameters = AllChem.ETKDGv3()
        parameters.randomSeed = 7
        parameters.useRandomCoords = True
        EmbedMolecules(
            molecules,
            parameters,
            confsPerMolecule=params.conformers_per_molecule,
            maxIterations=-1,
        )
        _synchronize_cuda()
        representatives: list[dict[str, Any]] = []
        conformer_molecules: list[Any] = []
        partial_ids: list[str] = []
        zero_ids: list[str] = []
        for record, molecule in zip(selected, molecules):
            generated = int(molecule.GetNumConformers())
            if not 0 <= generated <= params.conformers_per_molecule:
                raise RuntimeError("EmbedMolecules returned an invalid conformer count")
            output_record = {**record, "generated_conformer_count": generated}
            representatives.append(output_record)
            if generated == 0:
                zero_ids.append(record["molecule_id"])
            else:
                conformer_molecules.append(molecule)
                if generated < params.conformers_per_molecule:
                    partial_ids.append(record["molecule_id"])
        if not conformer_molecules:
            raise RuntimeError("all selected representatives produced zero conformers")
        current.representatives = representatives
        current.conformer_molecules = conformer_molecules
        summary = {
            "entry_point": "EmbedMolecules",
            "selection_executor": "Python/RDKit MMFF94 eligibility",
            "requested_representative_count": params.representative_count,
            "selected_representative_count": len(selected),
            "selection_shortfall": shortfall,
            "requested_conformers_per_molecule": params.conformers_per_molecule,
            "generated_conformer_count": sum(
                item["generated_conformer_count"] for item in representatives
            ),
            "partial_embedding_ids": partial_ids,
            "zero_embedding_ids": zero_ids,
        }
        _ensure_finite_json(summary)
        return AnalysisResult(
            kind=AnalysisKind.CONFORMERS,
            summary=summary,
            artifact={"representatives": representatives},
        )

    def optimize(self, state: object) -> AnalysisResult:
        current = _require_state(state)
        from rdkit import Chem
        from rdkit.Geometry import Point3D
        from nvmolkit.mmffOptimization import MMFFOptimizeMoleculesConfs
        from nvmolkit.types import CoordinateOutput

        molecules = [Chem.Mol(molecule) for molecule in current.conformer_molecules]
        successful = [
            record
            for record in current.representatives
            if record["generated_conformer_count"] > 0
        ]
        if not molecules or len(molecules) != len(successful):
            raise RuntimeError("embedded molecule provenance is unreconciled")
        result = MMFFOptimizeMoleculesConfs(
            molecules, maxIters=500, output=CoordinateOutput.DEVICE
        )
        _synchronize_cuda()
        records, authoritative_pairs = _optimization_records(
            result, molecules, successful
        )
        coordinate_groups = result.per_molecule()
        if len(coordinate_groups) != len(molecules):
            raise RuntimeError("MMFF94 coordinate molecule totals are unreconciled")
        for molecule, coordinates in zip(molecules, coordinate_groups):
            if len(coordinates) != molecule.GetNumConformers():
                raise RuntimeError("MMFF94 coordinate conformer totals are unreconciled")

        offsets = [0] * len(molecules)
        updates: list[tuple[Any, int, np.ndarray]] = []
        for molecule_index, conformer_index in authoritative_pairs:
            offset = offsets[molecule_index]
            if offset >= len(coordinate_groups[molecule_index]):
                raise RuntimeError("MMFF94 coordinate pairs are unreconciled")
            coordinates = _host_array(coordinate_groups[molecule_index][offset])
            offsets[molecule_index] += 1
            molecule = molecules[molecule_index]
            if coordinates.shape != (molecule.GetNumAtoms(), 3):
                raise RuntimeError("optimized coordinate array has the wrong shape")
            if not np.isfinite(coordinates).all():
                raise RuntimeError("optimized coordinates contain non-finite values")
            updates.append((molecule, conformer_index, coordinates))
        if offsets != [len(group) for group in coordinate_groups]:
            raise RuntimeError("MMFF94 coordinate pairs are unreconciled")
        for molecule, conformer_index, coordinates in updates:
            conformer = molecule.GetConformer(conformer_index)
            for atom_index, (x, y, z) in enumerate(coordinates):
                conformer.SetAtomPosition(
                    atom_index, Point3D(float(x), float(y), float(z))
                )

        selected: list[dict[str, Any]] = []
        for molecule_index, representative in enumerate(successful):
            converged = [
                record
                for record in records
                if record["optimization_molecule_index"] == molecule_index
                and record["converged"]
            ]
            if converged:
                best = min(
                    converged,
                    key=lambda record: (
                        record["energy_kcal_mol"], record["conformer_index"]
                    ),
                ).copy()
                best["selected_conformer_id"] = (
                    f"{representative['molecule_id']}:conf-{best['conformer_index']}"
                )
                selected.append(best)
        attempted = len(records)
        converged_count = sum(record["converged"] for record in records)
        summary = {
            "entry_point": "MMFFOptimizeMoleculesConfs",
            "attempted_conformer_count": attempted,
            "converged_conformer_count": converged_count,
            "unconverged_conformer_count": attempted - converged_count,
            "scope": "computational chemistry analysis only",
        }
        artifact = {
            "per_conformer_records": records,
            "selected_conformer_records": selected,
        }
        _ensure_finite_json({"summary": summary, "artifact": artifact})
        current.conformer_molecules = molecules
        current.optimization_result = result
        return AnalysisResult(
            kind=AnalysisKind.CONFORMERS, summary=summary, artifact=artifact
        )


def _require_state(state: object) -> _NvMolKitState:
    if not isinstance(state, _NvMolKitState):
        raise TypeError("NvMolKitRuntime received an incompatible state")
    return state


def _synchronize_cuda() -> None:
    import torch

    torch.cuda.synchronize()


def _host_array(value: Any) -> np.ndarray:
    _synchronize_cuda()
    host = value.cpu() if hasattr(value, "cpu") else value
    if hasattr(host, "numpy"):
        return np.asarray(host.numpy())
    return np.asarray(host)


def _eligibility_groups(state: _NvMolKitState) -> list[dict[str, Any]]:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    groups: list[dict[str, Any]] = []
    for cluster_id, cluster in enumerate(state.clusters):
        members: list[dict[str, Any]] = []
        for molecule_index in cluster:
            molecule = Chem.AddHs(Chem.Mol(state.molecules[molecule_index]))
            if AllChem.MMFFHasAllMoleculeParams(molecule):
                source = state.records[molecule_index]
                members.append(
                    {
                        "molecule_id": str(source["id"]),
                        "source_row": int(source["source_row"]),
                        "cluster_id": cluster_id,
                        "molecule_index": molecule_index,
                    }
                )
        if members:
            members.sort(key=lambda item: item["source_row"])
            groups.append(
                {
                    "cluster_id": cluster_id,
                    "cluster_size": len(cluster),
                    "minimum_source_row": min(
                        int(state.records[index]["source_row"]) for index in cluster
                    ),
                    "is_singleton": len(cluster) == 1,
                    "members": members,
                }
            )
    groups.sort(key=lambda group: (-group["cluster_size"], group["minimum_source_row"]))
    return groups


def _optimization_records(
    result: Any,
    molecules: list[Any],
    representatives: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    arrays = [
        _host_array(getattr(result, name).torch()).reshape(-1)
        for name in ("energies", "converged", "mol_indices", "conf_indices")
    ]
    energies, convergence, molecule_indices, conformer_indices = arrays
    if len({len(array) for array in arrays}) != 1:
        raise RuntimeError("MMFF94 result buffers must have the same length")
    if not np.isfinite(energies).all():
        raise RuntimeError("MMFF94 energies contain non-finite values")
    convergence_values = [int(value) for value in convergence.tolist()]
    if set(convergence_values) - {0, 1}:
        raise RuntimeError("MMFF94 convergence flags must be binary")
    expected_pairs = {
        (molecule_index, conformer_index)
        for molecule_index, molecule in enumerate(molecules)
        for conformer_index in range(molecule.GetNumConformers())
    }
    pairs = [
        (int(molecule_index), int(conformer_index))
        for molecule_index, conformer_index in zip(
            molecule_indices.tolist(), conformer_indices.tolist()
        )
    ]
    if len(pairs) != len(set(pairs)) or set(pairs) != expected_pairs:
        raise RuntimeError("MMFF94 molecule/conformer pairs are incomplete or duplicated")
    records = [
        {
            "molecule_id": str(representatives[molecule_index]["molecule_id"]),
            "cluster_id": int(representatives[molecule_index]["cluster_id"]),
            "conformer_index": conformer_index,
            "energy_kcal_mol": float(energy),
            "converged": bool(did_converge),
            "optimization_molecule_index": molecule_index,
        }
        for energy, did_converge, (molecule_index, conformer_index) in zip(
            energies.tolist(), convergence_values, pairs
        )
    ]
    records.sort(
        key=lambda item: (
            item["optimization_molecule_index"], item["conformer_index"]
        )
    )
    return records, pairs


def _ensure_finite_json(payload: dict[str, Any]) -> None:
    json.dumps(payload, allow_nan=False)
