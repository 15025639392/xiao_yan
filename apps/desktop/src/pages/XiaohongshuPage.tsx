import { useState, useEffect, useCallback, useRef } from "react";

import { fetchXhsWorkDomain, updateXhsWorkDomain, wakeLifecycle, type XhsWorkDomainResponse } from "../lib/api";
import { browserOpen } from "../lib/tauri/fsAccess";
import { Button } from "../components/ui";
import { XiaohongshuConfigPanel } from "./XiaohongshuConfigPanel";
import { XiaohongshuLoginGuidance } from "./XiaohongshuLoginGuidance";

type XiaohongshuPageProps = {
  assistantName: string;
};

const XHS_LOGIN_SESSION_ID = "xhs-login";

const STATUS_LABELS: Record<string, string> = {
  idle: "空闲",
  idle_reviewing: "待补图",
  scouting: "侦察中",
  drafting: "生成草稿中",
  publishing: "发布中",
  reviewing: "待确认发布",
  blocked: "已阻塞",
};

const STATUS_STEPS = ["idle", "scouting", "drafting", "publishing", "idle_reviewing", "reviewing"];

function getStepIndex(status: string): number {
  if (status === "blocked") return -1;
  return STATUS_STEPS.indexOf(status);
}

function LoopProgress({ status }: { status: string }) {
  const current = getStepIndex(status);
  const isBlocked = status === "blocked";

  return (
    <div className="xhs-loop-progress">
      {STATUS_STEPS.map((step, i) => {
        const isActive = i === current;
        const isDone = i < current;
        const isPending = i > current;
        return (
          <div key={step} className={`xhs-loop-step ${isDone ? "done" : ""} ${isActive ? "active" : ""} ${isPending ? "pending" : ""}`}>
            <div className="xhs-loop-step__dot">
              {isDone ? "✓" : isActive ? "●" : "○"}
            </div>
            <div className="xhs-loop-step__label">{STATUS_LABELS[step]}</div>
            {i < STATUS_STEPS.length - 1 && (
              <div className={`xhs-loop-step__line ${isDone ? "done" : ""}`} />
            )}
          </div>
        );
      })}
      {isBlocked && (
        <div className="xhs-loop-step xhs-loop-step--blocked">
          <div className="xhs-loop-step__dot">!</div>
          <div className="xhs-loop-step__label">阻塞</div>
        </div>
      )}
    </div>
  );
}

