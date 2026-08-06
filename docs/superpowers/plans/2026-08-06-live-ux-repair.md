# Live UX Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make one ephemeral API-key workspace support consecutive nvMolKit/Nemotron analyses while keeping the composer, figures, and valid conformer controls visible, diagnosable, and reproducible through the corrected Brev Launchable.

**Architecture:** Preserve the current single React/FastAPI container and four deterministic analysis functions. Add a typed, secret-safe hosted-provider status to the existing session, separate workspace reset from credential deletion, repair the bounded two-pane layout while retaining one page-lifetime 3Dmol viewer, and add production-CSS Chromium coverage before publishing a new immutable image. Qualify the image first on the confirmed live instance, then update and freshly deploy the Launchable.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, OpenAI-compatible NVIDIA API, React 19, TypeScript 7, Vite 8, Vitest/JSDOM, Playwright/Chromium, Plotly, 3Dmol.js, Docker Compose, GHCR, NVIDIA Brev L4.

---

## File map

Files to create:

- frontend/playwright.config.ts — production-CSS browser-test configuration.
- frontend/e2e/live-ux.spec.ts — visible-layout, sequential-workflow, reset/logout, and conformer-selector acceptance.
- docs/acceptance/2026-08-06-live-ux-repair-receipt.md — exact local, image, live-instance, and Launchable evidence recorded during closeout.

Files to modify:

- backend/app/nemotron.py — typed provider status, safe provider-error classification, and categorized Nemotron failures.
- backend/app/sessions.py — provider status in live server state and reset-without-key-deletion behavior.
- backend/app/main.py — provider-aware responses, safe free-form failures, and POST /api/session/reset.
- tests/test_nemotron.py — provider classification and redaction tests.
- tests/test_sessions.py — reset, expiry, serialization, and key-preservation tests.
- tests/test_api.py — endpoint contract, consecutive-task, reset/logout, provider-status, and route tests.
- frontend/src/types.ts — ProviderStatus and response contracts.
- frontend/src/api.ts — resetWorkspace, endSession, and provider-aware ApiError behavior.
- frontend/src/App.tsx — persistent composer, New analysis, End session, and safe provider notice.
- frontend/src/AdaptiveViewer.tsx — explicit inactive/2D/conformer state and synchronized selectors.
- frontend/src/styles.css — bounded viewport, independent scrolling, and reliable hidden conformer pane.
- frontend/src/App.test.tsx — workspace/session and consecutive-analysis behavior.
- frontend/src/AdaptiveViewer.test.tsx — inactive-pane and selector/style behavior.
- frontend/package.json and frontend/package-lock.json — exact Playwright dependency and browser-test script.
- .github/workflows/publish-image.yml — enforce backend, frontend, and real-browser tests before image publication.
- README.md — corrected workspace/session behavior and verification commands.
- deployment/compose.yaml — Phase B update to the accepted immutable image digest.
- deployment/launchable-fields.md — exact corrected Launchable source, image, and acceptance status.

## Task 0: Establish a clean, low-memory baseline

**Files:** No changes.

- [ ] **Step 1: Confirm source identity and clean state**

Run:

~~~bash
git status --short --branch
git rev-parse HEAD
git log -2 --oneline
~~~

Expected: branch codex/fix-live-nvmolkit-ux-20260806, HEAD is the committed implementation-plan revision, and no uncommitted files.

- [ ] **Step 2: Create the isolated Python environment**

Run:

~~~bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e 'backend[test]'
~~~

Expected: Python 3.12 environment with the backend and test extras installed. Do not install torch or nvMolKit locally on the Mac.

- [ ] **Step 3: Install the locked frontend graph with a task-local npm cache**

Run:

~~~bash
npm --cache /private/tmp/codex-npm-cache-nvmolkit ci --prefix frontend
~~~

Expected: npm completes without writing the root-owned user cache.

- [ ] **Step 4: Run the baseline backend suite**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
~~~

Expected: all non-GPU tests pass and tests/test_gpu_acceptance.py is explicitly skipped.

- [ ] **Step 5: Run the baseline frontend gates one at a time**

Run:

~~~bash
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
~~~

Expected: 19 Vitest tests pass, typecheck passes, and the Vite production build completes.

## Task 1: Add a typed, secret-safe Nemotron provider contract

**Files:**

- Modify: backend/app/nemotron.py
- Modify: tests/test_nemotron.py

- [ ] **Step 1: Write provider classification tests**

Add imports for ProviderStatus and provider_status_for_error, then add:

~~~python
class StatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__("raw provider body with nvapi-secret")
        self.status_code = status_code


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
~~~

- [ ] **Step 2: Update existing redaction tests to require status**

Change selection and interpretation error assertions to require:

~~~python
with pytest.raises(NemotronError) as caught:
    select_analysis(fake, "cluster these molecules")
assert caught.value.provider_status == "provider_unavailable"
assert "nvapi-secret" not in str(caught.value)
~~~

Apply the same pattern to interpretation failures. Update explicit test fixtures from NemotronError("offline") to NemotronError("provider_unavailable", "Hosted provider unavailable").

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_nemotron.py -q
~~~

