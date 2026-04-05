type SettingsPanelProps = {
  theme: "dark" | "light";
  onThemeChange: (theme: "dark" | "light") => void;
};

export function SettingsPanel({ theme, onThemeChange }: SettingsPanelProps) {
  return (
    <section className="settings-page">
      <header className="settings-page__header">
        <h2 className="settings-page__title">设置</h2>
        <p className="settings-page__subtitle">配置数字人控制台的各项参数</p>
      </header>

      <div className="settings-page__content">
        {/* 外观设置 */}
        <section className="settings-section">
          <h3 className="settings-section__title">
            <PaletteIcon /> 外观
          </h3>
          <div className="settings-section__body">
            <div className="setting-item">
              <div className="setting-item__info">
                <label className="setting-item__label">主题</label>
                <p className="setting-item__desc">选择界面的颜色主题</p>
              </div>
              <div className="setting-item__control">
                <div className="theme-selector">
                  <button
                    className={`theme-option ${theme === "dark" ? "theme-option--active" : ""}`}
                    onClick={() => onThemeChange("dark")}
                    type="button"
                  >
                    <MoonIcon />
                    <span>深色</span>
                  </button>
                  <button
                    className={`theme-option ${theme === "light" ? "theme-option--active" : ""}`}
                    onClick={() => onThemeChange("light")}
                    type="button"
                  >
                    <SunIcon />
                    <span>浅色</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 预留位置：通知设置 */}
        <section className="settings-section settings-section--placeholder">
          <h3 className="settings-section__title">
            <BellIcon /> 通知
          </h3>
          <div className="settings-section__body">
            <p className="settings-placeholder">通知设置即将推出</p>
          </div>
        </section>

        {/* 预留位置：快捷键设置 */}
        <section className="settings-section settings-section--placeholder">
          <h3 className="settings-section__title">
            <KeyboardIcon /> 快捷键
          </h3>
          <div className="settings-section__body">
            <p className="settings-placeholder">快捷键设置即将推出</p>
          </div>
        </section>

        {/* 预留位置：数据与隐私 */}
        <section className="settings-section settings-section--placeholder">
          <h3 className="settings-section__title">
            <ShieldIcon /> 数据与隐私
          </h3>
          <div className="settings-section__body">
            <p className="settings-placeholder">数据与隐私设置即将推出</p>
          </div>
        </section>

        {/* 关于 */}
        <section className="settings-section">
          <h3 className="settings-section__title">
            <InfoIcon /> 关于
          </h3>
          <div className="settings-section__body">
            <div className="about-info">
              <div className="about-info__item">
                <span className="about-info__label">版本</span>
                <span className="about-info__value">v0.1.0</span>
              </div>
              <div className="about-info__item">
                <span className="about-info__label">数字人控制台</span>
                <span className="about-info__value">AI Agent Desktop</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

function PaletteIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a10 10 0 0 1 10 10c0 5.523-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2z" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function KeyboardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="4" width="20" height="16" rx="2" ry="2" />
      <line x1="6" y1="8" x2="6" y2="8" />
      <line x1="10" y1="8" x2="10" y2="8" />
      <line x1="14" y1="8" x2="14" y2="8" />
      <line x1="18" y1="8" x2="18" y2="8" />
      <line x1="6" y1="12" x2="6" y2="12" />
      <line x1="10" y1="12" x2="10" y2="12" />
      <line x1="14" y1="12" x2="14" y2="12" />
      <line x1="18" y1="12" x2="18" y2="12" />
      <line x1="6" y1="16" x2="18" y2="16" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
