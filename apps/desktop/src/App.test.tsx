import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders wake and sleep controls", () => {
  render(<App />);
  expect(screen.getByText("Wake")).toBeInTheDocument();
  expect(screen.getByText("Sleep")).toBeInTheDocument();
});

test("sends a chat message and renders the assistant reply", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "hello xiao yan" }));
      return new Response(
        JSON.stringify({
          response_id: "resp_123",
          output_text: "hello human",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    return new Response(
      JSON.stringify({
        mode: "sleeping",
        current_thought: null,
        active_goal_ids: [],
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  fireEvent.change(screen.getByLabelText("Chat Input"), {
    target: { value: "hello xiao yan" },
  });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(screen.getByText("You: hello xiao yan")).toBeInTheDocument();
    expect(screen.getByText("Xiao Yan: hello human")).toBeInTheDocument();
  });
});
