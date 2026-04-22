import { Button } from "../components/ui";

type XiaohongshuLoginGuidanceProps = {
  onOpenLoginPage: () => void;
  opening: boolean;
};

export function XiaohongshuLoginGuidance({
  onOpenLoginPage,
  opening,
}: XiaohongshuLoginGuidanceProps) {
  return (
    <div className="xhs-login-guidance">
      <div className="xhs-login-guidance__text">
        <strong>未检测到小红书账号登录</strong>
        <span>点击「去登录」在浏览器中完成登录，系统将自动检测。</span>
      </div>
      <Button
        type="primary"
        onClick={onOpenLoginPage}
        disabled={opening}
      >
        {opening ? "正在打开..." : "去登录"}
      </Button>
    </div>
  );
}
