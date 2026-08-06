# nvMolKit Nemotron Chat Live UX Repair Design

**Date:** 2026-08-06  
**Status:** Approved in conversation; written-spec review pending  
**Repository:** `ktretina/nvmolkit-nemotron-chat`  
**Source baseline:** `e879390549d35fd4c6bf6a27c4064551cb6721e7`  
**Local branch:** `codex/fix-live-nvmolkit-ux-20260806`  
**Live target:** Brev organization `agents-in-ls`, instance `nvmolkit-nemotron-chat-72c7f3`, instance ID `he8b2ekuh`

## 1. Objective

Repair the existing focused nvMolKit/Nemotron application so one ephemeral API-key session supports consecutive analyses, keeps the chat composer visible, displays each validated 2D or 3D result in the visible viewer, and provides safe, actionable Nemotron failure states.

This is a state-management, layout, observability, and deployment repair. It does not change the four bounded scientific workflows, accept arbitrary data, add persistence, or expand the scientific claim boundary.

## 2. Evidence and root causes

The August 6 screenshots and source inspection establish these facts:

1. Fingerprint and similarity requests complete successfully. The UI advances to the correct analysis-function header and adds the message “The figure is ready,” which occurs only after `/api/chat` returns a validated visualization.
2. The retained conformer component is mounted for all viewer states with the HTML `hidden` attribute, but `.conformer-pane { display: grid; }` overrides the browser's hidden presentation. The empty conformer pane therefore appears above 2D Plotly figures and pushes them below the visible viewport.
3. The same oversized grid stretches the chat column and pushes the composer, request status, and compact validated-analysis menu below the visible viewport.
4. Molecule and conformer controls are empty outside a conformer result because they belong to the incorrectly visible inactive conformer pane. Rendering style appears populated because it has static options.
5. “Clear session” calls `DELETE /api/session`, deletes the server session and API key, clears the secure cookie, and intentionally returns to the key screen. The control's behavior is logout behavior, not a workspace reset.
6. API-key submission accepts and stores any nonblank string; it does not verify hosted Nemotron connectivity. Provider, authentication, model, rate-limit, network, and protocol failures are currently collapsed into “interpretation unavailable.” The exact live provider failure category must be established from secret-safe diagnostics before changing provider behavior.
7. The live Launchable definition points to Compose revision `da32093a86f578493cea6276771ec039c4854af1` and image index `sha256:0931542cde79aa9d64438c7b720aa80adacb8ab328ab585af5b3b717937f5afb`. Repository `main` already points to a later compiler-equipped image, so fixing only the running container would not fix future Launchable deployments.

## 3. Product behavior

### 3.1 Ephemeral credential workspace

The initial masked `NVIDIA_API_KEY` form remains. Submission creates an in-memory server session and an opaque `Secure`, `HttpOnly`, `SameSite=Strict` cookie. The key is never returned to the browser, stored in browser storage, written to disk, or included in application logs.

The key-entry action is labeled **Start workspace**, not “login,” because session creation does not prove that the hosted provider has accepted the key. The workspace begins with provider status `unchecked`. The first hosted request updates that status to `available` or a safe failure category.

### 3.2 Consecutive work

The user can run any number of suggested or free-form analyses in one live session without clearing the workspace. The four validated workflows remain available after the first request through a compact menu, and the free-form composer remains visible at all times.

Requests within one session remain serialized. A busy workspace disables reset, end-session, prompt, and send controls until the current request completes.

### 3.3 New analysis versus end session

Replace the ambiguous **Clear session** action with two explicit actions:

- **New analysis:** Calls `POST /api/session/reset`, preserves the same session token and API key, replaces the analysis engine with a fresh engine, clears the latest visualization and server-side analysis state, and resets the visible chat/workspace state.
- **End session:** Calls the existing `DELETE /api/session`, deletes the server session and key, removes the cookie, clears the UI, and returns to the key-entry screen.

Reload after **New analysis** must remain authenticated and must not restore the cleared result. Reload after **End session** must require the key again.

### 3.4 Visible chat composer

On desktop, the app occupies exactly the dynamic viewport height. The chat pane and viewer pane scroll independently. The conversation region is the flexible, scrollable element; the compact workflow menu, request status, error message, composer, and scientific-boundary note remain visible at the bottom of the chat pane.