Expected: collection or assertion failures because ProviderStatus, provider_status_for_error, and the new constructor do not exist.

- [ ] **Step 4: Implement the provider types and errors**

In backend/app/nemotron.py, add:

~~~python
from typing import Any, Literal, TypeAlias

ProviderStatus: TypeAlias = Literal[
    "unchecked",
    "available",
    "authentication_failed",
    "rate_limited",
    "provider_unavailable",
    "model_unavailable",
    "invalid_response",
]


def provider_status_for_error(error: Exception) -> ProviderStatus:
    status_code = getattr(error, "status_code", None)
    if status_code in {401, 403}:
        return "authentication_failed"
    if status_code == 404:
        return "model_unavailable"
    if status_code == 429:
        return "rate_limited"
    return "provider_unavailable"


class NemotronError(RuntimeError):
    def __init__(
        self, provider_status: ProviderStatus, safe_message: str
    ) -> None:
        super().__init__(safe_message)
        self.provider_status = provider_status


class NemotronProtocolError(NemotronError):
    def __init__(self, safe_message: str) -> None:
        super().__init__("invalid_response", safe_message)
~~~

Do not preserve raw provider exception text.

- [ ] **Step 5: Classify provider calls at the source**

Change both hosted call exception blocks to:

~~~python
except Exception as error:
    raise NemotronError(
        provider_status_for_error(error),
        "Hosted analysis selection failed",
    ) from None
~~~

and:

~~~python
except Exception as error:
    raise NemotronError(
        provider_status_for_error(error),
        "Hosted interpretation failed",
    ) from None
~~~

Keep protocol validation as NemotronProtocolError so malformed hosted responses remain invalid_response.

Update every remaining constructor call: missing/blank/oversized interpretation text must raise NemotronProtocolError, and the existing catch around _message must re-raise NemotronProtocolError rather than converting it to an unclassified NemotronError. After this step, no one-argument NemotronError call may remain.

- [ ] **Step 6: Run the focused and backend suites**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_nemotron.py -q
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
~~~

Expected: both commands pass.

- [ ] **Step 7: Commit the provider contract**

Run:

~~~bash
git add backend/app/nemotron.py tests/test_nemotron.py tests/test_api.py
git commit -m "feat: classify hosted provider failures"
~~~

## Task 2: Reset workspace state without deleting credentials

**Files:**

- Modify: backend/app/sessions.py
- Modify: tests/test_sessions.py
- Modify: backend/app/main.py
- Modify: tests/test_api.py

- [ ] **Step 1: Write the SessionStore reset tests**

Add:

~~~python
def test_reset_replaces_analysis_state_but_preserves_key_and_token() -> None:
    engines = iter([object(), object()])
    store = SessionStore(lambda: next(engines))
    token = store.create("nvapi-secret")
    before = store.get(token)
    assert before is not None
    old_engine = before.engine
    before.latest_visualization = {"kind": "similarity"}
    before.provider_status = "available"

    assert store.reset(token) is True

    after = store.get(token)
    assert after is before
    assert after.api_key_value() == "nvapi-secret"
    assert after.engine is not old_engine
    assert after.latest_visualization is None
    assert after.provider_status == "unchecked"


def test_reset_missing_or_expired_session_is_false() -> None:
    clock = Clock()
    store = SessionStore(lambda: object(), clock=clock, idle_seconds=10)
    token = store.create("key")
    clock.now += 11
    assert store.reset(token) is False
    assert store.reset("missing") is False
~~~

Add a threaded test that holds store.lease(token), starts store.reset(token) on another worker, asserts reset remains pending, releases the lease, and then asserts reset succeeds.

- [ ] **Step 2: Run the session tests and verify RED**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_sessions.py -q
~~~

Expected: failures because Session.provider_status and SessionStore.reset do not exist.

- [ ] **Step 3: Add provider state and reset to SessionStore**

Import ProviderStatus from .nemotron. Add this dataclass field:

~~~python
provider_status: ProviderStatus = "unchecked"
~~~

Add:

~~~python
def reset(self, token: str) -> bool:
    with self.lease(token) as session:
        if session is None:
            return False
        engine = self._engine_factory()
        session.engine = engine
        session.latest_visualization = None
        session.provider_status = "unchecked"
        return True
~~~

Creating the replacement engine before assignment ensures a factory exception leaves the prior engine intact.

- [ ] **Step 4: Run the session tests and verify GREEN**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_sessions.py -q
~~~

Expected: all session tests pass.

- [ ] **Step 5: Write API reset and session-contract tests**

Update key/session expectations to include provider_status: "unchecked". Add:

~~~python
def test_reset_preserves_authentication_and_clears_workspace() -> None:
    first = FakeEngine()
    second = FakeEngine()
    client, _, store = _client(
        [first, second], [_completion(content="Ready.")]
    )
    _authenticate(client)
    token = client.cookies["session"]
    assert client.post(
        "/api/chat", json={"prompt_id": "similarity"}
    ).status_code == 200

    response = client.post("/api/session/reset")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "visualization": None,
        "provider_status": "unchecked",
    }
    assert client.cookies["session"] == token
    current = store.get(token)
    assert current is not None
    assert current.api_key_value() == SECRET
    assert current.engine is second
    assert current.latest_visualization is None


