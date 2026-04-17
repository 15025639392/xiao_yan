type AppSidebarRoute =
  | "overview"
  | "chat"
  | "persona"
  | "memory"
  | "tools"
  | "capabilities";

type AppSidebarProps = {
  assistantName: string;
  isAwake: boolean;
  mode: "awake" | "sleeping";
  route: AppSidebarRoute;
  showBrandMenu: boolean;
  theme: "dark" | "light";
  onNavigate: (route: AppSidebarRoute) => void;
  onShowBrandMenuChange: (open: boolean) => void;
  onToggleTheme: () => void;
  onShowAbout: () => void;
  onWake: () => void;
  onSleep: () => void;
};

export function AppSidebar({
  assistantName,
  isAwake,
  mode,
  route,
  showBrandMenu,
  theme,
  onNavigate,
  onShowBrandMenuChange,
  onToggleTheme,
  onShowAbout,
  onWake,
  onSleep,
}: AppSidebarProps) {
  return (
    <aside className="app-sidebar">
      <div className="app-sidebar__header">
        <div className="app-sidebar__brand-dropdown">
          <button
            type="button"
            className="app-sidebar__brand"
            onClick={() => onShowBrandMenuChange(!showBrandMenu)}
          >
            <span className="app-sidebar__logo">🤖</span>
            <span className="app-sidebar__title">{assistantName}</span>
            <svg
              className={`app-sidebar__brand-chevron ${showBrandMenu ? "app-sidebar__brand-chevron--open" : ""}`}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          {showBrandMenu && (
            <div className="app-sidebar__brand-menu">
              <button
                type="button"
                className="app-sidebar__brand-menu-item"
                onClick={() => {
                  onNavigate("persona");
                  onShowBrandMenuChange(false);
                }}
              >
                <span>🎭</span>
                <span>人格设置</span>
              </button>
              <button
                type="button"
                className="app-sidebar__brand-menu-item"
                onClick={() => {
                  onToggleTheme();
                  onShowBrandMenuChange(false);
                }}
              >
                <span>{theme === "dark" ? "☀️" : "🌙"}</span>
                <span>切换{theme === "dark" ? "浅色" : "深色"}主题</span>
              </button>
              <button
                type="button"
                className="app-sidebar__brand-menu-item"
                onClick={() => {
                  onShowAbout();
                  onShowBrandMenuChange(false);
                }}
              >
                <span>ℹ️</span>
                <span>关于</span>
              </button>
            </div>
          )}
        </div>
        <div className={`app-sidebar__status-dot app-sidebar__status-dot--${mode}`} />
      </div>

      <nav className="app-sidebar__nav" aria-label="主导航">
        <button
          className={`app-sidebar__nav-item ${route === "overview" ? "app-sidebar__nav-item--active" : ""}`}
          onClick={() => onNavigate("overview")}
          type="button"
        >
          <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
          </svg>
          <span>总览</span>
        </button>
        <button
          className={`app-sidebar__nav-item ${route === "chat" ? "app-sidebar__nav-item--active" : ""}`}
          onClick={() => onNavigate("chat")}
          type="button"
        >
          <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <span>对话</span>
        </button>
        <button
          className={`app-sidebar__nav-item ${route === "tools" ? "app-sidebar__nav-item--active" : ""}`}
          onClick={() => onNavigate("tools")}
          type="button"
        >
          <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14.7 6.3a1 1 0 0 0 0-1.4l1.83-2a1 1 0 0 0-1.42-1.4L13.28 5.17a4 4 0 1 0-5.66 5.66l-8.49 8.49a1 1 0 0 0-1.41 0" />
            <path d="M16 21v-6a1 1 0 0 1 1-1h6" />
          </svg>
          <span>工具箱</span>
        </button>
      </nav>

      <div className="app-sidebar__section">
        <div className="app-sidebar__section-title">可选入口</div>
        <div className="app-sidebar__actions">
          <button
            className={`app-sidebar__action-btn ${route === "memory" ? "app-sidebar__action-btn--primary" : ""}`}
            onClick={() => onNavigate("memory")}
            type="button"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a10 10 0 1 0 10 10H12V2z" />
              <path d="M12 2a10 10 0 0 1 10 10" />
              <path d="M12 12L2.5 12" />
            </svg>
            记忆库
          </button>
        </div>
        <p className="app-sidebar__section-hint">
          记忆与人格设置保留为次级入口，默认路径继续聚焦陪伴、对话与当下状态。
        </p>
      </div>

      <div className="app-sidebar__section">
        <div className="app-sidebar__section-title">控制</div>
        <div className="app-sidebar__actions">
          <button
            className="app-sidebar__action-btn app-sidebar__action-btn--primary"
            onClick={onWake}
            type="button"
            disabled={isAwake}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
            唤醒
          </button>
          <button
            className="app-sidebar__action-btn"
            onClick={onSleep}
            type="button"
            disabled={!isAwake}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
            休眠
          </button>
        </div>
      </div>

      <div className="app-sidebar__footer">
        <div className="app-sidebar__status">
          <span className={`app-sidebar__status-indicator app-sidebar__status-indicator--${mode}`} />
          <span className="app-sidebar__status-text">{isAwake ? "运行中" : "休眠中"}</span>
        </div>
      </div>
    </aside>
  );
}
