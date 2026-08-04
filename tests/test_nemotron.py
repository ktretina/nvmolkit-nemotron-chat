from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.models import AnalysisKind, AnalysisResult
from app.nemotron import (
    TOOL_SCHEMAS,
    NemotronError,
    NemotronProtocolError,
    interpret_result,
    parse_analysis_call,
    select_analysis,
)


TOOL_KINDS = {
    "analyze_fingerprint_density": AnalysisKind.FINGERPRINT_DENSITY,
    "analyze_similarity_map": AnalysisKind.SIMILARITY,
    "analyze_cluster_distribution": AnalysisKind.CLUSTERS,
    "analyze_representative_conformers": AnalysisKind.CONFORMERS,
}


def completion(*calls: object, content: object = None) -> object:
    message = SimpleNamespace(tool_calls=list(calls), content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def call(
    name: str = "analyze_similarity_map",
    arguments: object = "{}",
    *,
    call_id: str = "call-1",
    call_type: str = "function",
) -> object:
    return SimpleNamespace(
        id=call_id,
        type=call_type,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeCompletions:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def client(response: object = None, error: Exception | None = None) -> object:
    return SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions(response, error))
    )


@pytest.mark.parametrize(("name", "kind"), TOOL_KINDS.items())
def test_parse_maps_each_tool_to_exact_analysis_kind(
    name: str, kind: AnalysisKind
) -> None:
    selection = parse_analysis_call(completion(call(name)))

    assert selection.kind is kind
    assert selection.call_id == "call-1"
    assert selection.params.fingerprint_radius == 2
    assert "fallback" not in repr(selection).lower()


@pytest.mark.parametrize(
    "bad_completion",
    [
        completion(),
        completion(call(), call(call_id="call-2")),
        completion(call(call_type="custom")),
        completion(call(name="unknown")),
        completion(call(call_id="")),
        completion(call(arguments="not-json")),
        completion(call(arguments="[]")),
        completion(call(arguments='{"extra": 1}')),
        completion(call(arguments='{"cluster_cutoff": 0.61}')),
        completion(call(arguments='{"representative_count": 2}')),
    ],
)
def test_parse_rejects_invalid_or_unbounded_tool_calls(bad_completion: object) -> None:
    with pytest.raises(NemotronProtocolError):
        parse_analysis_call(bad_completion)


def test_tool_schemas_are_exactly_four_strict_parameter_schemas() -> None:
    assert [schema["function"]["name"] for schema in TOOL_SCHEMAS] == list(TOOL_KINDS)
    for schema in TOOL_SCHEMAS:
        parameters = schema["function"]["parameters"]
        assert parameters["additionalProperties"] is False
        assert set(parameters["properties"]) == {
            "fingerprint_radius",
            "fingerprint_size",
            "cluster_cutoff",
            "representative_count",
            "conformers_per_molecule",
        }


def test_select_sends_only_bounded_message_and_four_tools() -> None:
    secret = "nvapi-secret"
    fake = client(completion(call("analyze_cluster_distribution")))

    selection = select_analysis(fake, "  compare molecular clusters  ")

    assert selection.kind is AnalysisKind.CLUSTERS
    request = fake.chat.completions.requests[0]
    assert len(request["tools"]) == 4
    assert request["tool_choice"] in ("auto", "required")
    payload = json.dumps(request)
    assert "compare molecular clusters" in payload
    assert secret not in payload
    assert "coordinates" not in payload.lower()
    assert "tensor" not in payload.lower()


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
def test_select_rejects_invalid_message_without_calling_client(message: str) -> None:
    fake = client()

    with pytest.raises(ValueError):
        select_analysis(fake, message)

    assert fake.chat.completions.requests == []


def test_select_redacts_client_error() -> None:
    fake = client(error=RuntimeError("request failed for nvapi-secret"))

    with pytest.raises(NemotronError) as caught:
        select_analysis(fake, "cluster these molecules")

    assert "nvapi-secret" not in str(caught.value)


def test_interpretation_payload_uses_summary_and_safe_labels_only() -> None:
    fake = client(completion(content="  Two compact clusters are visible.  "))
    result = AnalysisResult(
        kind=AnalysisKind.SIMILARITY,
        summary={"mean_similarity": 0.42},
        artifact={
            "secret": "artifact-secret-sentinel",
            "matrix": [[1.0, 0.2], [0.2, 1.0]],
            "coordinates": [[0.0, 1.0, 2.0]],
        },
    )

    text = interpret_result(
        fake,
        result,
        {
            "kind": "heatmap",
            "labels": {"x": "Molecule ID", "y": "Molecule ID"},
            "matrix": [["full-matrix-sentinel"]],
            "coordinates": ["coordinate-sentinel"],
        },
    )

    assert text == "Two compact clusters are visible."
    payload = json.dumps(fake.chat.completions.requests[0])
    assert "mean_similarity" in payload
    assert "Molecule ID" in payload
    assert "heatmap" in payload
    assert "artifact-secret-sentinel" not in payload
    assert "full-matrix-sentinel" not in payload
    assert "coordinate-sentinel" not in payload


def test_interpretation_filters_non_label_data_nested_under_labels() -> None:
    fake = client(completion(content="A bounded interpretation."))

    interpret_result(
        fake,
        AnalysisResult(
            kind=AnalysisKind.SIMILARITY, summary={"mean": 0.5}, artifact={}
        ),
        {
            "kind": "heatmap",
            "labels": {
                "x_label": "Molecule ID",
                "coordinates": ["nested-coordinate-sentinel"],
                "matrix": [["nested-matrix-sentinel"]],
            },
        },
    )

    payload = json.dumps(fake.chat.completions.requests[0])
    assert "Molecule ID" in payload
    assert "nested-coordinate-sentinel" not in payload
    assert "nested-matrix-sentinel" not in payload


@pytest.mark.parametrize(
    "response",
    [
        completion(content=""),
        completion(content="   "),
        completion(content=None),
        SimpleNamespace(choices=[]),
    ],
)
def test_interpretation_rejects_blank_or_missing_content(response: object) -> None:
    with pytest.raises(NemotronError):
        interpret_result(
            client(response),
            AnalysisResult(
                kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}
            ),
            {"kind": "bar", "labels": {"y": "Molecule count"}},
        )


def test_interpretation_redacts_client_error() -> None:
    with pytest.raises(NemotronError) as caught:
        interpret_result(
            client(error=RuntimeError("nvapi-secret")),
            AnalysisResult(
                kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}
            ),
            {"kind": "bar"},
        )

    assert "nvapi-secret" not in str(caught.value)
