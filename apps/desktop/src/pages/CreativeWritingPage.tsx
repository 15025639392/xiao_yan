import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, PenLine, Plus, RefreshCw } from "lucide-react";

import { Button } from "../components/ui";
import {
  BeingContextSummary,
  FragmentList,
  HabitStateEditor,
  PanelTitle,
  ProjectOverview,
  SessionQueue,
} from "../components/creative-writing/CreativeWritingSections";
import {
  createNovelProject,
  createNovelWritingSession,
  executeNovelWritingSession,
  fetchCreativeWritingSnapshot,
  fetchNovelProject,
  updateNovelHabitState,
  type CreativeWritingSnapshot,
  type NovelProject,
  type NovelProjectDetail,
  type UpdateNovelHabitPayload,
  type NovelWritingSession,
} from "../lib/apiCreativeWriting";

type CreativeWritingPageProps = {
  assistantName: string;
};

const EMPTY_SNAPSHOT: CreativeWritingSnapshot = {
  projects: [],
  sessions: [],
  recommended_project_id: null,
  impulses: [],
  being_context: null,
};

export function CreativeWritingPage({ assistantName }: CreativeWritingPageProps) {
  const [snapshot, setSnapshot] = useState<CreativeWritingSnapshot>(EMPTY_SNAPSHOT);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectDetail, setProjectDetail] = useState<NovelProjectDetail | null>(null);
  const [title, setTitle] = useState("");
  const [premise, setPremise] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const next = await fetchCreativeWritingSnapshot();
      setSnapshot(next);
      setSelectedProjectId((current) => current ?? next.recommended_project_id ?? next.projects[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载创作状态失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadProject = useCallback(async (projectId: string | null) => {
    if (!projectId) {
      setProjectDetail(null);
      return;
    }
    try {
      setProjectDetail(await fetchNovelProject(projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载小说项目失败");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadProject(selectedProjectId);
  }, [loadProject, selectedProjectId]);

  const selectedProject = useMemo(
    () => snapshot.projects.find((project) => project.id === selectedProjectId) ?? null,
    [selectedProjectId, snapshot.projects],
  );
  const recommended = useMemo(
    () => snapshot.impulses.find((item) => item.project_id === snapshot.recommended_project_id) ?? null,
    [snapshot.impulses, snapshot.recommended_project_id],
  );
  const pendingSessions = snapshot.sessions.filter((session) => session.status === "pending");

  async function runAction(name: string, action: () => Promise<void>) {
    setBusyAction(name);
    setError("");
    try {
      await action();
      await load();
      await loadProject(selectedProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateProject() {
    if (!title.trim() || !premise.trim()) return;
    await runAction("create-project", async () => {
      const result = await createNovelProject({ title, premise });
      setTitle("");
      setPremise("");
      setSelectedProjectId(result.project.id);
    });
  }

  async function handleCreateSession(projectId?: string) {
    await runAction(`session-${projectId ?? "recommended"}`, async () => {
      const result = await createNovelWritingSession(projectId);
      if (result.session) setSelectedProjectId(result.session.project_id);
    });
  }

  async function handleExecuteSession(session: NovelWritingSession, content?: string) {
    await runAction(`execute-${session.id}`, async () => {
      await executeNovelWritingSession(session.id, { content: content?.trim() || undefined });
      setSelectedProjectId(session.project_id);
    });
  }

  async function handleSaveHabit(project: NovelProject, payload: UpdateNovelHabitPayload) {
    await runAction(`habit-${project.id}`, async () => {
      await updateNovelHabitState(project.id, payload);
    });
  }

  return (
    <div className="creative-page">
      <header className="creative-header">
        <div>
          <h2 className="creative-title">小说创作</h2>
          <p className="creative-subtitle">{assistantName} 的长期创作工作台</p>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={15} />
          刷新
        </Button>
      </header>

      {error ? <div className="creative-error">{error}</div> : null}

      <section className="creative-grid">
        <aside className="creative-rail">
          <section className="creative-panel">
            <PanelTitle icon={<PenLine size={18} />} title="继续写" count={snapshot.impulses.length} />
            {recommended ? (
              <div className="creative-recommendation">
                <strong>{recommended.title}</strong>
                <span>{recommended.suggested_action}</span>
                <BeingContextSummary context={snapshot.being_context} reasons={recommended.reasons} />
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void handleCreateSession(recommended.project_id)}
                  disabled={Boolean(busyAction)}
                >
                  <Plus size={15} />
                  准备会话
                </Button>
              </div>
            ) : (
              <p className="creative-muted">暂无可继续的小说。</p>
            )}
          </section>

          <section className="creative-panel">
            <PanelTitle icon={<BookOpen size={18} />} title="作品" count={snapshot.projects.length} />
            <div className="creative-project-list">
              {snapshot.projects.map((project) => (
                <button
                  key={project.id}
                  type="button"
                  className={`creative-project ${project.id === selectedProjectId ? "creative-project--active" : ""}`}
                  onClick={() => setSelectedProjectId(project.id)}
                >
                  <strong>{project.title}</strong>
                  <span>第 {project.current_chapter_index} 章 · {project.status}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="creative-panel">
            <PanelTitle icon={<Plus size={18} />} title="新作品" />
            <input className="creative-input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="标题" />
            <textarea
              className="creative-textarea"
              value={premise}
              onChange={(event) => setPremise(event.target.value)}
              placeholder="核心前提"
              rows={3}
            />
            <Button type="button" size="sm" onClick={() => void handleCreateProject()} disabled={!title.trim() || !premise.trim() || Boolean(busyAction)}>
              创建
            </Button>
          </section>
        </aside>

        <main className="creative-workspace">
          <ProjectOverview
            project={selectedProject}
            detail={projectDetail}
            onCreateSession={() => selectedProject && void handleCreateSession(selectedProject.id)}
            busy={Boolean(busyAction)}
          />
          <HabitStateEditor project={selectedProject} onSave={handleSaveHabit} busy={Boolean(busyAction)} />
          <SessionQueue sessions={pendingSessions} onExecute={handleExecuteSession} busyAction={busyAction} />
          <FragmentList fragments={projectDetail?.fragments ?? []} />
        </main>
      </section>
    </div>
  );
}
