const API = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(20_000),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Could not reach VoxDesk. Check that the backend is running. If this was a sent message, retry it to safely retrieve the outcome.",
      0,
    );
  }
  const result = await response.json();
  if (!response.ok) {
    const detail =
      typeof result.detail === "string"
        ? result.detail
        : "That request could not be processed. Check your input and try again.";
    throw new ApiError(detail, response.status);
  }
  return result as T;
}
