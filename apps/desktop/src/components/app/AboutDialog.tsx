type AboutDialogProps = {
  assistantIdentity: string;
  assistantName: string;
  open: boolean;
  onClose: () => void;
};

export function AboutDialog({ assistantIdentity, assistantName, open, onClose }: AboutDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--sm" onClick={(event) => event.stopPropagation()}>
        <div className="modal__header">
          <h3 className="modal__title">关于 {assistantName}</h3>
          <button type="button" className="modal__close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal__body">
          <div className="about-content">
            <div className="about-logo">🤖</div>
            <h4 className="about-name">{assistantName}</h4>
            <p className="about-desc">{assistantIdentity}</p>
            <div className="about-meta">
              <div className="about-meta__item">
                <span className="about-meta__label">版本</span>
                <span className="about-meta__value">v0.1.0</span>
              </div>
              <div className="about-meta__item">
                <span className="about-meta__label">人格系统</span>
                <span className="about-meta__value">情绪驱动</span>
              </div>
              <div className="about-meta__item">
                <span className="about-meta__label">记忆系统</span>
                <span className="about-meta__value">结构化记忆</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