On narrow screens, chat stacks above the viewer. The composer remains visible within the chat section, and each section has a bounded minimum height without forcing unrelated content off-screen.

### 3.5 Viewer states

The viewer has four explicit states:

1. **Empty:** Show the scientific-viewer placeholder. Do not show molecule, conformer, or rendering-style controls.
2. **2D result:** Show the Plotly fingerprint, similarity, or cluster figure immediately below the result header. Do not show conformer controls or an empty molecular canvas.
3. **Conformer result:** Show populated Molecule, Conformer, and Rendering style controls; the active 3Dmol model; atom legend; XYZ triad; and labeled energy plot.
4. **Retained valid result after failure:** Keep the preceding result visible and label it with both the successful request and the failed later request.

The page-lifetime 3Dmol viewer remains mounted to prevent repeated observer/listener construction, but its inactive pane must be reliably hidden with an explicit active/hidden class contract that real-browser tests exercise. Switching molecule, conformer, or rendering style must produce an observable viewer update.

## 4. Backend API and state design

### 4.1 Workspace reset endpoint

Add `POST /api/session/reset`.

Successful response:

```json
{
  "authenticated": true,
  "visualization": null,
  "provider_status": "unchecked"
}
```

The operation acquires the session lease, creates a new `AnalysisEngine` through the existing engine factory, clears `latest_visualization`, and resets safe provider status. It preserves the API key, cookie, and session token. A missing or expired session returns `401 Authentication required`.

### 4.2 Session response

`GET /api/session` returns authentication state, the latest visualization, and a safe provider status. Allowed provider states are:

- `unchecked`
- `available`
- `authentication_failed`
- `rate_limited`
- `provider_unavailable`
- `model_unavailable`
- `invalid_response`

No response includes raw provider exceptions, request bodies, credentials, provider response bodies, or stack traces.

### 4.3 Hosted Nemotron failure mapping

Extend the bounded Nemotron adapter to classify failures from typed/status-bearing provider exceptions without copying raw error text. The backend records only the category in the in-memory session.

- Suggested workflows still return a valid deterministic figure when interpretation fails. The response includes `interpretation_unavailable: true` and the safe provider category.
- Free-form routing requires Nemotron. A provider failure returns a safe error with the matching category and does not execute a fallback analysis.
- Protocol failures remain distinct from provider connectivity failures and occur before GPU execution when routing is invalid.

The implementation must preserve `timeout=30.0`, `max_retries=0`, bounded output tokens, exact four-tool routing, and current secret-redaction behavior.

## 5. Frontend component boundaries

Changes remain focused in the existing modules:

- `frontend/src/App.tsx`: workspace actions, persistent composer, provider-status display, and consecutive-analysis state.
- `frontend/src/api.ts`: reset request and typed safe errors.
- `frontend/src/types.ts`: session/provider status and response types.
- `frontend/src/AdaptiveViewer.tsx`: explicit empty/2D/conformer visibility contract and synchronized selector state.
- `frontend/src/styles.css`: bounded viewport, independent scrolling, reliable hidden conformer pane, and responsive behavior.
- Existing frontend tests plus a real-browser regression suite: user-visible behavior and computed-layout coverage.

Do not add global state management, routing, persistence, analytics, or a component-library migration.

## 6. Verification design

### 6.1 Frontend unit tests

Tests must establish:

- The composer is present before and after the first analysis.
- Multiple suggested and free-form requests use the same authenticated session.
- **New analysis** calls the reset endpoint, clears visible work, and does not show the key form.
- **End session** deletes the session and shows the key form.
- Empty and 2D states do not expose conformer controls.
- A conformer payload populates molecule and conformer options.
- Changing molecule, conformer, and rendering style calls the viewer with different active content or style.
- A later failed request retains the preceding valid figure.
- Safe provider categories render without raw provider text or credential material.

### 6.2 Backend tests

Tests must establish:

- Reset preserves the session token and key while replacing analysis state.
- Reset serializes with an active request and cannot mutate an expired session.
- End session still deletes all credential-bearing state.
- Consecutive requests remain serialized per session and independent across sessions.
- Each provider failure class maps to exactly one safe category.
- Suggested workflows preserve valid figures when interpretation fails.
- Free-form provider failures execute no chemistry function.
- All validation errors and logs remain secret-safe.

