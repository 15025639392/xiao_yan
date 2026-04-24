import { afterEach, expect, test, vi } from "vitest";

import { createVrmGenerationJob, fetchVrmGenerationJob, listVrmGenerationJobs } from "./apiVrmGeneration";

afterEach(() => {
  vi.restoreAllMocks();
});

test("creates and fetches VRM generation jobs", async () => {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/vrm-generation/jobs")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual({ prompt: "小晏，白色居家裙" });
      return new Response(JSON.stringify({ job_id: "job-1", prompt: "小晏，白色居家裙", status: "queued", artifacts: {} }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.endsWith("/vrm-generation/jobs/job-1")) {
      return new Response(JSON.stringify({ job_id: "job-1", prompt: "小晏，白色居家裙", status: "completed", artifacts: { output_vrm_path: "/tmp/out.vrm" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    throw new Error(`unexpected url ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);

  const created = await createVrmGenerationJob({ prompt: "小晏，白色居家裙" });
  expect(created.status).toBe("queued");

  const fetched = await fetchVrmGenerationJob("job-1");
  expect(fetched.status).toBe("completed");
  expect(fetched.artifacts.output_vrm_path).toBe("/tmp/out.vrm");
});


test("lists recent VRM generation jobs", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    expect(url).toContain("/vrm-generation/jobs?limit=3");
    return new Response(JSON.stringify({ items: [{ job_id: "job-1", prompt: "小晏", status: "completed", artifacts: {} }] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }));

  const payload = await listVrmGenerationJobs({ limit: 3 });

  expect(payload.items).toHaveLength(1);
  expect(payload.items[0].job_id).toBe("job-1");
});
