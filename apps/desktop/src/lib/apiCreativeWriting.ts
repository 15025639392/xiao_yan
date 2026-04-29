import { get, patch, post } from "./apiClient";

export type NovelHabitState = {
  attachment_reason: string;
  last_pause: string;
  next_intention: string;
  cadence_note: string;
  updated_at: string;
};

export type NovelProject = {
  id: string;
  title: string;
  premise: string;
  tone: string;
  habit_note: string;
  habit_state: NovelHabitState;
  current_chapter_index: number;
  status: "drafting" | "paused" | "finished";
  folder_name: string;
  created_at: string;
  updated_at: string;
};

export type NovelFragmentDigest = {
  summary: string;
  next_intention: string;
  should_advance_chapter: boolean;
  chapter_closure_reason: string;
};

export type NovelFragment = {
  id: string;
  project_id: string;
  chapter_index: number;
  sequence: number;
  content: string;
  summary: string;
  digest: NovelFragmentDigest | null;
  file_path: string;
  created_at: string;
};

export type NovelWritingContext = {
  project_id: string;
  chapter_index: number;
  previous_chapter_summaries: string[];
  recent_summaries: string[];
  recent_excerpt: string;
};

export type NovelWritingSession = {
  id: string;
  project_id: string;
  title: string;
  intention: string;
  suggested_action: string;
  reasons: string[];
  context: NovelWritingContext;
  status: "pending" | "cancelled" | "completed";
  completed_fragment_id: string | null;
  created_at: string;
  updated_at: string;
};

export type NovelWritingImpulse = {
  project_id: string;
  title: string;
  score: number;
  reasons: string[];
  next_intention: string;
  suggested_action: string;
};

export type BeingWritingContext = {
  time_of_day: string;
  energy: string;
  mood: string;
  focus_tension: string;
  primary_emotion: string;
  primary_intensity: string;
  mood_valence: number;
  arousal: number;
};

export type CreativeWritingSnapshot = {
  projects: NovelProject[];
  sessions: NovelWritingSession[];
  recommended_project_id: string | null;
  impulses: NovelWritingImpulse[];
  being_context: BeingWritingContext | null;
};

export type NovelProjectDetail = {
  project: NovelProject;
  fragments: NovelFragment[];
  chapter_summaries: Array<{
    id: string;
    project_id: string;
    chapter_index: number;
    title: string;
    summary: string;
    file_path: string;
    created_at: string;
  }>;
};

export type CreateNovelProjectPayload = {
  title: string;
  premise: string;
  tone?: string;
};

export type UpdateNovelHabitPayload = {
  attachment_reason?: string;
  last_pause?: string;
  next_intention?: string;
  cadence_note?: string;
};

export type ExecuteNovelWritingSessionPayload = {
  content?: string;
  summary?: string;
};

export async function fetchCreativeWritingSnapshot(): Promise<CreativeWritingSnapshot> {
  const [projectsResult, sessionsResult, impulsesResult] = await Promise.all([
    get<{ projects: NovelProject[] }>("/creative-writing/projects"),
    get<{ sessions: NovelWritingSession[] }>("/creative-writing/sessions"),
    get<{
      recommended_project_id: string | null;
      impulses: NovelWritingImpulse[];
      being_context: BeingWritingContext | null;
    }>("/creative-writing/impulses"),
  ]);
  return {
    projects: projectsResult.projects,
    sessions: sessionsResult.sessions,
    recommended_project_id: impulsesResult.recommended_project_id,
    impulses: impulsesResult.impulses,
    being_context: impulsesResult.being_context,
  };
}

export function fetchNovelProject(projectId: string): Promise<NovelProjectDetail> {
  return get<NovelProjectDetail>(`/creative-writing/projects/${encodeURIComponent(projectId)}`);
}

export function createNovelProject(payload: CreateNovelProjectPayload): Promise<{ project: NovelProject }> {
  return post<{ project: NovelProject }>("/creative-writing/projects", payload);
}

export function createNovelWritingSession(projectId?: string): Promise<{ session: NovelWritingSession | null }> {
  if (projectId) {
    return post<{ session: NovelWritingSession | null }>(
      `/creative-writing/projects/${encodeURIComponent(projectId)}/sessions`,
      {},
    );
  }
  return post<{ session: NovelWritingSession | null }>("/creative-writing/sessions", {});
}

export function executeNovelWritingSession(
  sessionId: string,
  payload: ExecuteNovelWritingSessionPayload = {},
): Promise<{
  session: NovelWritingSession;
  fragment: NovelFragment;
}> {
  return post(`/creative-writing/sessions/${encodeURIComponent(sessionId)}/execute`, payload);
}

export function updateNovelHabitState(
  projectId: string,
  payload: UpdateNovelHabitPayload,
): Promise<{ project: NovelProject }> {
  return patch(`/creative-writing/projects/${encodeURIComponent(projectId)}/habit`, payload);
}
