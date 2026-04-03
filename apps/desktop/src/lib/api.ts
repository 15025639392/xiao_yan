export type BeingState = {
  mode: "awake" | "sleeping";
  current_thought: string | null;
  active_goal_ids: string[];
};

export type ChatResult = {
  response_id: string | null;
  output_text: string;
};

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatHistoryResponse = {
  messages: ChatHistoryMessage[];
};

export type Goal = {
  id: string;
  title: string;
  status: "active" | "paused" | "completed" | "abandoned";
  chain_id?: string | null;
  parent_goal_id?: string | null;
  generation?: number;
};

export type InnerWorldState = {
  time_of_day: "morning" | "afternoon" | "evening" | "night";
  energy: "low" | "medium" | "high";
  mood: "calm" | "engaged" | "tired";
  focus_tension: "low" | "medium" | "high";
  focus_stage?: "none" | "start" | "deepen" | "consolidate";
  focus_step?: number | null;
  latest_event?: string | null;
};

export type GoalsResponse = {
  goals: Goal[];
};

export type AutobioResponse = {
  entries: string[];
};

const BASE_URL = "http://127.0.0.1:8000";

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }

  return response.json();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }

  return response.json();
}

export function wake(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/wake");
}

export function sleep(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/sleep");
}

export function chat(message: string): Promise<ChatResult> {
  return post<ChatResult>("/chat", { message });
}

export function fetchState(): Promise<BeingState> {
  return get<BeingState>("/state");
}

export function fetchMessages(): Promise<ChatHistoryResponse> {
  return get<ChatHistoryResponse>("/messages");
}

export function fetchGoals(): Promise<GoalsResponse> {
  return get<GoalsResponse>("/goals");
}

export function fetchWorld(): Promise<InnerWorldState> {
  return get<InnerWorldState>("/world");
}

export function fetchAutobio(): Promise<AutobioResponse> {
  return get<AutobioResponse>("/autobio");
}

export function updateGoalStatus(
  goalId: string,
  status: Goal["status"],
): Promise<Goal> {
  return post<Goal>(`/goals/${goalId}/status`, { status });
}
