from __future__ import annotations

from typing import Any

import pytest

from app.models import AnalysisKind, AnalysisParameters, AnalysisResult


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.invocations: list[tuple[str, AnalysisParameters | None]] = []

    def _record(
        self,
        stage: str,
        params: AnalysisParameters | None = None,
    ) -> AnalysisResult:
        self.calls.append(stage)
        self.invocations.append((stage, params))
        kind = {
            "fingerprints": AnalysisKind.FINGERPRINT_DENSITY,
            "similarity": AnalysisKind.SIMILARITY,
            "clusters": AnalysisKind.CLUSTERS,
            "embed": AnalysisKind.CONFORMERS,
            "optimize": AnalysisKind.CONFORMERS,
        }[stage]
        return AnalysisResult(
            kind=kind,
            summary={
                "terminal_stage": stage,
                "call_number": len(self.calls),
                "nested": {"values": [stage]},
            },
            artifact={
                "stage": stage,
                "token": len(self.calls),
                "nested": {"values": [stage]},
            },
        )

    def load(self) -> dict[str, Any]:
        self.calls.append("load")
        self.invocations.append(("load", None))
        return {"loaded": True}

    def fingerprints(
        self, state: object, params: AnalysisParameters
    ) -> AnalysisResult:
        return self._record("fingerprints", params)

    def similarity(self, state: object) -> AnalysisResult:
        return self._record("similarity")

    def clusters(self, state: object, params: AnalysisParameters) -> AnalysisResult:
        return self._record("clusters", params)

    def embed(self, state: object, params: AnalysisParameters) -> AnalysisResult:
        return self._record("embed", params)

    def optimize(self, state: object) -> AnalysisResult:
        return self._record("optimize")


@pytest.fixture
def fake_runtime() -> FakeRuntime:
    return FakeRuntime()
