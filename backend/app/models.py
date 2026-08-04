"""Validated public models for deterministic chemistry analyses."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisKind(StrEnum):
    FINGERPRINT_DENSITY = "fingerprint_density"
    SIMILARITY = "similarity"
    CLUSTERS = "clusters"
    CONFORMERS = "conformers"


class AnalysisParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    fingerprint_radius: Literal[2, 3] = 2
    fingerprint_size: Literal[1024, 2048] = 2048
    cluster_cutoff: float = Field(default=0.50, ge=0.40, le=0.60)
    representative_count: int = Field(default=3, ge=3, le=6)
    conformers_per_molecule: int = Field(default=5, ge=3, le=8)


class AnalysisResult(BaseModel):
    kind: AnalysisKind
    summary: dict[str, Any]
    artifact: dict[str, Any]
