import { useState } from "react";
import { Button, Input, Panel } from "../ui";

type BrowserUrlDialogProps = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (url: string) => void;
};

export function BrowserUrlDialog({ isOpen, onClose, onSubmit }: BrowserUrlDialogProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = () => {
    const trimmed = url.trim();
    if (!trimmed) {
      setError("请输入网址");
      return;
    }
    let normalized = trimmed;
    if (!/^https?:\/\//i.test(normalized)) {
      normalized = "https://" + normalized;
    }
    try {
      new URL(normalized);
    } catch {
      setError("网址格式不正确");
      return;
    }
    setError(null);
    onSubmit(normalized);
    setUrl("");
  };

  return (
    <div className="browser-url-dialog-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <Panel className="browser-url-dialog" title="🌐 浏览网页" actions={
        <Button type="button" variant="ghost" size="icon" onClick={onClose}>×</Button>
      }>
        <div className="browser-url-dialog__body">
          <p className="browser-url-dialog__hint">输入网址，小晏将打开页面并读取内容</p>
          <Input
            type="text"
            className="browser-url-dialog__input"
            value={url}
            onChange={(e) => { setUrl(e.target.value); setError(null); }}
            placeholder="https://example.com"
            onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
            autoFocus
          />
          {error ? <p className="browser-url-dialog__error">{error}</p> : null}
          <div className="browser-url-dialog__actions">
            <Button type="button" variant="secondary" onClick={onClose}>取消</Button>
            <Button type="button" variant="default" onClick={handleSubmit}>打开</Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}
