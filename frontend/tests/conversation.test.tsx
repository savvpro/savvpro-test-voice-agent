import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiClient } from "../src/api/client";
import { App } from "../src/app/App";
import { view } from "./factories";

describe("caller interface", () => {
  it("opens a conversation and submits a typed description", async () => {
    const fetcher: typeof fetch = async (url, init) => {
      if (String(url).endsWith("/turns")) {
        const body = JSON.parse(String(init?.body)) as { text: string };
        return Response.json(
          view({
            version: 1,
            reply: "What colour is it?",
            transcript: [
              { role: "caller", text: body.text },
              { role: "assistant", text: "What colour is it?" },
            ],
          }),
        );
      }
      return Response.json(view());
    };
    render(<App client={new ApiClient(fetcher)} />);
    await screen.findByText("Tell me what you lost.");
    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "my backpack" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("my backpack")).toBeInTheDocument();
    expect(await screen.findByText("What colour is it?")).toBeInTheDocument();
  });

  it("shows a saved pending claim without claiming ownership", async () => {
    const fetcher: typeof fetch = async () =>
      Response.json(
        view({
          state: "completed",
          receipt: {
            reference: "LF-DEMO",
            kind: "claim",
            status: "pending_review",
          },
        }),
      );
    render(<App client={new ApiClient(fetcher)} />);
    expect(await screen.findByText("LF-DEMO")).toBeInTheDocument();
    expect(screen.getByText("Pending staff review")).toBeInTheDocument();
  });

  it("recovers from a network failure using the original turn identifier", async () => {
    const ids: string[] = [];
    const fetcher: typeof fetch = async (url, init) => {
      if (String(url).endsWith("/turns")) {
        const body = JSON.parse(String(init?.body)) as { request_id: string };
        ids.push(body.request_id);
        if (ids.length === 1) throw new TypeError("network disconnected");
        return Response.json(view({ version: 1, reply: "Recovered safely." }));
      }
      return Response.json(view());
    };
    render(<App client={new ApiClient(fetcher)} />);
    await screen.findByText("Tell me what you lost.");
    fireEvent.change(screen.getByLabelText("Your message"), {
      target: { value: "a bag" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry message" }),
    );
    await waitFor(() => expect(ids).toHaveLength(2));
    expect(ids[0]).toBe(ids[1]);
  });

  it("keeps the technical inspector optional", async () => {
    const fetcher: typeof fetch = async () => Response.json(view());
    render(<App client={new ApiClient(fetcher)} />);
    await screen.findByText("Tell me what you lost.");
    const disclosure = screen.getByText("How the assistant decided");
    expect(disclosure.closest("details")).not.toHaveAttribute("open");
  });
});
