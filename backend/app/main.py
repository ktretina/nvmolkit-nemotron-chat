"""Minimal, secret-safe FastAPI transport for the bounded chemistry workflow."""

from __future__ import annotations

import asyncio
import copy
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeAlias

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

if TYPE_CHECKING:
    AnalysisEngine: TypeAlias = Any
    AnalysisKind: TypeAlias = Any
    AnalysisParameters: TypeAlias = Any
    AnalysisResult: TypeAlias = Any
    SessionStore: TypeAlias = Any
    NvMolKitRuntime: Any
    SETTINGS: Any
    NemotronError: Any
    interpret_result: Any
    select_analysis: Any
    build_cluster_chart: Any
    build_conformer_bundle: Any
    build_fingerprint_histogram: Any
    build_similarity_heatmap: Any
else:
    from .chemistry import AnalysisEngine, NvMolKitRuntime
    from .config import SETTINGS
    from .models import AnalysisKind, AnalysisParameters, AnalysisResult
    from .nemotron import NemotronError, interpret_result, select_analysis
    from .sessions import SessionStore
    from .visualizations import (
        build_cluster_chart,
        build_conformer_bundle,
        build_fingerprint_histogram,
        build_similarity_heatmap,
    )


PromptId = Literal["fingerprints", "similarity", "clusters", "conformers"]
NonBlankKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]
NonBlankMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]

_PROMPT_KINDS: dict[PromptId, AnalysisKind] = {
    "fingerprints": AnalysisKind.FINGERPRINT_DENSITY,
    "similarity": AnalysisKind.SIMILARITY,
    "clusters": AnalysisKind.CLUSTERS,
    "conformers": AnalysisKind.CONFORMERS,
}
_ALLOWED_PROMPT_IDS = tuple(_PROMPT_KINDS)
_BUILDERS: dict[AnalysisKind, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    AnalysisKind.FINGERPRINT_DENSITY: build_fingerprint_histogram,
    AnalysisKind.SIMILARITY: build_similarity_heatmap,
    AnalysisKind.CLUSTERS: build_cluster_chart,
    AnalysisKind.CONFORMERS: build_conformer_bundle,
}


class ApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    api_key: NonBlankKey


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prompt_id: PromptId | None = None
    message: NonBlankMessage | None = None

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "ChatRequest":
        if (self.prompt_id is None) == (self.message is None):
            raise ValueError("provide exactly one of prompt_id or message")
        return self


def _production_engine() -> AnalysisEngine:
    return AnalysisEngine(NvMolKitRuntime(SETTINGS.data_path))


def _production_nemotron_client(api_key: str) -> object:
    # Keep both the dependency and credential-bound client out of import-time work.
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url="https://integrate.api.nvidia.com/v1")


def _production_readiness() -> dict[str, bool]:
    checks = {"cuda": False, "pytorch": False, "nvmolkit": False}
    try:
        import torch  # type: ignore

        checks["pytorch"] = True
        checks["cuda"] = bool(torch.cuda.is_available())
    except Exception:
        pass
    try:
        import nvmolkit  # type: ignore[import-not-found]  # noqa: F401

        checks["nvmolkit"] = True
    except Exception:
        pass
    return checks


def _safe_capability_detail() -> dict[str, Any]:
    return {
        "message": "Request must select one supported molecular analysis.",
        "allowed_prompt_ids": list(_ALLOWED_PROMPT_IDS),
    }


def _safe_capability_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=_safe_capability_detail(),
    )


def _visualize(result: AnalysisResult) -> dict[str, Any]:
    builder = _BUILDERS[result.kind]
    return builder(copy.deepcopy(result.artifact))


def _textual_metadata(visualization: Mapping[str, Any]) -> dict[str, Any]:
    if visualization.get("kind") == AnalysisKind.CONFORMERS.value:
        graph = visualization.get("energy_plot")
    else:
        graph = visualization
    if not isinstance(graph, Mapping):
        raise ValueError("visualization graph is unavailable")
    layout = graph.get("layout")
    if not isinstance(layout, Mapping):
        raise ValueError("visualization labels are unavailable")

    def title(container: object) -> str | None:
        if not isinstance(container, Mapping):
            return None
        value = container.get("text")
        return value if isinstance(value, str) and value else None

    metadata: dict[str, Any] = {"kind": str(visualization["kind"])}
    graph_title = title(layout.get("title"))
    x_label = (
        title(layout.get("xaxis", {}).get("title"))
        if isinstance(layout.get("xaxis"), Mapping)
        else None
    )
    y_label = (
        title(layout.get("yaxis", {}).get("title"))
        if isinstance(layout.get("yaxis"), Mapping)
        else None
    )
    if graph_title:
        metadata["title"] = graph_title
    if x_label:
        metadata["x_label"] = x_label
    if y_label:
        metadata["y_label"] = y_label
    data = graph.get("data")
    if isinstance(data, list) and data and isinstance(data[0], Mapping):
        colorbar = data[0].get("colorbar")
        if isinstance(colorbar, Mapping):
            colorbar_label = title(colorbar.get("title"))
            if colorbar_label:
                metadata["colorbar_label"] = colorbar_label
    if result_units := _units_from_labels(metadata):
        metadata["units"] = result_units
    return metadata


def _units_from_labels(metadata: Mapping[str, Any]) -> str | None:
    labels = " ".join(
        value for value in metadata.values() if isinstance(value, str)
    ).lower()
    if "kcal/mol" in labels:
        return "kcal/mol"
    if "tanimoto" in labels or "unitless" in labels:
        return "unitless"
    return None


