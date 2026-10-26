import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/api/client";
import { view } from "./factories";

describe("API boundary", () => {
  it("uses the public same-origin session endpoint", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json(view()));
    const result = await new ApiClient(fetcher).open();
    expect(result.state).toBe("collecting");
    expect(fetcher.mock.calls[0]?.[0]).toBe("/api/v1/session");
    expect(fetcher.mock.calls[0]?.[1]?.credentials).toBe("same-origin");
  });

  it("preserves the complete request identity when retrying", async () => {
    const bodies: unknown[] = [];
    const fetcher: typeof fetch = async (_url, init) => {
      bodies.push(JSON.parse(String(init?.body)));
      return Response.json(view({ version: 1 }));
    };
    const client = new ApiClient(fetcher);
    const payload = {
      text: "black bag",
      request_id: "fixture-request",
      expected_version: 0,
    };
    await client.send(payload);
    await client.send(payload);
    expect(bodies).toEqual([payload, payload]);
  });

  it("maps safe errors without exposing server internals", async () => {
    const fetcher: typeof fetch = async () =>
      Response.json(
        {
          error: {
            code: "VERSION_CONFLICT",
            message: "Refresh and try again.",
            request_id: "request",
          },
        },
        { status: 409 },
      );
    await expect(new ApiClient(fetcher).get()).rejects.toMatchObject({
      status: 409,
      code: "VERSION_CONFLICT",
      message: "Refresh and try again.",
    });
  });

  it("handles deletion without parsing an empty response", async () => {
    const fetcher: typeof fetch = async () =>
      new Response(null, { status: 204 });
    await expect(new ApiClient(fetcher).erase()).resolves.toBeUndefined();
  });

  it("turns unstructured server errors into a useful generic message", async () => {
    const fetcher: typeof fetch = async () =>
      new Response("internal SQL", { status: 503 });
    await expect(new ApiClient(fetcher).get()).rejects.toBeInstanceOf(ApiError);
    await expect(new ApiClient(fetcher).get()).rejects.not.toThrow(
      "internal SQL",
    );
  });

  it("aborts a timed-out request while allowing an identical retry", async () => {
    const fetcher: typeof fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    await expect(new ApiClient(fetcher, 5).open()).rejects.toMatchObject({
      code: "TIMEOUT",
    });
  });
});
