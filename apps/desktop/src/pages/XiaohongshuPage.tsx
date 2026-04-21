import { useState, useEffect, useCallback, useRef } from "react";

import { fetchXhsWorkDomain, updateXhsWorkDomain, type XhsWorkDomainResponse } from "../lib/api";
import { browserOpen } from "../lib/tauri/fsAccess";
import { Button } from "../components/ui";

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
  blocked: "已阻塞",
};

const STATUS_STEPS = ["idle", "scouting", "drafting", "publishing", "idle_reviewing"];

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
  const [autoPublishSelector, setAutoPublishSelector] = useState("");
  const [saving, setSaving] = useState(false);
  const [openingLogin, setOpeningLogin] = useState(false);

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
      setAutoPublishSelector(workDomain.profile.auto_publish_selector || "");
    }
  }, [workDomain?.profile]);

  async function handleSaveConfig() {
    setSaving(true);
    try {
      await updateXhsWorkDomain({
        account_name: accountName,
        scouting_interval_hours: scoutingInterval,
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
    // Open browser for manual login if needed
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

  const state = workDomain?.state;
  const profile = workDomain?.profile;
  const status = state?.status || "idle";
  const isRunning = status !== "idle" && status !== "blocked";

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
            type="outline"
            onClick={() => setConfigOpen((o) => !o)}
          >
            {configOpen ? "收起配置" : "配置"}
          </Button>
          <Button
            type={isRunning ? "destructive" : "default"}
            onClick={() => {
              updateXhsWorkDomain({ status: isRunning ? "idle" : "scouting" }).then(loadDomain);
            }}
          >
            {isRunning ? "暂停闭环" : "启动闭环"}
          </Button>
        </div>
      </header>

      {configOpen && (
        <section className="xhs-config-panel">
          <h3 className="xhs-config-panel__title">闭环配置</h3>
          <div className="xhs-config-panel__fields">
            <label className="xhs-config-field">
              <span className="xhs-config-field__label">小红书账号名</span>
              <input
                type="text"
                className="xhs-config-field__input"
                value={accountName}
                placeholder="例如：小红薯66661C17"
                onChange={(e) => setAccountName(e.target.value)}
              />
            </label>
            <label className="xhs-config-field">
              <span className="xhs-config-field__label">侦察间隔（小时）</span>
              <input
                type="number"
                className="xhs-config-field__input"
                value={scoutingInterval}
                min={0.1}
                max={24}
                step={0.1}
                onChange={(e) => setScoutingInterval(parseFloat(e.target.value) || 1.0)}
              />
            </label>
            <label className="xhs-config-field">
              <span className="xhs-config-field__label">发布按钮 Selector</span>
              <input
                type="text"
                className="xhs-config-field__input"
                value={autoPublishSelector}
                placeholder="自动发现（留空）"
                onChange={(e) => setAutoPublishSelector(e.target.value)}
              />
            </label>
          </div>
          <div className="xhs-config-panel__actions">
            <Button type="default" onClick={() => setConfigOpen(false)}>取消</Button>
            <Button type="primary" onClick={handleSaveConfig} disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </Button>
          </div>
        </section>
      )}

      {(!(profile?.account_name && profile.account_name !== "当前账号" && profile.account_name.trim() !== "" && profile.account_name !== "已登录账号") || state?.current_bottleneck === "需要登录小红书账号") && (
        <div className="xhs-login-guidance">
          <div className="xhs-login-guidance__text">
            <strong>未检测到小红书账号登录</strong>
            <span>点击「去登录」在浏览器中完成登录，系统将自动检测。</span>
          </div>
          <Button
            type="primary"
            onClick={handleOpenLoginPage}
            disabled={openingLogin}
          >
            {openingLogin ? "正在打开..." : "去登录"}
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
                <li key={draft.draft_id} className="xhs-pending-item">
                  <span className="xhs-pending-item__title">{draft.title}</span>
                  <span className="xhs-pending-item__status">{draft.status}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
