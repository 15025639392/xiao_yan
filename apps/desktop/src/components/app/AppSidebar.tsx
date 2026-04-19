type AppSidebarRoute =
  | "chat"
  | "persona"
  | "memory"
  | "tools";

type AppSidebarProps = {
  assistantName: string;
  route: AppSidebarRoute;
  showBrandMenu: boolean;
  theme: "dark" | "light";
  onNavigate: (route: AppSidebarRoute) => void;
  onShowBrandMenuChange: (open: boolean) => void;
  onToggleTheme: () => void;
  onShowAbout: () => void;
};

export function AppSidebar({
  assistantName,
  route,
  showBrandMenu,
  theme,
  onNavigate,
  onShowBrandMenuChange,
  onToggleTheme,
  onShowAbout,
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
                  onNavigate("memory");
                  onShowBrandMenuChange(false);
                }}
              >
                <span>🧠</span>
                <span>回看记忆</span>
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
      </div>

      <nav className="app-sidebar__nav" aria-label="主导航">
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
          <span>外部能力</span>
        </button>
      </nav>
    </aside>
  );
}
