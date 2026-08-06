import type {
  ChatResponse,
  PromptId,
  ProviderStatus,
  SessionResponse,
  StartWorkspaceResponse,
  WorkspaceResetResponse,
} from "./types";

const PROVIDER_STATUSES: ReadonlySet<string> = new Set([
  "unchecked",
  "available",
  "authentication_failed",
  "rate_limited",
  "provider_unavailable",
  "model_unavailable",
  "invalid_response",
]);

function providerStatus(value: unknown): ProviderStatus | undefined {
  return typeof value === "string" && PROVIDER_STATUSES.has(value)
    ? value as ProviderStatus
    : undefined;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly providerStatus?: ProviderStatus,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: init.body ? { "Content-Type": "application/json" } : undefined,
  });
  const body = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    let message = "The request could not be completed.";
    let safeProviderStatus: ProviderStatus | undefined;
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") message = detail;
      if (
        detail &&
        typeof detail === "object" &&
        "message" in detail &&
        typeof (detail as { message: unknown }).message === "string"
      ) {
        message = (detail as { message: string }).message;
      }
      if (detail && typeof detail === "object" && "provider_status" in detail) {
        safeProviderStatus = providerStatus(
          (detail as { provider_status: unknown }).provider_status,
        );
      }
    }
    throw new ApiError(message, response.status, safeProviderStatus);
  }
  return body as T;
}

export function getSession(): Promise<SessionResponse> {
  return request<SessionResponse>("/api/session");
}

export function setSessionKey(apiKey: string): Promise<StartWorkspaceResponse> {
  return request("/api/session/key", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export function resetWorkspace(): Promise<WorkspaceResetResponse> {
  return request("/api/session/reset", { method: "POST" });
}

export function endSession(): Promise<{ authenticated: false }> {
  return request("/api/session", { method: "DELETE" });
}

export function sendSuggestedPrompt(promptId: PromptId): Promise<ChatResponse> {
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ prompt_id: promptId }),
  });
}

export function sendMessage(message: string): Promise<ChatResponse> {
  return request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}
