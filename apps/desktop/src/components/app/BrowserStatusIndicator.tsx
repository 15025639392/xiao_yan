import type { BrowserOrganState } from "../../lib/api";

type BrowserStatusIndicatorProps = {
  organ: BrowserOrganState | null | undefined;
};

export function BrowserStatusIndicator({ organ }: BrowserStatusIndicatorProps) {
  if (!organ) {
    return (
      <div className="browser-status browser-status--offline" title="浏览器器官未知">
        <span className="browser-status__icon">🌐</span>
        <span className="browser-status__label">未连接</span>
      </div>
    );
  }

  const { binding_status, health_status, browser_binary_ready } = organ;

  if (binding_status === "unbound" || !browser_binary_ready) {
    return (
      <div className="browser-status browser-status--offline" title="浏览器未绑定或二进制文件不可用">
        <span className="browser-status__icon">🌐</span>
        <span className="browser-status__label">离线</span>
      </div>
    );
  }

  if (health_status === "degraded") {
    return (
      <div className="browser-status browser-status--degraded" title="浏览器器官降级">
        <span className="browser-status__icon">🌐</span>
        <span className="browser-status__label">降级</span>
      </div>
    );
  }

  return (
    <div className="browser-status browser-status--healthy" title="浏览器器官在线">
      <span className="browser-status__icon">🌐</span>
      <span className="browser-status__label">在线</span>
    </div>
  );
}