### 6.3 Real-browser regression tests

Use Chromium with production CSS and mocked deterministic API payloads. At minimum, test desktop viewports matching the supplied screenshots and one narrow viewport.

- The composer and send button are within the visible chat pane without page scrolling.
- A 2D figure is within the visible viewer region immediately after the response.
- The inactive conformer pane has computed `display: none` and contributes no layout height.
- Conformer controls appear only for a conformer payload and contain selectable options.
- Changing each selector updates the 3D viewer.
- Repeated 3D → 2D → 3D transitions keep one page-lifetime 3Dmol viewer.

JSDOM-only visibility tests are insufficient because they did not apply the production CSS cascade that caused the live failure.

### 6.4 Local and container gates

Before publication:

1. Backend unit suite passes, including the explicit skipped GPU gate when `RUN_GPU_TESTS` is unset.
2. Frontend unit suite, typecheck, production build, and real-browser suite pass.
3. Docker Compose parses successfully.
4. The new Linux/amd64 image builds from the reviewed commit and is recorded by immutable OCI index and platform-manifest digests.
5. Targeted tracked-file, Git-history, build-input, container-history, log, and generated-output scans find no credential.

## 7. Live qualification and rollout

### 7.1 Control-plane boundary

The user confirmed `agents-in-ls / nvmolkit-nemotron-chat-72c7f3 / he8b2ekuh` as the intended live target. This confirms identity but does not by itself prove exclusive control, the remote Compose path, container name, process namespace, or interruption authority.

Before remote access or mutation, perform a read-only preflight that verifies the exact instance, remote user, workspace path, Compose project, active image digest, exposed port, GPU identity, and current service health. Container replacement requires explicit interruption approval after those exact targets are shown. Stop, reset, delete, organization switching, credential refresh, and creation of another billable instance remain outside this approval.

### 7.2 Qualification sequence

After local acceptance and publication of the reviewed immutable image:

1. Update only the task-owned application container on the confirmed live instance, preserving the prior Compose file for rollback.
2. Verify the exact new image digest, CUDA/PyTorch/nvMolKit readiness, health endpoint, and GPU execution.
3. Through the Secure Link, run fingerprint, similarity, cluster, and conformer workflows consecutively under one API-key session.
4. Verify visible labeled figures; populated, functioning conformer controls; a permanently visible composer; one successful free-form Nemotron route; safe unsupported-request behavior; **New analysis**; and **End session**.
5. Inspect secret-redacted logs and outputs.
6. Record a bounded acceptance receipt. Preserve the prior container until the rollback window is closed; do not delete it automatically.

### 7.3 Launchable correction

Hot-updating the current instance is not sufficient. Once the corrected image passes live qualification:

1. Commit a digest-pinned Compose file referencing the accepted image.
2. Update the Brev Launchable in the Console to the exact commit-pinned Compose URL.
3. Read back the Launchable definition and verify the Compose URL, image digest, L4 hardware, 50 GiB storage, and Secure Link on port `8000`.
4. Perform one fresh deployment only with explicit cost and lifecycle approval.
5. Repeat the critical browser acceptance checks on that fresh deployment before calling the Launchable corrected.

## 8. Completion boundary

The repair is complete only when:

- Local unit, build, container, browser, and secret gates pass.
- The confirmed live instance runs the accepted immutable image and passes all four workflows plus free-form routing, reset, logout, selector, and figure-visibility checks.
- The Brev Launchable references the accepted Compose revision and image digest.
- One fresh Launchable deployment passes the critical acceptance flow.

A healthy process, a successful API response hidden below the viewport, a locally passing JSDOM test, or a hot-patched existing container alone does not satisfy completion.

## 9. Out of scope

- Persisting API keys, chat history, figures, or analysis state across backend restarts.
- Arbitrary analyses, tools, uploads, datasets, or code execution.
- Scientific claims beyond computational fingerprints, similarity, clustering, and conformer outputs.
- Production multi-user scaling, databases, queues, analytics, accounts, or role management.
- Automatic stopping, resetting, deleting, or replacing unrelated Brev resources.
- Release-ready security, benchmarking, or scientific-validation claims.
