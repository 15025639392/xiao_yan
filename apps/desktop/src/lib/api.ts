export type BeingState = {
  mode: "awake" | "sleeping";
  current_thought: string | null;
  active_goal_ids: string[];
};

const BASE_URL = "http://127.0.0.1:8000";

async function post(path: string): Promise<BeingState> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }

  return response.json();
}

export function wake(): Promise<BeingState> {
  return post("/lifecycle/wake");
}

export function sleep(): Promise<BeingState> {
  return post("/lifecycle/sleep");
}
