import type { components } from "./schema";

export type SessionView = components["schemas"]["SessionView"];
export type TurnRequest = components["schemas"]["TurnRequest"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export class ApiClient {
  private readonly fetcher: typeof fetch;
  private readonly timeout: number;
  constructor(
    fetcher: typeof fetch = (...args) => fetch(...args),
    timeout = 12000,
  ) {
    this.fetcher = fetcher;
    this.timeout = timeout;
  }

  private async request(
    path: string,
    method: string,
    body?: TurnRequest,
  ): Promise<SessionView | undefined> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const response = await this.fetcher(`/api/v1/${path}`, {
        method,
        credentials: "same-origin",
        signal: controller.signal,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        let code = "SERVICE_ERROR",
          message = "The service is unavailable. Please try again.";
        try {
          const data: unknown = await response.json();
          if (
            typeof data === "object" &&
            data &&
            "error" in data &&
            typeof data.error === "object" &&
            data.error
          ) {
            if ("code" in data.error && typeof data.error.code === "string")
              code = data.error.code;
            if (
              "message" in data.error &&
              typeof data.error.message === "string"
            )
              message = data.error.message;
          }
        } catch {
          /* An unstructured response is deliberately replaced with a safe message. */
        }
        throw new ApiError(response.status, code, message);
      }
      if (response.status === 204) return undefined;
      const data: unknown = await response.json();
      if (
        !data ||
        typeof data !== "object" ||
        !("version" in data) ||
        typeof data.version !== "number" ||
        !("transcript" in data) ||
        !Array.isArray(data.transcript)
      ) {
        throw new ApiError(
          502,
          "INVALID_RESPONSE",
          "The service returned an incomplete response. Please retry.",
        );
      }
      return data as SessionView;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (controller.signal.aborted)
        throw new ApiError(
          0,
          "TIMEOUT",
          "The reply took too long. Retry to safely recover the same message.",
        );
      throw new ApiError(
        0,
        "NETWORK_ERROR",
        "Connection interrupted. Retry to safely recover the same message.",
      );
    } finally {
      clearTimeout(timer);
    }
  }

  private async view(
    path: string,
    method: string,
    body?: TurnRequest,
  ): Promise<SessionView> {
    const result = await this.request(path, method, body);
    if (!result)
      throw new ApiError(
        502,
        "INVALID_RESPONSE",
        "The service returned an empty response.",
      );
    return result;
  }
  open(): Promise<SessionView> {
    return this.view("session", "POST");
  }
  get(): Promise<SessionView> {
    return this.view("session", "GET");
  }
  send(body: TurnRequest): Promise<SessionView> {
    return this.view("turns", "POST", body);
  }
  async erase(): Promise<void> {
    await this.request("session", "DELETE");
  }
}

export const api = new ApiClient();
