import { afterEach, describe, expect, test, vi } from "vitest";

import {
  resetPersona,
  updatePersona,
  updatePersonality,
  updateSpeakingStyle,
} from "./api";

describe("persona api methods", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("uses PUT for persona update endpoints and POST for reset", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ success: true, profile: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await updatePersona({ name: "小晏" });
    await updatePersonality({ openness: 80 });
    await updateSpeakingStyle({ response_length: "short" });
    await resetPersona();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/persona",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/persona/personality",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/persona/speaking-style",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/persona/reset",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
