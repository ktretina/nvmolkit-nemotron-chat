"""Bounded hosted-Nemotron selection and scientific interpretation adapter."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .config import SETTINGS
from .models import AnalysisKind, AnalysisParameters, AnalysisResult


class NemotronError(RuntimeError):
    """A safe-to-return hosted model failure."""


class NemotronProtocolError(NemotronError):
    """A hosted response that violates the analysis selection protocol."""


TOOL_KINDS: dict[str, AnalysisKind] = {
    "analyze_fingerprint_density": AnalysisKind.FINGERPRINT_DENSITY,
    "analyze_similarity_map": AnalysisKind.SIMILARITY,
    "analyze_cluster_distribution": AnalysisKind.CLUSTERS,
    "analyze_representative_conformers": AnalysisKind.CONFORMERS,
}


def _build_tool_schemas() -> list[dict[str, Any]]:
    parameters = AnalysisParameters.model_json_schema()
    descriptions = {
        "analyze_fingerprint_density": "Analyze Morgan fingerprint density.",
        "analyze_similarity_map": "Analyze pairwise molecular similarity.",
        "analyze_cluster_distribution": "Analyze molecular cluster sizes.",
        "analyze_representative_conformers": "Analyze representative conformers.",
    }
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": descriptions[name],
                "parameters": copy.deepcopy(parameters),
            },
        }
        for name in TOOL_KINDS
    ]


TOOL_SCHEMAS = _build_tool_schemas()


@dataclass(frozen=True)
class AnalysisSelection:
    call_id: str
    kind: AnalysisKind
    params: AnalysisParameters


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _message(completion: object) -> object:
    choices = _field(completion, "choices")
    if not isinstance(choices, (list, tuple)) or not choices:
        raise NemotronProtocolError("Hosted model returned an invalid response")
    return _field(choices[0], "message")


def parse_analysis_call(completion: object) -> AnalysisSelection:
    """Validate one and only one high-level analysis tool selection."""

    message = _message(completion)
    tool_calls = _field(message, "tool_calls")
    if not isinstance(tool_calls, (list, tuple)) or len(tool_calls) != 1:
        raise NemotronProtocolError("Hosted model must select exactly one analysis")
    tool_call = tool_calls[0]
    call_id = _field(tool_call, "id")
    if not isinstance(call_id, str) or not call_id.strip():
        raise NemotronProtocolError("Hosted model returned an invalid tool call")
    if _field(tool_call, "type") != "function":
        raise NemotronProtocolError("Hosted model returned an invalid tool call")
    function = _field(tool_call, "function")
    name = _field(function, "name")
    if not isinstance(name, str) or name not in TOOL_KINDS:
        raise NemotronProtocolError("Hosted model selected an unknown analysis")
    raw_arguments = _field(function, "arguments")
    if not isinstance(raw_arguments, str):
        raise NemotronProtocolError("Hosted model returned invalid analysis parameters")
    try:
        arguments = json.loads(raw_arguments)
    except (TypeError, ValueError):
        raise NemotronProtocolError(
            "Hosted model returned invalid analysis parameters"
        ) from None
    if not isinstance(arguments, dict):
        raise NemotronProtocolError("Hosted model returned invalid analysis parameters")
    for field_name in ("fingerprint_radius", "fingerprint_size"):
        if field_name in arguments and type(arguments[field_name]) is not int:
            raise NemotronProtocolError(
                "Hosted model returned invalid analysis parameters"
            )
    try:
        params = AnalysisParameters.model_validate(arguments)
    except ValidationError:
        raise NemotronProtocolError(
            "Hosted model returned invalid analysis parameters"
        ) from None
    return AnalysisSelection(call_id=call_id, kind=TOOL_KINDS[name], params=params)


def select_analysis(client: object, message: str) -> AnalysisSelection:
    """Ask a caller-supplied, key-bound client to select one bounded analysis."""

    if not isinstance(message, str):
        raise NemotronProtocolError("Analysis request must be text")
    user_message = message.strip()
    if not user_message:
        raise ValueError("message must not be empty")
    if len(user_message) > 2000:
        raise ValueError("message must be at most 2000 characters")
    request = {
        "model": SETTINGS.nemotron_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Select exactly one supplied analysis function that best answers "
                    "the user's molecular-analysis request. Do not answer in prose."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        "tools": copy.deepcopy(TOOL_SCHEMAS),
        "tool_choice": "required",
    }
    try:
        response = client.chat.completions.create(**request)  # type: ignore[attr-defined]
    except Exception:
        raise NemotronError("Hosted analysis selection failed") from None
    return parse_analysis_call(response)


_SAFE_METADATA_FIELDS = (
    "kind",
    "title",
    "labels",
    "x_label",
    "y_label",
    "axis_labels",
    "colorbar_label",
    "legend_label",
    "units",
)


_MAX_METADATA_STRINGS = 64
_MAX_METADATA_STRING_LENGTH = 200
_MAX_METADATA_DEPTH = 3
_MAX_METADATA_NODES = 128
_MAX_METADATA_CONTAINER_LENGTH = 32
_MAX_METADATA_BYTES = 8192
_ALLOWED_METADATA_KEYS = frozenset(
    {
        *_SAFE_METADATA_FIELDS,
        "x",
        "y",
        "z",
        "text",
        "name",
    }
)


def _is_label_key(key: str) -> bool:
    return key in _ALLOWED_METADATA_KEYS


def _count_metadata_string(value: str, string_count: list[int]) -> str:
    if not value or len(value) > _MAX_METADATA_STRING_LENGTH:
        raise NemotronProtocolError("Visualization metadata contains invalid text")
    string_count[0] += 1
    if string_count[0] > _MAX_METADATA_STRINGS:
        raise NemotronProtocolError("Visualization metadata is too large")
    return value


def _safe_metadata_value(
    value: Any, *, depth: int, string_count: list[int], node_count: list[int]
) -> Any:
    node_count[0] += 1
    if node_count[0] > _MAX_METADATA_NODES:
        raise NemotronProtocolError("Visualization metadata is too large")
    if depth > _MAX_METADATA_DEPTH:
        raise NemotronProtocolError("Visualization metadata is too deeply nested")
    if type(value) is str:
        return _count_metadata_string(value, string_count)
    if isinstance(value, (list, tuple)):
        if not value or len(value) > _MAX_METADATA_CONTAINER_LENGTH:
            raise NemotronProtocolError("Visualization metadata has invalid list size")
        return [
            _safe_metadata_value(
                item,
                depth=depth + 1,
                string_count=string_count,
                node_count=node_count,
            )
            for item in value
        ]
    if isinstance(value, Mapping):
        if not value or len(value) > _MAX_METADATA_CONTAINER_LENGTH:
            raise NemotronProtocolError(
                "Visualization metadata has invalid mapping size"
            )
        safe: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str or not _is_label_key(key):
                raise NemotronProtocolError(
                    "Visualization metadata contains a non-label field"
                )
            _count_metadata_string(key, string_count)
            safe[key] = _safe_metadata_value(
                item,
                depth=depth + 1,
                string_count=string_count,
                node_count=node_count,
            )
        return safe
    raise NemotronProtocolError("Visualization metadata must contain only text labels")


def interpret_result(
    client: object,
    result: AnalysisResult,
    visualization_metadata: Mapping[str, Any],
) -> str:
    """Interpret compact summary and display labels without sending raw artifacts."""

    string_count = [0]
    node_count = [0]
    safe_metadata = {
        key: _safe_metadata_value(
            visualization_metadata[key],
            depth=0,
            string_count=string_count,
            node_count=node_count,
        )
        for key in _SAFE_METADATA_FIELDS
        if key in visualization_metadata
    }
    serialized_metadata = json.dumps(safe_metadata, separators=(",", ":"))
    if len(serialized_metadata.encode("utf-8")) > _MAX_METADATA_BYTES:
        raise NemotronProtocolError("Visualization metadata is too large")
    compact_context = {
        "analysis_kind": result.kind.value,
        "summary": result.summary,
        "visualization": safe_metadata,
    }
    request = {
        "model": SETTINGS.nemotron_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Write a brief 2-4 sentence scientific interpretation. Describe only "
                    "what the supplied summary supports; do not imply clinical, causal, "
                    "or experimental validation."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(compact_context, separators=(",", ":")),
            },
        ],
        "max_tokens": 256,
    }
    try:
        response = client.chat.completions.create(**request)  # type: ignore[attr-defined]
    except Exception:
        raise NemotronError("Hosted interpretation failed") from None
    try:
        content = _field(_message(response), "content")
    except NemotronProtocolError:
        raise NemotronError("Hosted interpretation returned no text") from None
    if not isinstance(content, str) or not content.strip():
        raise NemotronError("Hosted interpretation returned no text")
    interpretation = content.strip()
    if len(interpretation) > 2000:
        raise NemotronError("Hosted interpretation returned too much text")
    return interpretation
