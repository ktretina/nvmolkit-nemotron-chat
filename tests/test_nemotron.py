from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.models import AnalysisKind, AnalysisResult
from app.nemotron import (
    TOOL_SCHEMAS,
    NemotronError,
    NemotronProtocolError,
    ProviderStatus,
    interpret_result,
    parse_analysis_call,
    provider_status_for_error,
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


class StatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__("raw provider body with nvapi-secret")
        self.status_code = status_code


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
        completion(call(arguments='{"fingerprint_radius": 2.0}')),
        completion(call(arguments='{"fingerprint_size": 2048.0}')),
        completion(call(arguments='{"fingerprint_radius": true}')),
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
    assert request["tool_choice"] == "required"
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


def test_select_rejects_none_message_with_safe_protocol_error() -> None:
    fake = client()

    with pytest.raises(NemotronProtocolError):
        select_analysis(fake, None)  # type: ignore[arg-type]

    assert fake.chat.completions.requests == []


def test_select_redacts_client_error() -> None:
    fake = client(error=RuntimeError("request failed for nvapi-secret"))

    with pytest.raises(NemotronError) as caught:
        select_analysis(fake, "cluster these molecules")

    assert caught.value.provider_status == "provider_unavailable"
    assert "nvapi-secret" not in str(caught.value)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (StatusError(401), "authentication_failed"),
        (StatusError(403), "authentication_failed"),
        (StatusError(404), "model_unavailable"),
        (StatusError(429), "rate_limited"),
        (StatusError(500), "provider_unavailable"),
        (TimeoutError("nvapi-secret"), "provider_unavailable"),
        (RuntimeError("nvapi-secret"), "provider_unavailable"),
    ],
)
def test_provider_errors_map_to_safe_status(
    error: Exception, expected: ProviderStatus
) -> None:
    assert provider_status_for_error(error) == expected


def test_protocol_error_is_always_invalid_response_and_secret_safe() -> None:
    error = NemotronProtocolError("Hosted response violated the bounded protocol")

    assert error.provider_status == "invalid_response"
    assert "nvapi-" not in str(error)


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


def test_interpretation_rejects_non_label_fields_nested_under_labels() -> None:
    fake = client()

    with pytest.raises(NemotronProtocolError):
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

    assert fake.chat.completions.requests == []


@pytest.mark.parametrize(
    "labels",
    [
        {"x": [[1.0, 0.2], [0.2, 1.0]]},
        {"x": ["Molecule ID", 3]},
        {"x": {"title": {"text": {"label": "too deep"}}}},
        {"x": [f"label-{index}" for index in range(65)]},
        {"x": "x" * 201},
        {"label" + "x" * 201: "Molecule ID"},
        {"labelfoo": "Molecule ID"},
        {"unkindness": "heatmap"},
        {"x": []},
        {"x": [[] for _ in range(100_000)]},
        {"x": [f"label-{index}" for index in range(33)]},
        {"x": None},
        {"x": True},
    ],
)
def test_interpretation_rejects_noncompact_nontextual_labels_before_client_call(
    labels: object,
) -> None:
    fake = client()

    with pytest.raises(NemotronProtocolError):
        interpret_result(
            fake,
            AnalysisResult(
                kind=AnalysisKind.SIMILARITY, summary={"mean": 0.5}, artifact={}
            ),
            {"kind": "heatmap", "labels": labels},
        )

    assert fake.chat.completions.requests == []


def test_interpretation_preserves_bounded_textual_label_metadata() -> None:
    fake = client(completion(content="A bounded interpretation."))

    interpret_result(
        fake,
        AnalysisResult(kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}),
        {
            "kind": "bar",
            "labels": {
                "x": "Cluster ID",
                "y": "Molecule count",
                "legend_label": ["Cluster", "Representative"],
            },
        },
    )

    payload = json.dumps(fake.chat.completions.requests[0])
    assert "Cluster ID" in payload
    assert "Molecule count" in payload
    assert "Representative" in payload


def test_interpretation_accepts_container_and_payload_boundaries() -> None:
    fake = client(completion(content="A bounded interpretation."))
    boundary_labels = [f"label-{index}" for index in range(32)]
    near_byte_limit = ["x" * 200 for _ in range(20)]

    interpret_result(
        fake,
        AnalysisResult(kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}),
        {
            "kind": "bar",
            "labels": {
                "legend_label": boundary_labels,
                "x_label": near_byte_limit,
            },
        },
    )

    assert len(fake.chat.completions.requests) == 1


def test_interpretation_rejects_oversized_serialized_metadata_before_client() -> None:
    fake = client()
    long_labels = ["x" * 200 for _ in range(25)]

    with pytest.raises(NemotronProtocolError):
        interpret_result(
            fake,
            AnalysisResult(
                kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}
            ),
            {
                "kind": "bar",
                "labels": {
                    "x_label": long_labels,
                    "y_label": long_labels,
                },
            },
        )

    assert fake.chat.completions.requests == []


def test_interpretation_request_caps_provider_output_tokens() -> None:
    fake = client(completion(content="A bounded interpretation."))

    interpret_result(
        fake,
        AnalysisResult(kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}),
        {"kind": "bar", "x_label": "Cluster ID"},
    )

    assert fake.chat.completions.requests[0]["max_tokens"] == 256


def test_interpretation_rejects_oversized_returned_text() -> None:
    fake = client(completion(content="x" * 2001))

    with pytest.raises(NemotronProtocolError) as caught:
        interpret_result(
            fake,
            AnalysisResult(
                kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}
            ),
            {"kind": "bar"},
        )

    assert caught.value.provider_status == "invalid_response"


def test_interpretation_accepts_2000_character_returned_text() -> None:
    fake = client(completion(content="x" * 2000))

    interpretation = interpret_result(
        fake,
        AnalysisResult(kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}),
        {"kind": "bar"},
    )

    assert len(interpretation) == 2000


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
    with pytest.raises(NemotronProtocolError) as caught:
        interpret_result(
            client(response),
            AnalysisResult(
                kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}
            ),
            {"kind": "bar", "labels": {"y": "Molecule count"}},
        )

    assert caught.value.provider_status == "invalid_response"


def test_interpretation_redacts_client_error() -> None:
    with pytest.raises(NemotronError) as caught:
        interpret_result(
            client(error=RuntimeError("nvapi-secret")),
            AnalysisResult(
                kind=AnalysisKind.CLUSTERS, summary={"count": 2}, artifact={}
            ),
            {"kind": "bar"},
        )

    assert caught.value.provider_status == "provider_unavailable"
    assert "nvapi-secret" not in str(caught.value)
