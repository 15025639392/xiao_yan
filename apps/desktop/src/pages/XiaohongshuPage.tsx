import { useState, useEffect, useCallback } from "react";

import { fetchXhsWorkDomain, updateXhsWorkDomain, type XhsWorkDomainResponse } from "../lib/api";
import { regenerateDraft } from "../lib/apiRuntime";
import { previewXiaohongshuCover, type XiaohongshuCoverPreviewResponse } from "../lib/apiXiaohongshu";
import { browserOpen } from "../lib/tauri/fsAccess";
import { Button } from "../components/ui";
import { formatRelativeTimeZh, formatTimeInfo } from "../lib/utils/time";
import { XiaohongshuConfigPanel } from "./XiaohongshuConfigPanel";
import { XiaohongshuLoginGuidance } from "./XiaohongshuLoginGuidance";
import { XiaohongshuPendingDraftList } from "./XiaohongshuPendingDraftList";

type XiaohongshuPageProps = {
  assistantName: string;
};

const XHS_LOGIN_SESSION_ID = "xhs-login";

const STATUS_LABELS: Record<string, string> = {
  idle: "空闲",
  scouting: "侦察中",
  drafting: "生成草稿中",
  publishing: "发布中",
  reviewing: "待确认发布",
  blocked: "已阻塞",
};

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
            {formatRelativeTimeZh(entry.published_at)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function getPublishModeLabel(publishMode: string | undefined): string {
  return publishMode === "auto" ? "自动发布" : "手动发布";
}

export function XiaohongshuPage({ assistantName }: XiaohongshuPageProps) {
  const [workDomain, setWorkDomain] = useState<XhsWorkDomainResponse | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [accountName, setAccountName] = useState("");
  const [scoutingInterval, setScoutingInterval] = useState(1.0);
  const [publishMode, setPublishMode] = useState<"manual" | "auto">("manual");
  const [saving, setSaving] = useState(false);
  const [openingLogin, setOpeningLogin] = useState(false);
  const [draftEdits, setDraftEdits] = useState<Record<string, { title: string; body: string }>>({});
  const [draftCoverPreviews, setDraftCoverPreviews] = useState<Record<string, XiaohongshuCoverPreviewResponse | null>>({});
  const [draftCoverLoading, setDraftCoverLoading] = useState<Record<string, boolean>>({});
  const [draftCoverErrors, setDraftCoverErrors] = useState<Record<string, string>>({});

  const loadDomain = useCallback(() => {
    fetchXhsWorkDomain()
      .then(setWorkDomain)
      .catch(() => setWorkDomain(null));
  }, []);

  useEffect(() => {
    loadDomain();
    const interval = setInterval(loadDomain, 5000);
    return () => clearInterval(interval);
  }, [loadDomain]);

  useEffect(() => {
    if (workDomain?.profile) {
      setAccountName(workDomain.profile.account_name || "");
      setScoutingInterval(workDomain.profile.scouting_interval_hours || 1.0);
      setPublishMode(workDomain.profile.publish_mode || "manual");
    }
  }, [workDomain?.profile]);

  useEffect(() => {
    const serverDrafts = workDomain?.state?.pending_drafts || [];
    if (serverDrafts.length === 0) {
      setDraftEdits({});
      setDraftCoverPreviews({});
      setDraftCoverLoading({});
      setDraftCoverErrors({});
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

  useEffect(() => {
    const serverDrafts = workDomain?.state?.pending_drafts || [];
    if (serverDrafts.length === 0) return;
    let cancelled = false;

    async function ensureCoverPreviews() {
      for (const draft of serverDrafts) {
        if (draftCoverPreviews[draft.draft_id]) continue;
        const title = draftEdits[draft.draft_id]?.title ?? draft.title;
        const body = draftEdits[draft.draft_id]?.body ?? draft.body;
        if (!title.trim() || !body.trim()) continue;
        setDraftCoverLoading((prev) => ({ ...prev, [draft.draft_id]: true }));
        setDraftCoverErrors((prev) => ({ ...prev, [draft.draft_id]: "" }));
        try {
          const result = await previewXiaohongshuCover({ title, body });
          if (!cancelled) {
            setDraftCoverPreviews((prev) => ({ ...prev, [draft.draft_id]: result }));
          }
        } catch (error) {
          if (!cancelled) {
            setDraftCoverErrors((prev) => ({
              ...prev,
              [draft.draft_id]: error instanceof Error ? error.message : "生成封面预览失败",
            }));
          }
        } finally {
          if (!cancelled) {
            setDraftCoverLoading((prev) => ({ ...prev, [draft.draft_id]: false }));
          }
        }
      }
    }

    void ensureCoverPreviews();
    return () => {
      cancelled = true;
    };
  }, [workDomain?.state?.pending_drafts, draftEdits, draftCoverPreviews]);

  async function handleSwitchDraftCoverTemplate(draftId: string, templateName: string) {
    const pendingDraft = workDomain?.state?.pending_drafts?.find((item) => item.draft_id === draftId);
    if (!pendingDraft) return;
    const title = draftEdits[draftId]?.title ?? pendingDraft.title;
    const body = draftEdits[draftId]?.body ?? pendingDraft.body;
    setDraftCoverLoading((prev) => ({ ...prev, [draftId]: true }));
    setDraftCoverErrors((prev) => ({ ...prev, [draftId]: "" }));
    try {
      const result = await previewXiaohongshuCover({
        title,
        body,
        template_name: templateName,
      });
      setDraftCoverPreviews((prev) => ({ ...prev, [draftId]: result }));
    } catch (error) {
      setDraftCoverErrors((prev) => ({
        ...prev,
        [draftId]: error instanceof Error ? error.message : "切换封面模板失败",
      }));
    } finally {
      setDraftCoverLoading((prev) => ({ ...prev, [draftId]: false }));
    }
  }

  async function handleSaveConfig() {
    setSaving(true);
    try {
      await updateXhsWorkDomain({
        account_name: accountName,
        scouting_interval_hours: scoutingInterval,
        publish_mode: publishMode,
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

  async function handleRegenerateDraft() {
    try {
      await regenerateDraft();
      loadDomain();
    } catch {
      // ignore
    }
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
    try {
      await updateXhsWorkDomain({
        pending_drafts: remaining,
        backlog_count: newBacklog,
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

  function handleDraftEditChange(draftId: string, patch: Partial<{ title: string; body: string }>) {
    setDraftEdits((prev) => ({
      ...prev,
      [draftId]: {
        ...prev[draftId],
        ...patch,
      },
    }));
  }

  async function handlePublishDraft(draftId: string) {
    if (!workDomain?.state?.pending_drafts) return;
    const orderedDrafts = workDomain.state.pending_drafts.map((d) => ({
      ...d,
      title: draftEdits[d.draft_id]?.title ?? d.title,
      body: draftEdits[d.draft_id]?.body ?? d.body,
    }));
    const targetDraft = orderedDrafts.find((d) => d.draft_id === draftId);
    if (!targetDraft) return;

    const reorderedDrafts = [
      targetDraft,
      ...orderedDrafts.filter((d) => d.draft_id !== draftId),
    ];

    try {
      await updateXhsWorkDomain({
        pending_drafts: reorderedDrafts,
        backlog_count: reorderedDrafts.length,
        status: "publishing",
        current_focus: `已选择优先发布：${targetDraft.title || "(无标题)"}`,
        current_bottleneck: "",
        next_recommended_action: "",
      });
      loadDomain();
    } catch {
      // ignore
    }
  }

  const state = workDomain?.state;
  const profile = workDomain?.profile;
  const status = state?.status || "idle";
  const publishModeLabel = getPublishModeLabel(profile?.publish_mode);

  const showLoginGuidance =
    (!(profile?.account_name && profile.account_name !== "当前账号" && profile.account_name.trim() !== "" && profile.account_name !== "已登录账号") ||
      state?.current_bottleneck === "需要登录小红书账号");

  return (
    <div className="xhs-page">
      <header className="xhs-page__header">
        <div>
          <h2 className="xhs-page__title">小红书经营闭环</h2>
          <p className="xhs-page__subtitle">
            {profile?.publish_mode === "auto"
              ? `${assistantName} 会自动侦察、生成轻科普草稿，并把待发草稿依次自动发布到小红书。`
              : `${assistantName} 会先自动侦察并生成轻科普草稿，等你选中草稿后再打开小红书发布。`}
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
            variant="default"
            onClick={() => {
              void handleRegenerateDraft();
            }}
          >
            重新生成草稿
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
        </div>
      )}

      <section className={`xhs-status-bar${status === "scouting" || status === "drafting" || status === "publishing" ? " xhs-status-bar--active" : ""}${status === "reviewing" ? " xhs-status-bar--reviewing" : ""}${status === "blocked" ? " xhs-status-bar--blocked" : ""}`}>
        <div className={`xhs-status-badge xhs-status-badge--${status}`}>
          {STATUS_LABELS[status] || status}
        </div>
        <div className="xhs-status-bar__body">
          {state?.current_focus && (
            <span className="xhs-status-bar__focus">{state.current_focus}</span>
          )}
          {state?.next_recommended_action && (
            <span className="xhs-status-bar__next">{state.next_recommended_action}</span>
          )}
          {state?.current_bottleneck && (
            <span className="xhs-status-bar__bottleneck">{state.current_bottleneck}</span>
          )}
        </div>
        <span className="xhs-status-bar__updated">
          状态更新 {formatRelativeTimeZh(state?.last_scouting_at ?? state?.last_published_at)}
        </span>
      </section>

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
            <p className="xhs-info-card__value">{publishModeLabel}</p>
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">上次侦察</h4>
            {state?.last_scouting_at ? (
              <div className="xhs-info-card__value xhs-info-card__value--time">
                <span className="xhs-info-card__value-relative">
                  {formatTimeInfo(state.last_scouting_at)?.relative}
                </span>
                <span className="xhs-info-card__value-absolute">
                  {formatTimeInfo(state.last_scouting_at)?.absolute}
                </span>
              </div>
            ) : (
              <p className="xhs-info-card__value">—</p>
            )}
          </div>
          <div className="xhs-info-card">
            <h4 className="xhs-info-card__title">上次发布</h4>
            {state?.last_published_at ? (
              <div className="xhs-info-card__value xhs-info-card__value--time">
                <span className="xhs-info-card__value-relative">
                  {formatTimeInfo(state.last_published_at)?.relative}
                </span>
                <span className="xhs-info-card__value-absolute">
                  {formatTimeInfo(state.last_published_at)?.absolute}
                </span>
              </div>
            ) : (
              <p className="xhs-info-card__value">—</p>
            )}
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

        {state?.pending_drafts && state.pending_drafts.length > 0 ? (
          <XiaohongshuPendingDraftList
            drafts={state.pending_drafts}
            status={status}
            publishMode={publishMode}
            draftEdits={draftEdits}
            draftCoverPreviews={draftCoverPreviews}
            draftCoverLoading={draftCoverLoading}
            draftCoverErrors={draftCoverErrors}
            onDraftEditChange={handleDraftEditChange}
            onSwitchDraftCoverTemplate={(draftId, templateName) => {
              void handleSwitchDraftCoverTemplate(draftId, templateName);
            }}
            onSaveDrafts={() => {
              void handleSaveDrafts();
            }}
            onPublishDraft={(draftId) => {
              void handlePublishDraft(draftId);
            }}
            onDeleteDraft={(draftId) => {
              void handleDeleteDraft(draftId);
            }}
          />
        ) : null}
      </section>
    </div>
  );
}
