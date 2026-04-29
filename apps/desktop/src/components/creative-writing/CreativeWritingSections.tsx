import { useEffect, useState, type ReactNode } from "react";
import { Check, FileText, Heart, Plus } from "lucide-react";

import { Button } from "../ui";
import type {
  BeingWritingContext,
  NovelFragment,
  NovelHabitState,
  NovelProject,
  NovelProjectDetail,
  NovelWritingSession,
  UpdateNovelHabitPayload,
} from "../../lib/apiCreativeWriting";

export function PanelTitle({ icon, title, count }: { icon: ReactNode; title: string; count?: number }) {
  return (
    <div className="creative-panel-title">
      {icon}
      <h3>{title}</h3>
      {typeof count === "number" ? <span>{count}</span> : null}
    </div>
  );
}

export function BeingContextSummary({
  context,
  reasons,
}: {
  context: BeingWritingContext | null;
  reasons: string[];
}) {
  const visibleReasons = reasons.slice(0, 3);
  return (
    <div className="creative-being">
      {context ? (
        <div className="creative-being__chips" aria-label="本体写作状态">
          <span>能量 {context.energy || "未知"}</span>
          <span>心情 {context.mood || "未知"}</span>
          <span>情绪 {context.primary_emotion || "calm"}</span>
        </div>
      ) : null}
      <ul>
        {(visibleReasons.length > 0 ? visibleReasons : ["当前可继续。"]).map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}

export function ProjectOverview({
  project,
  detail,
  onCreateSession,
  busy,
}: {
  project: NovelProject | null;
  detail: NovelProjectDetail | null;
  onCreateSession: () => void;
  busy: boolean;
}) {
  if (!project) {
    return <section className="creative-panel creative-empty">还没有小说项目。</section>;
  }
  return (
    <section className="creative-panel creative-overview">
      <div>
        <span className="creative-kicker">第 {project.current_chapter_index} 章</span>
        <h3>{project.title}</h3>
        <p>{project.premise}</p>
      </div>
      <div className="creative-overview__meta">
        <span>{project.habit_state.next_intention || "暂无下一步意向"}</span>
        <span>{detail?.fragments.length ?? 0} 个片段</span>
      </div>
      <Button type="button" size="sm" onClick={onCreateSession} disabled={busy}>
        <Plus size={15} />
        准备会话
      </Button>
    </section>
  );
}

export function HabitStateEditor({
  project,
  busy,
  onSave,
}: {
  project: NovelProject | null;
  busy: boolean;
  onSave: (project: NovelProject, payload: UpdateNovelHabitPayload) => void;
}) {
  const [draft, setDraft] = useState<Pick<NovelHabitState, "attachment_reason" | "last_pause" | "next_intention">>({
    attachment_reason: "",
    last_pause: "",
    next_intention: "",
  });

  useEffect(() => {
    setDraft({
      attachment_reason: project?.habit_state.attachment_reason ?? "",
      last_pause: project?.habit_state.last_pause ?? "",
      next_intention: project?.habit_state.next_intention ?? "",
    });
  }, [project]);

  if (!project) {
    return null;
  }

  return (
    <section className="creative-panel creative-habit">
      <PanelTitle icon={<Heart size={18} />} title="创作习惯" />
      <label>
        <span>牵挂</span>
        <textarea
          value={draft.attachment_reason}
          onChange={(event) => setDraft({ ...draft, attachment_reason: event.target.value })}
          rows={2}
        />
      </label>
      <label>
        <span>停顿</span>
        <input value={draft.last_pause} onChange={(event) => setDraft({ ...draft, last_pause: event.target.value })} />
      </label>
      <label>
        <span>下一步</span>
        <input
          value={draft.next_intention}
          onChange={(event) => setDraft({ ...draft, next_intention: event.target.value })}
        />
      </label>
      <Button type="button" size="sm" onClick={() => onSave(project, draft)} disabled={busy}>
        保存习惯
      </Button>
    </section>
  );
}

export function SessionQueue({
  sessions,
  onExecute,
  busyAction,
}: {
  sessions: NovelWritingSession[];
  onExecute: (session: NovelWritingSession, content?: string) => void;
  busyAction: string | null;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  return (
    <section className="creative-panel">
      <PanelTitle icon={<Check size={18} />} title="待确认" count={sessions.length} />
      {sessions.length === 0 ? <p className="creative-muted">当前没有待确认会话。</p> : null}
      {sessions.map((session) => (
        <article key={session.id} className="creative-session">
          <div>
            <strong>{session.title}</strong>
            <p>{session.intention}</p>
            {session.context.recent_excerpt ? <small>{session.context.recent_excerpt}</small> : null}
            <label className="creative-session__draft">
              <span>本次正文</span>
              <textarea
                value={drafts[session.id] ?? ""}
                onChange={(event) => setDrafts({ ...drafts, [session.id]: event.target.value })}
                rows={4}
                placeholder="留空时使用模型自动生成；填写后会按这里的正文保存片段。"
              />
            </label>
          </div>
          <Button
            type="button"
            size="sm"
            onClick={() => onExecute(session, drafts[session.id])}
            disabled={Boolean(busyAction)}
          >
            执行
          </Button>
        </article>
      ))}
    </section>
  );
}

export function FragmentList({ fragments }: { fragments: NovelFragment[] }) {
  return (
    <section className="creative-panel">
      <PanelTitle icon={<FileText size={18} />} title="片段" count={fragments.length} />
      {fragments.slice().reverse().map((fragment) => (
        <article key={fragment.id} className="creative-fragment">
          <div className="creative-fragment__head">
            <strong>第 {fragment.chapter_index} 章 · {fragment.sequence}</strong>
            {fragment.digest?.should_advance_chapter ? <span>建议收章</span> : null}
          </div>
          <p>{fragment.summary || fragment.digest?.summary || fragment.content.slice(0, 90)}</p>
          {fragment.digest?.next_intention ? <small>{fragment.digest.next_intention}</small> : null}
        </article>
      ))}
    </section>
  );
}
