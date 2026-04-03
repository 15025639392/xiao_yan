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