def _execute_chat(
    token: str,
    request: ChatRequest,
    store: SessionStore,
    client_factory: Callable[[str], object],
) -> dict[str, Any]:
    with store.lease(token) as session:
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        client: object | None = None
        if request.prompt_id is not None:
            kind = _PROMPT_KINDS[request.prompt_id]
            params = AnalysisParameters()
        else:
            try:
                client = client_factory(session.api_key_value())
                selection = select_analysis(client, request.message or "")
            except Exception:
                raise _safe_capability_error() from None
            kind = selection.kind
            params = selection.params
        try:
            result = session.engine.run(kind, params)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chemistry runtime is unavailable.",
            ) from None
        try:
            visualization = _visualize(result)
            metadata = _textual_metadata(visualization)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Analysis result could not be visualized.",
            ) from None

        try:
            if client is None:
                client = client_factory(session.api_key_value())
            interpretation = interpret_result(client, result, metadata)
            unavailable = False
        except NemotronError:
            interpretation = None
            unavailable = True
        except Exception:
            interpretation = None
            unavailable = True
        visualization["interpretation"] = interpretation
        visualization["interpretation_unavailable"] = unavailable
        # This is the only promotion point: analysis and visualization are valid.
        session.latest_visualization = copy.deepcopy(visualization)
        return {"visualization": copy.deepcopy(visualization)}


def create_app(
    *,
    session_store: SessionStore | None = None,
    nemotron_client_factory: Callable[[str], object] | None = None,
    readiness: Callable[[], Mapping[str, Any] | bool] | None = None,
    executor_factory: Callable[[], Executor] | None = None,
    frontend_dist: str | Path | None = None,
) -> FastAPI:
    """Assemble the app without initializing CUDA, nvMolKit, or hosted clients."""

    store = session_store or SessionStore(_production_engine)
    client_factory = nemotron_client_factory or _production_nemotron_client
    readiness_callable = readiness or _production_readiness
    make_executor = executor_factory or partial(
        ThreadPoolExecutor, max_workers=8, thread_name_prefix="api-work"
    )
    executor: Executor | None = None
    executor_lock = threading.Lock()
    readiness_lock = threading.Lock()
    readiness_cache: dict[str, bool] | None = None

    def get_executor() -> Executor:
        nonlocal executor
        with executor_lock:
            if executor is None:
                executor = make_executor()
            return executor

    def cached_readiness() -> dict[str, bool]:
        nonlocal readiness_cache
        with readiness_lock:
            if readiness_cache is None:
                try:
                    raw = readiness_callable()
                    if isinstance(raw, bool):
                        readiness_cache = {
                            name: raw for name in ("cuda", "pytorch", "nvmolkit")
                        }
                    elif isinstance(raw, Mapping):
                        readiness_cache = {
                            name: raw.get(name) is True
                            for name in ("cuda", "pytorch", "nvmolkit")
                        }
                    else:
                        readiness_cache = {
                            name: False for name in ("cuda", "pytorch", "nvmolkit")
                        }
                except Exception:
                    readiness_cache = {
                        name: False for name in ("cuda", "pytorch", "nvmolkit")
                    }
            return dict(readiness_cache)

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default includes rejected input values, which may be a credential.
        if request.url.path == "/api/chat":
            return JSONResponse(
                status_code=422, content={"detail": _safe_capability_detail()}
            )
        return JSONResponse(status_code=422, content={"detail": "Invalid request."})

    @app.post("/api/session/key")
    def set_session_key(request: ApiKeyRequest, response: Response) -> dict[str, bool]:
        token = store.create(request.api_key)
        response.set_cookie(
            "session",
            token,
            max_age=3600,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )
        return {"authenticated": True}

    @app.get("/api/session")
    def get_session(session: Annotated[str | None, Cookie()] = None) -> dict[str, Any]:
        if not session:
            return {"authenticated": False, "visualization": None}
        with store.lease(session) as current:
            if current is None:
                return {"authenticated": False, "visualization": None}
            return {
                "authenticated": True,
                "visualization": copy.deepcopy(current.latest_visualization),
            }

    @app.delete("/api/session")
    def delete_session(
        response: Response, session: Annotated[str | None, Cookie()] = None
    ) -> dict[str, bool]:
        if session:
            store.delete(session)
        response.delete_cookie(
            "session", httponly=True, secure=True, samesite="strict", path="/"
        )
        return {"authenticated": False}

    @app.post("/api/chat")
    async def chat(
        request: ChatRequest, session: Annotated[str | None, Cookie()] = None
    ) -> dict[str, Any]:
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            get_executor(),
            partial(_execute_chat, session, request, store, client_factory),
        )

    @app.get("/api/health")
    async def health() -> JSONResponse:
        loop = asyncio.get_running_loop()
        checks = await loop.run_in_executor(get_executor(), cached_readiness)
        dependencies_ready = all(checks.values())
        process_ready = True
        ready = process_ready and dependencies_ready
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "process": {"ready": process_ready},
                "dependencies": {
                    "ready": dependencies_ready,
                    "checks": checks,
                },
                "ready": ready,
            },
        )

    def close_executor() -> None:
        if executor is not None:
            executor.shutdown(wait=True)

    app.add_event_handler("shutdown", close_executor)

    dist = (
        Path(frontend_dist)
        if frontend_dist is not None
        else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    )
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