function PublishedHistory({ history }: { history: Array<{ draft_id: string; title: string; published_at: string; post_url: string }> }) {
  if (!history || history.length === 0) {
    return <p className="xhs-history-empty">暂无发布记录</p>;
  }
  return (
    <ul className="xhs-history-list">
      {history.slice(-5).reverse().map((entry) => (
        <li key={entry.draft_id} className="xhs-history-item">
          <span className="xhs-history-item__title">{entry.title || "(无标题)"}</span>
          <span className="xhs-history-item__time">
            {new Date(entry.published_at).toLocaleString()}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function XiaohongshuPage({ assistantName }: XiaohongshuPageProps) {
  const [workDomain, setWorkDomain] = useState<XhsWorkDomainResponse | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [accountName, setAccountName] = useState("");
  const [scoutingInterval, setScoutingInterval] = useState(1.0);
  const [publishMode, setPublishMode] = useState<"review_before_publish" | "direct_publish">("review_before_publish");
  const [autoPublishSelector, setAutoPublishSelector] = useState("");
  const [saving, setSaving] = useState(false);
  const [openingLogin, setOpeningLogin] = useState(false);
  const [draftEdits, setDraftEdits] = useState<Record<string, { title: string; body: string }>>({});

  const loadDomain = useCallback(() => {
    fetchXhsWorkDomain()
      .then(setWorkDomain)
      .catch(() => setWorkDomain(null));
  }, []);

  // Ref to track whether login guidance is showing (avoids interval reset on state change)
  const loginGuidanceShownRef = useRef(false);

  useEffect(() => {
    loadDomain();
    const interval = setInterval(() => {
      // Auto-retry scouting while login guidance is shown
      if (loginGuidanceShownRef.current) {
        updateXhsWorkDomain({ status: "scouting" }).then(loadDomain);
      } else {
        loadDomain();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [loadDomain]);

  // Keep ref in sync with whether login guidance should be shown
  useEffect(() => {
    const name = profile?.account_name || "";
    loginGuidanceShownRef.current =
      (name === "" || name === "当前账号" || state?.current_bottleneck === "需要登录小红书账号") &&
      name !== "已登录账号";
  });

  useEffect(() => {
    if (workDomain?.profile) {
      setAccountName(workDomain.profile.account_name || "");
      setScoutingInterval(workDomain.profile.scouting_interval_hours || 1.0);
      setPublishMode(workDomain.profile.publish_mode || "review_before_publish");
      setAutoPublishSelector(workDomain.profile.auto_publish_selector || "");
    }
  }, [workDomain?.profile]);

  useEffect(() => {
    const serverDrafts = workDomain?.state?.pending_drafts || [];
    if (serverDrafts.length === 0) {
      setDraftEdits({});
      return;
    }
    setDraftEdits((prev) => {
      const localIds = new Set(Object.keys(prev));
      const hasNew = serverDrafts.some((d) => !localIds.has(d.draft_id));
      if (!hasNew && Object.keys(prev).length > 0) return prev;
      const next: Record<string, { title: string; body: string }> = { ...prev };
      serverDrafts.forEach((d) => {
        if (!next[d.draft_id]) {
          next[d.draft_id] = { title: d.title, body: d.body };
        }
      });
      return next;
    });
  }, [workDomain?.state?.pending_drafts]);

  async function handleSaveConfig() {
    setSaving(true);
    try {
      await updateXhsWorkDomain({
        account_name: accountName,
        scouting_interval_hours: scoutingInterval,
        publish_mode: publishMode,
        auto_publish_selector: autoPublishSelector,
      });
      loadDomain();
      setConfigOpen(false);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  async function handleOpenLoginPage() {
    setOpeningLogin(true);
    try {
      await browserOpen("https://creator.xiaohongshu.com/new/home", {
        session_id: XHS_LOGIN_SESSION_ID,
        headless: false,
      });
    } catch {
      // ignore
    } finally {
      setOpeningLogin(false);
    }
  }

  async function handleToggleLoop() {
    if (isRunning) {
      await updateXhsWorkDomain({ status: "idle" });
      loadDomain();
      return;
    }

    try {
      await wakeLifecycle();
    } catch {
      // ignore wake failure and still try to start xhs loop state
    }
    await updateXhsWorkDomain({ status: "scouting" });
    loadDomain();
  }

  async function handleConfirmManualPublish() {
    await updateXhsWorkDomain({ status: "idle" });
    loadDomain();
  }

  async function handleSaveDrafts() {
    if (!workDomain?.state?.pending_drafts) return;
    const updated = workDomain.state.pending_drafts.map((d) => ({
      ...d,
      title: draftEdits[d.draft_id]?.title ?? d.title,
      body: draftEdits[d.draft_id]?.body ?? d.body,
    }));
    try {
      await updateXhsWorkDomain({ pending_drafts: updated });
      loadDomain();
    } catch {
      // ignore
    }
  }

  async function handleDeleteDraft(draftId: string) {
    if (!workDomain?.state?.pending_drafts) return;
    const remaining = workDomain.state.pending_drafts.filter((d) => d.draft_id !== draftId);
    const newBacklog = remaining.length;
    const currentStatus = workDomain.state?.status || "idle";
    try {
      await updateXhsWorkDomain({
        pending_drafts: remaining,
        backlog_count: newBacklog,
        ...(currentStatus === "idle_reviewing" && remaining.length === 0 ? { status: "idle" } : {}),
      });
      setDraftEdits((prev) => {
        const next = { ...prev };
        delete next[draftId];
        return next;
      });
      loadDomain();
    } catch {
      // ignore
    }
  }

  const state = workDomain?.state;
  const profile = workDomain?.profile;
  const status = state?.status || "idle";
  const isRunning = status !== "idle" && status !== "blocked";

  const showLoginGuidance =
    (!(profile?.account_name && profile.account_name !== "当前账号" && profile.account_name.trim() !== "" && profile.account_name !== "已登录账号") ||
      state?.current_bottleneck === "需要登录小红书账号");

  return (
    <div className="xhs-page">
      <header className="xhs-page__header">
        <div>
          <h2 className="xhs-page__title">小红书经营闭环</h2>
          <p className="xhs-page__subtitle">
            {assistantName} 全自动管理小红书账号：自动侦察 → AI生成草稿 → 自动发布 → 循环继续。
          </p>
        </div>
        <div className="xhs-page__header-actions">
          <Button
            variant="outline"
            onClick={() => setConfigOpen((o) => !o)}
          >
            {configOpen ? "收起配置" : "配置"}
          </Button>
          <Button
            variant={isRunning ? "destructive" : "default"}
            onClick={() => {
              void handleToggleLoop();
            }}
          >
            {isRunning ? "暂停闭环" : "启动闭环"}
          </Button>
        </div>
      </header>

      {configOpen && (
        <XiaohongshuConfigPanel
          accountName={accountName}
          onAccountNameChange={setAccountName}
          scoutingInterval={scoutingInterval}
          onScoutingIntervalChange={setScoutingInterval}
          publishMode={publishMode}
          onPublishModeChange={setPublishMode}
          autoPublishSelector={autoPublishSelector}
          onAutoPublishSelectorChange={setAutoPublishSelector}
          onSave={handleSaveConfig}
          onCancel={() => setConfigOpen(false)}
          saving={saving}
        />
      )}

      {showLoginGuidance && (
        <XiaohongshuLoginGuidance
          onOpenLoginPage={handleOpenLoginPage}
          opening={openingLogin}
        />
      )}

      {status === "reviewing" && (
        <div className="xhs-review-confirm">
          <span>小晏已把内容填到发布页，请检查后直接点击浏览器中的「发布」。</span>
          <Button variant="default" onClick={handleConfirmManualPublish}>
            已手动发布，结束本轮
          </Button>
        </div>
      )}

      <section className="xhs-status-bar">
        <div className={`xhs-status-badge xhs-status-badge--${status}`}>
          {STATUS_LABELS[status] || status}
        </div>
        {state?.current_focus && (
          <span className="xhs-status-bar__focus">{state.current_focus}</span>
        )}
        {state?.next_recommended_action && (
          <span className="xhs-status-bar__next">{state.next_recommended_action}</span>
        )}
        {state?.current_bottleneck && (
          <span className="xhs-status-bar__bottleneck">⛔ {state.current_bottleneck}</span>
        )}
      </section>

      <LoopProgress status={status} />

      <section className="xhs-page__body">
        <div className="xhs-page__info-grid">
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">账号</h4>
            <p className="xhs-info-card__value">{profile?.account_name || "未配置"}</p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">侦察间隔</h4>
            <p className="xhs-info-card__value">{profile?.scouting_interval_hours ?? 1.0}h</p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">发布模式</h4>
            <p className="xhs-info-card__value">
              {profile?.publish_mode === "direct_publish" ? "自动直发" : "待确认发布"}
            </p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">上次侦察</h4>
            <p className="xhs-info-card__value">
              {state?.last_scouting_at
                ? new Date(state.last_scouting_at).toLocaleString()
                : "—"}
            </p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">上次发布</h4>
            <p className="xhs-info-card__value">
              {state?.last_published_at
                ? new Date(state.last_published_at).toLocaleString()
                : "—"}
            </p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">待发草稿</h4>
            <p className="xhs-info-card__value">{state?.backlog_count ?? 0}</p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">已发布总数</h4>
            <p className="xhs-info-card__value">{state?.published_history?.length ?? 0}</p>
          </div>
        </div>

        <div className="xhs-page__history-section">
          <h4 className="xhs-section-title">发布历史（最近5条）</h4>
          <PublishedHistory history={state?.published_history || []} />
        </div>

        {state?.pending_drafts && state.pending_drafts.length > 0 && (
          <div className="xhs-page__pending-section">
            <h4 className="xhs-section-title">待发布草稿</h4>
            <ul className="xhs-pending-list">
              {state.pending_drafts.map((draft) => (
                <li key={draft.draft_id} className="xhs-pending-item xhs-pending-item--editable">
                  <input
                    className="xhs-pending-item__title-input"
                    type="text"
                    value={draftEdits[draft.draft_id]?.title ?? draft.title}
                    onChange={(e) =>
                      setDraftEdits((prev) => ({
                        ...prev,
                        [draft.draft_id]: {
                          ...prev[draft.draft_id],
                          title: e.target.value,
                        },
                      }))
                    }
                  />
                  <textarea
                    className="xhs-pending-item__body-input"
                    rows={3}
                    value={draftEdits[draft.draft_id]?.body ?? draft.body}
                    onChange={(e) =>
                      setDraftEdits((prev) => ({
                        ...prev,
                        [draft.draft_id]: {
                          ...prev[draft.draft_id],
                          body: e.target.value,
                        },
                      }))
                    }
                  />
                  <div className="xhs-pending-item__actions">
                    <span className="xhs-pending-item__status">{draft.status}</span>
                    <Button variant="outline" onClick={handleSaveDrafts}>
                      保存修改
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => {
                        if (window.confirm("确定删除这条草稿？")) {
                          void handleDeleteDraft(draft.draft_id);
                        }
                      }}
                    >
                      删除
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