def test_reset_requires_a_live_session() -> None:
    client, _, _ = _client([], [])
    assert client.post("/api/session/reset").status_code == 401
~~~

Update the required-route assertion to include /api/session/reset.

- [ ] **Step 6: Run the API tests and verify RED**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_api.py -q
~~~

Expected: response-shape and missing-route failures.

- [ ] **Step 7: Add the reset endpoint and provider status to session responses**

Change the POST /api/session/key return annotation to dict[str, Any] and return:

~~~python
{"authenticated": True, "provider_status": "unchecked"}
~~~

Make GET /api/session return provider_status for authenticated sessions and unchecked for unauthenticated sessions.

Add:

~~~python
@app.post("/api/session/reset")
def reset_session(
    session: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    if not session or not store.reset(session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return {
        "authenticated": True,
        "visualization": None,
        "provider_status": "unchecked",
    }
~~~

- [ ] **Step 8: Run session, API, and full backend suites**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_sessions.py tests/test_api.py -q
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
~~~

Expected: all commands pass.

- [ ] **Step 9: Commit workspace reset**

Run:

~~~bash
git add backend/app/sessions.py backend/app/main.py tests/test_sessions.py tests/test_api.py
git commit -m "feat: reset workspace without deleting key"
~~~

## Task 3: Propagate safe provider status through chat responses

**Files:**

- Modify: backend/app/main.py
- Modify: tests/test_api.py

- [ ] **Step 1: Write suggested-workflow provider tests**

Extend the interpretation-failure test to assert:

~~~python
assert response.json()["provider_status"] == "provider_unavailable"
assert visual["interpretation_unavailable"] is True
assert client.get("/api/session").json()["provider_status"] == "provider_unavailable"
~~~

Add a successful interpretation assertion:

~~~python
assert response.json()["provider_status"] == "available"
assert client.get("/api/session").json()["provider_status"] == "available"
~~~

- [ ] **Step 2: Write free-form failure tests**

Parameterize safe provider failures:

~~~python
@pytest.mark.parametrize(
    ("error", "http_status", "provider_status"),
    [
        (StatusError(401), 401, "authentication_failed"),
        (StatusError(429), 429, "rate_limited"),
        (StatusError(404), 503, "model_unavailable"),
        (RuntimeError("raw nvapi-secret"), 503, "provider_unavailable"),
    ],
)
def test_freeform_provider_failure_is_safe_and_runs_no_chemistry(
    error: Exception, http_status: int, provider_status: str
) -> None:
    engine = FakeEngine()
    client, _, _ = _client([engine], [error])
    _authenticate(client)
    response = client.post("/api/chat", json={"message": "show similarity"})
    assert response.status_code == http_status
    assert response.json()["detail"]["provider_status"] == provider_status
    assert engine.calls == []
    assert SECRET not in response.text
    assert "raw" not in response.text
~~~

Use a local StatusError helper identical to Task 1.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_api.py -q
~~~

Expected: failures because chat responses do not expose or persist provider status.

- [ ] **Step 4: Add safe provider response maps**

In backend/app/main.py, import ProviderStatus and provider_status_for_error. Add exact maps:

~~~python
_PROVIDER_HTTP_STATUS: dict[ProviderStatus, int] = {
    "unchecked": 503,
    "available": 200,
    "authentication_failed": 401,
    "rate_limited": 429,
    "provider_unavailable": 503,
    "model_unavailable": 503,
    "invalid_response": 422,
}

_PROVIDER_MESSAGES: dict[ProviderStatus, str] = {
    "unchecked": "Nemotron has not been checked.",
    "available": "Nemotron is available.",
    "authentication_failed": "Nemotron rejected the API key.",
    "rate_limited": "Nemotron rate-limited the request.",
    "provider_unavailable": "Nemotron is temporarily unavailable.",
    "model_unavailable": "The configured Nemotron model is unavailable.",
    "invalid_response": "Nemotron returned an invalid bounded response.",
}
~~~

Add a helper returning HTTPException with detail containing only message, provider_status, and allowed_prompt_ids for free-form routing.

- [ ] **Step 5: Update provider status inside the session lease**

For free-form selection:

~~~python
except NemotronError as error:
    session.provider_status = error.provider_status
    raise _safe_provider_error(error.provider_status) from None
except Exception as error:
    provider_status = provider_status_for_error(error)
    session.provider_status = provider_status
    raise _safe_provider_error(provider_status) from None
~~~

For interpretation success, set session.provider_status = "available". For NemotronError, persist error.provider_status; for an unexpected exception, persist provider_unavailable. Return:

~~~python
return {
    "visualization": copy.deepcopy(visualization),
    "provider_status": session.provider_status,
}
~~~

- [ ] **Step 6: Run the backend suite**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
~~~

Expected: all tests pass, including secret-redaction assertions.

- [ ] **Step 7: Commit provider-aware chat**

Run:

~~~bash
git add backend/app/main.py tests/test_api.py
git commit -m "feat: expose safe Nemotron status"
~~~

## Task 4: Separate New analysis from End session in the frontend

**Files:**

- Modify: frontend/src/types.ts
- Modify: frontend/src/api.ts
- Modify: frontend/src/App.tsx
- Modify: frontend/src/App.test.tsx
- Modify: frontend/src/styles.css

- [ ] **Step 1: Add typed response-contract tests through App behavior**

Update all authenticated mock responses to include provider_status. Add:

~~~typescript
it("keeps the composer available for consecutive tasks", async () => {
  const fetchMock = mockFetch(
    response({ authenticated: true, visualization: null, provider_status: "unchecked" }),
    response({ visualization: graph, provider_status: "available" }),
    response({ visualization: graph, provider_status: "available" }),
  );
  render(<App />);
  expect(await screen.findByLabelText(/ask about the bundled molecules/i)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: exactPrompts[1] }));
  await screen.findByText(/one self-match/i);
  fireEvent.change(screen.getByLabelText(/ask about the bundled molecules/i), {
    target: { value: "Show molecular groups" },
  });
  fireEvent.click(screen.getByRole("button", { name: /send message/i }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(screen.getByLabelText(/ask about the bundled molecules/i)).toBeVisible();
});
~~~

Add a New analysis test asserting POST /api/session/reset, retained authentication, cleared result, and no API-key field. Rename the existing logout test to End session and keep its DELETE assertion.

- [ ] **Step 2: Run App tests and verify RED**

Run:

~~~bash
npm --prefix frontend test -- --run src/App.test.tsx
~~~

Expected: failures for missing provider_status handling, New analysis, End session, and persistent composer behavior.

- [ ] **Step 3: Add frontend provider types**

In frontend/src/types.ts add:

~~~typescript
export type ProviderStatus =
  | "unchecked"
  | "available"
  | "authentication_failed"
  | "rate_limited"
  | "provider_unavailable"
  | "model_unavailable"
  | "invalid_response";
~~~

Add provider_status to SessionResponse and ChatResponse. Add:

~~~typescript
export interface WorkspaceResetResponse {
  authenticated: true;
  visualization: null;
  provider_status: "unchecked";
}
~~~

Also add a typed StartWorkspaceResponse with authenticated: true and provider_status, and use it as the setSessionKey return type.

- [ ] **Step 4: Make ApiError provider-aware and add reset/end functions**

Change ApiError to accept optional providerStatus. Parse detail.provider_status only when it is one of the allowed literal values. Add:

~~~typescript
export function resetWorkspace(): Promise<WorkspaceResetResponse> {
  return request("/api/session/reset", { method: "POST" });
}

export function endSession(): Promise<{ authenticated: false }> {
  return request("/api/session", { method: "DELETE" });
}
~~~

Remove clearSession.

- [ ] **Step 5: Implement the App workspace actions**

Add providerStatus state initialized to unchecked and update it from GET session, key submission, chat responses, and ApiError.

Add:

~~~typescript
async function newAnalysis() {
  if (busy) return;
  setBusy(true);
  setError(null);
  try {
    const reset = await resetWorkspace();
    setAuthenticated(reset.authenticated);
    setProviderStatus(reset.provider_status);
    setVisualization(null);
    setFigureContext(null);
    setFailedRequest(null);
    setChatStarted(false);
    setEntries([]);
    setMessage("");
  } catch (caught) {
    if (caught instanceof ApiError && caught.providerStatus) {
      setProviderStatus(caught.providerStatus);
    }
    setError(caught instanceof Error ? caught.message : "The analysis workspace could not be reset.");
  } finally {
    setBusy(false);
  }
}
~~~

Rename logout to endWorkspaceSession and keep the credential-deleting behavior. Change Start session to Start workspace.

Render two header actions:

~~~tsx
<div className="session-actions">
  <button type="button" onClick={() => void newAnalysis()} disabled={busy}>
    New analysis
  </button>
  <button type="button" onClick={() => void endWorkspaceSession()} disabled={busy}>
    End session
  </button>
</div>
~~~

Keep the chat form rendered for every authenticated state, not only after chat starts.

- [ ] **Step 6: Add safe provider notices**

Map non-available states to fixed UI text:

~~~typescript
const PROVIDER_MESSAGES: Record<ProviderStatus, string | null> = {
  unchecked: "Nemotron will be checked on the first hosted request.",
  available: null,
  authentication_failed: "Nemotron rejected the API key. End the session and enter a valid key.",
  rate_limited: "Nemotron rate-limited the request. Try again later.",
  provider_unavailable: "Nemotron is temporarily unavailable.",
  model_unavailable: "The configured Nemotron model is unavailable.",
  invalid_response: "Nemotron returned an invalid bounded response.",
};
~~~

Render only this fixed text; never render raw provider response bodies.

- [ ] **Step 7: Run frontend unit and type gates**

Run:

~~~bash
npm --prefix frontend test -- --run src/App.test.tsx
npm --prefix frontend run typecheck
~~~

Expected: both pass.

- [ ] **Step 8: Commit workspace UX**

Run:

~~~bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/styles.css
git commit -m "feat: separate reset from session end"
~~~

## Task 5: Repair viewer visibility, layout, and selector behavior

**Files:**

- Modify: frontend/src/AdaptiveViewer.tsx
- Modify: frontend/src/AdaptiveViewer.test.tsx
- Modify: frontend/src/styles.css

- [ ] **Step 1: Expand the conformer fixture to two molecules**

Add CHEMBL2 with one conformer, add CHEMBL2 to selectors.molecule_ids, and map it in conformer_ids_by_molecule. Keep CHEMBL1 with two conformers.

- [ ] **Step 2: Write inactive-pane and selector tests**

Add or strengthen:

~~~typescript
it("removes the inactive conformer pane from layout for a 2D figure", () => {
  render(<AdaptiveViewer visualization={similarity} />);
  const pane = document.querySelector(".conformer-pane");
  expect(pane).toHaveAttribute("hidden");
  expect(pane).not.toHaveClass("is-active");
  expect(screen.queryByRole("combobox", { name: /molecule/i })).not.toBeInTheDocument();
  expect(screen.getByRole("figure", { name: /pairwise molecular similarity/i })).toBeVisible();
});

it("populates and applies every conformer control", () => {
  render(<AdaptiveViewer visualization={conformers} />);
  expect(document.querySelector(".conformer-pane")).toHaveClass("is-active");
  expect(screen.getAllByRole("option", { name: /CHEMBL/i })).toHaveLength(2);
  fireEvent.change(screen.getByLabelText(/molecule/i), {
    target: { value: "CHEMBL2" },
  });
  expect(screen.getByLabelText(/^conformer$/i)).toHaveValue("CHEMBL2:0");
  fireEvent.change(screen.getByLabelText(/rendering style/i), {
    target: { value: "sphere" },
  });
  expect(viewer.setStyle).toHaveBeenLastCalledWith(
    {},
    { sphere: { colorscheme: "Jmol", scale: 0.32 } },
  );
});
~~~

Add a rerender test for conformer -> 2D -> conformer that asserts createViewer is called exactly once and the retained viewer receives the second conformer payload.

- [ ] **Step 3: Run viewer tests and verify RED where CSS/layout behavior is missing**

Run:

~~~bash
npm --prefix frontend test -- --run src/AdaptiveViewer.test.tsx
~~~

Expected: selector fixture assertions fail until the payload and state are synchronized. JSDOM may still pass hidden visibility, which is why Task 6 adds Chromium proof.

- [ ] **Step 4: Make viewer state explicit**

Keep PersistentConformerPane mounted, but give it an explicit active class and hidden state:

~~~tsx
<section
  className={visualization ? "conformer-pane is-active" : "conformer-pane"}
  hidden={!visualization}
  aria-hidden={!visualization}
  ...
>
~~~

Give option elements explicit values. Keep the existing effects that choose the first molecule and first conformer after a new payload.

- [ ] **Step 5: Repair the desktop layout CSS**

Add:

~~~css
html,
body,
#root {
  height: 100%;
}

body {
  overflow: hidden;
}

.app-shell {
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
}

.chat-pane,
.viewer-pane {
  min-height: 0;
  overflow: hidden;
}

.conversation {
  min-height: 0;
}

.viewer-pane {
  display: flex;
  flex-direction: column;
}

.viewer-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.conformer-pane[hidden] {
  display: none;
}
~~~

Replace viewport-derived minimum heights inside viewer-content with 100% or content-sized values so an inactive child cannot increase the grid height. Style session-actions as a compact accessible button group.

- [ ] **Step 6: Preserve mobile stacking**

Inside the existing max-width 800px media query, restore document scrolling and bounded sections:

~~~css
body {
  overflow: auto;
}

.app-shell {
  height: auto;
  min-height: 100dvh;
  overflow: visible;
}

.chat-pane {
  min-height: 100dvh;
}

.viewer-pane,
.viewer-content {
  min-height: 72dvh;
  overflow: visible;
}
~~~

- [ ] **Step 7: Run all frontend unit gates**

Run:

~~~bash
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
~~~

Expected: all pass.

- [ ] **Step 8: Commit viewer and layout repair**

Run:

~~~bash
git add frontend/src/AdaptiveViewer.tsx frontend/src/AdaptiveViewer.test.tsx frontend/src/styles.css
git commit -m "fix: keep figures and composer visible"
~~~

## Task 6: Add production-CSS Chromium regression coverage

**Files:**

- Create: frontend/playwright.config.ts
- Create: frontend/e2e/live-ux.spec.ts
- Modify: frontend/package.json
- Modify: frontend/package-lock.json

- [ ] **Step 1: Install the exact Playwright test dependency**

Run:

~~~bash
npm --cache /private/tmp/codex-npm-cache-nvmolkit --prefix frontend install --save-dev --save-exact @playwright/test@1.62.1
~~~

Expected: package.json and package-lock.json add @playwright/test 1.62.1.

- [ ] **Step 2: Add the browser-test script**

Add:

~~~json
"preview": "vite preview",
"test:e2e": "npm run build && playwright test"
~~~

Keep test mapped to Vitest so the Dockerfile's existing npm test command remains a unit-test gate.

- [ ] **Step 3: Add Playwright configuration**

Create frontend/playwright.config.ts:

~~~typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
~~~

- [ ] **Step 4: Add deterministic API fixtures in the browser test**

Create frontend/e2e/live-ux.spec.ts with graph and two-molecule conformer payloads matching frontend/src/types.ts. Add a route helper that:

- returns authenticated true, visualization null, provider_status unchecked for GET /api/session;
- returns the requested graph or conformer response for POST /api/chat;
- returns authenticated true, visualization null, provider_status unchecked for POST /api/session/reset;
- returns authenticated false for DELETE /api/session.

Every response must use application/json and status 200.

- [ ] **Step 5: Add the visible 2D-layout test**

The test must use viewport 1563 by 1103, matching the supplied screenshots. Assert:

~~~typescript
await expect(page.getByLabel("Ask about the bundled molecules")).toBeInViewport();
await page.getByRole("button", {
  name: "Map structural similarity across the bundled dataset.",
}).click();
await expect(page.getByRole("figure", {
  name: /Pairwise molecular similarity/,
})).toBeInViewport();
await expect(page.getByLabel("Molecule")).toHaveCount(0);
await expect(page.locator(".conformer-pane")).toHaveCSS("display", "none");
~~~

Also assert documentElement.scrollHeight is no greater than innerHeight on desktop.

- [ ] **Step 6: Add conformer and session-action tests**

For a conformer response, assert two molecule options, selectable conformers, a visible molecule canvas, and a visible energy plot. Change molecule, conformer, and style and assert the selected values.

In the same page, exercise conformer -> 2D -> conformer. Save the first molecule-canvas DOM node on window after the initial conformer response and assert the identical node is reactivated after the 2D response; the unit test in Task 5 supplies the exact createViewer call-count proof.

Run one graph request, click New analysis, assert the key field is absent and the figure is cleared, then click End session and assert the masked key field is visible.

- [ ] **Step 7: Add the narrow-screen test**

Use viewport 390 by 844. Assert the composer is visible within the chat section, the page can scroll to the viewer, and a returned graph is visible after scrolling without conformer controls.

- [ ] **Step 8: Install Chromium and run the browser suite**

Run:

~~~bash
cd frontend
npx playwright install chromium
npm run test:e2e
~~~

Expected: all Chromium tests pass with one worker. Run no other heavy command concurrently.

- [ ] **Step 9: Commit browser regression coverage**

Run:

~~~bash
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts frontend/e2e/live-ux.spec.ts
git commit -m "test: cover live UX in Chromium"
~~~

## Task 7: Enforce verification before image publication

**Files:**

- Modify: .github/workflows/publish-image.yml
- Modify: README.md

- [ ] **Step 1: Add a verify job before publish**

Use the existing pinned checkout action. Add pinned:

- actions/setup-node at 820762786026740c76f36085b0efc47a31fe5020 with node-version 24 and npm caching against frontend/package-lock.json.
- actions/setup-python at 5fda3b95a4ea91299a34e894583c3862153e4b97 with python-version 3.12 and pip caching against backend/pyproject.toml.

The job runs, in order:

~~~bash
python -m pip install -e 'backend[test]'
python -m pytest tests -m 'not gpu' -ra
npm ci --prefix frontend
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
~~~

Set the existing publish job to need verify. Keep workflow_dispatch as the only trigger and preserve current GHCR permissions.

- [ ] **Step 2: Validate workflow structure**

Run:

~~~bash
backend/.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/publish-image.yml')); print('workflow yaml ok')"
~~~

Expected: workflow yaml ok.

- [ ] **Step 3: Update README behavior and commands**

Document:

- Start workspace stores but does not pre-validate the key.
- Consecutive tasks do not require reset.
- New analysis preserves the key and resets analysis state.
- End session deletes the key.
- npm run test:e2e is the production-CSS browser gate.
- Live and fresh-Launchable qualification remain required before claiming the repair complete.

- [ ] **Step 4: Run packaging regression tests**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_packaging.py -q
git diff --check
~~~

Expected: packaging tests and whitespace check pass.

- [ ] **Step 5: Commit verification enforcement**

Run:

~~~bash
git add .github/workflows/publish-image.yml README.md
git commit -m "ci: gate image on browser acceptance"
~~~

## Task 8: Run the complete local acceptance gate

**Files:**

- Create: docs/acceptance/2026-08-06-live-ux-repair-receipt.md

- [ ] **Step 1: Run backend acceptance**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
backend/.venv/bin/python -m compileall -q backend/app tests
~~~

Expected: all non-GPU tests pass, the GPU gate is explicitly skipped, and byte-compilation succeeds.

- [ ] **Step 2: Run frontend acceptance one command at a time**

Run:

~~~bash
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:e2e
~~~

Expected: unit, type, build, and Chromium gates all pass.

- [ ] **Step 3: Validate Compose and repository state**

Run:

~~~bash
docker compose -f deployment/compose.yaml config --quiet
git diff --check
git status --short
~~~

Expected: Compose and diff checks pass; only the new receipt is uncommitted.

- [ ] **Step 4: Run targeted secret scans without printing matches**

Use count-only scans for NVIDIA-key-shaped strings and API-key assignments across tracked files and all reachable commits. If any count is nonzero, inspect only the file paths, confirm fixtures, and stop before publication if a real credential is present.

Expected: zero confirmed credentials.

- [ ] **Step 5: Write the local portion of the acceptance receipt**

Record exact UTC start/end times, branch, commit, tool versions, every command above, pass/fail counts, Chromium viewport coverage, secret-scan counts, and all remaining image/GPU/Nemotron/Brev/Launchable gates as not_run.

- [ ] **Step 6: Commit the local acceptance receipt**

Run:

~~~bash
git add docs/acceptance/2026-08-06-live-ux-repair-receipt.md
git commit -m "docs: record local live UX acceptance"
~~~

## Task 9: Publish the Phase A immutable image

**Files:** No source changes until the workflow returns a digest.

- [ ] **Step 1: Review the exact publish scope**

Run:

~~~bash
git status --short --branch
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
~~~

Expected: only approved repair, test, workflow, README, design, plan, and receipt commits.

- [ ] **Step 2: Stop for external-write approval**

Show the user the exact branch, commit list, diff stat, public repository target, and one proposed workflow run. Obtain explicit approval before push or workflow dispatch.

- [ ] **Step 3: Push the reviewed branch**

After approval:

~~~bash
git push -u origin codex/fix-live-nvmolkit-ux-20260806
~~~

Expected: the public branch points to the reviewed local HEAD.

- [ ] **Step 4: Dispatch exactly one image workflow**

Run:

~~~bash
gh workflow run publish-image.yml --ref codex/fix-live-nvmolkit-ux-20260806
gh run list --workflow publish-image.yml --branch codex/fix-live-nvmolkit-ux-20260806 --limit 1
~~~

Record the single run ID. Do not retry automatically.

- [ ] **Step 5: Watch and read back the workflow**

Run gh run watch against the exact run ID, then gh run view for the conclusion and job logs. Expected: verify and publish succeed exactly once.

- [ ] **Step 6: Record immutable identity**

Read the workflow output and GHCR manifest. Record:

- source commit SHA;
- OCI index digest;
- linux/amd64 manifest digest;
- compressed size;
- workflow run URL.

- [ ] **Step 7: Inspect image metadata without exposing environment values**

Inspect the immutable image history, layer/build metadata, configured user, entrypoint, and environment variable *names*. Scan count-only across image history and extracted application/build artifacts for NVIDIA-key-shaped values. Do not print environment values. Stop if any confirmed credential is present.

Do not call the image runtime-qualified.

## Task 10: Pin Phase B Compose and deployment metadata

**Files:**

- Modify: deployment/compose.yaml
- Modify: deployment/launchable-fields.md
- Modify: README.md
- Modify: docs/acceptance/2026-08-06-live-ux-repair-receipt.md

- [ ] **Step 1: Replace only the Compose image digest**

Change services.app.image to the exact OCI index digest returned by Task 9. Preserve TRITON_CACHE_DIR, port 8000, one NVIDIA GPU reservation, and the existing health check.

- [ ] **Step 2: Update Launchable fields**

Record the exact image build commit, workflow run, OCI index, linux/amd64 digest, architecture, L4 requirement, 50 GiB storage, port 8000 Secure Link, and no public TCP/UDP ports. Mark live runtime and fresh deployment pending.

- [ ] **Step 3: Re-run focused packaging gates**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests/test_packaging.py -q
docker compose -f deployment/compose.yaml config --quiet
git diff --check
~~~

Expected: all pass.

- [ ] **Step 4: Commit Phase B metadata**

Run:

~~~bash
git add deployment/compose.yaml deployment/launchable-fields.md README.md docs/acceptance/2026-08-06-live-ux-repair-receipt.md
git commit -m "deploy: pin corrected live UX image"
~~~

- [ ] **Step 5: Review and obtain approval before the second push**

Show the exact four-file diff and commit. Push only after explicit approval.

## Task 11: Read-only preflight on the confirmed live instance

**Files:** No local changes until evidence is recorded.

- [ ] **Step 1: Re-verify Brev CLI and organization without switching**

Run:

~~~bash
/opt/homebrew/bin/brev --version
/opt/homebrew/bin/brev exec --help
/opt/homebrew/bin/brev ls --help
/opt/homebrew/bin/brev org ls --no-check-latest
/opt/homebrew/bin/brev ls --org agents-in-ls --json --no-check-latest
~~~

Expected: active organization agents-in-ls and exact instance he8b2ekuh is RUNNING, COMPLETED, READY, HEALTHY, L4. Abort if any identity differs. Do not run brev set, refresh, login, or logout.

- [ ] **Step 2: Verify remote namespaces read-only**

Against the exact instance name, run one bounded command that prints:

- whoami and pwd;
- /home/ubuntu/workspace path ownership and mount identity;
- docker compose ls --format json;
- docker ps with container ID, name, image, status, ports, Compose project, working directory, and config-file labels;
- nvidia-smi -L and a query of GPU UUID, name, memory, and active compute applications;
- curl of http://127.0.0.1:8000/api/health.

Do not print environment variables, inspect container environment, read credentials, or inspect unrelated file contents.

- [ ] **Step 3: Resolve the exact mutation target**

From Step 2, record the application container, Compose project, Compose file, working directory, active image digest, service port, GPU UUID, and whether any other controller/process shares the instance.

- [ ] **Step 4: Stop for interruption approval**

Show the resolved exact target, expected interruption, rollback copy path, proposed image digest, and current hourly cost. Obtain explicit approval before pulling or recreating the application container.

## Task 12: Update and qualify only the live application container

**Files:**

- Modify after evidence: docs/acceptance/2026-08-06-live-ux-repair-receipt.md

- [ ] **Step 1: Preserve the exact prior Compose file**

After interruption approval, create a timestamped backup beside the verified task-owned Compose file and record its SHA-256. Do not alter unrelated services or directories.

- [ ] **Step 2: Pull the exact Phase A image digest**

Use docker pull with the immutable GHCR digest from Task 9. Verify RepoDigests contains that exact digest before Compose mutation.

- [ ] **Step 3: Replace only the app service**

Write the reviewed Phase B Compose content to the verified task-owned Compose file and run docker compose up -d --no-deps app from the verified Compose project. Do not run docker compose down, docker system prune, or any host-global cleanup.

- [ ] **Step 4: Verify runtime identity and readiness**

Read back the container ID, image RepoDigest, health status, port 8000, process user, and GPU access. Poll /api/health until ready or the bounded timeout expires. On failure, preserve logs and restore the exact backup; do not retry an image replacement automatically.

- [ ] **Step 5: Run the real GPU acceptance gate**

Inside the accepted immutable container, run only the repository's explicit tests/test_gpu_acceptance.py gate or its packaged equivalent. Expected: all four AnalysisKind paths use CUDA/nvMolKit and return finite valid visualization payloads.

- [ ] **Step 6: Run Secure Link browser acceptance**

Using a user-entered masked NVIDIA API key, verify in one session:

1. composer visible before work;
2. fingerprint figure visible;
3. similarity figure visible;
4. cluster figure visible;
5. conformer dropdowns populated and selections change the model/style;
6. one free-form request routes through Nemotron;
7. a safe unsupported request;
8. New analysis preserves authentication and clears work;
9. End session deletes authentication.

Never capture or record the key.

- [ ] **Step 7: Inspect secret-redacted logs and close the receipt**

Record pass/fail, exact image/container/GPU identity, safe provider status, browser results, and zero confirmed credentials. Keep the prior backup until the user closes the rollback window.

## Task 13: Correct and freshly qualify the Brev Launchable

**Files:**

- Modify: deployment/launchable-fields.md
- Modify: docs/acceptance/2026-08-06-live-ux-repair-receipt.md

- [ ] **Step 1: Push the approved Phase B commit**

After explicit approval, push the exact Phase B commit and verify its remote SHA with git ls-remote.

- [ ] **Step 2: Prepare the exact Console update**

Provide the user the commit-pinned raw deployment/compose.yaml URL from the Phase B commit. The user updates Launchable env-3HVH6EJJaIzVc6RYjBqUoYmw1gu in the Brev Console because no supported callable authoring interface is exposed.

- [ ] **Step 3: Read back the public Launchable**

Verify that the deploy page resolves the Phase B Compose URL and accepted image digest, one L4, x86_64, 50 GiB storage, Secure Link port 8000, and no public TCP/UDP ports.

- [ ] **Step 4: Stop for fresh-deployment cost approval**

Re-read current provider/SKU availability and displayed hourly price. Obtain explicit authorization for exactly one fresh deployment, its name, maximum hourly price, runtime window, and stop/delete authority. Do not infer this approval from the existing running instance.

- [ ] **Step 5: Deploy once and repeat critical acceptance**

Deploy exactly once. Verify exact organization, Launchable ID, instance ID, provider, SKU, source commit, Compose URL, and image digest. Repeat the nine Secure Link checks from Task 12.

- [ ] **Step 6: Finalize repository evidence**

Update Launchable fields and the receipt with exact fresh-deployment evidence. Mark only gates actually run as pass; keep unrun release/security/scientific gates explicit.

- [ ] **Step 7: Run final verification and commit**

Run:

~~~bash
backend/.venv/bin/python -m pytest tests -m 'not gpu' -ra
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:e2e
docker compose -f deployment/compose.yaml config --quiet
git diff --check
~~~

Expected: all local gates pass after evidence-only edits.

- [ ] **Step 8: Review branch completion**

Run:

~~~bash
git status --short --branch
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
~~~

Use the finishing-development-branch workflow to present merge/pull-request options. Do not merge, force-push, stop, or delete Brev resources without the corresponding explicit approval.
