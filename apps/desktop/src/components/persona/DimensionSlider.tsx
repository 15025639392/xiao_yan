import { DIMENSIONS } from "./personaConstants";

type DimensionSliderProps = {
  dimensionKey: keyof typeof DIMENSIONS;
  value: number;
  onChange: (value: number) => void;
};

export function DimensionSlider({ dimensionKey, value, onChange }: DimensionSliderProps) {
  const info = DIMENSIONS[dimensionKey];
  const isNeutral = Math.abs(value - 50) < 10;
  const isHigh = value > 50;

  return (
    <div className="personality-dimension">
      <div className="personality-dimension__header">
        <div className="personality-dimension__title-group">
          <span className="personality-dimension__icon">{info.icon}</span>
          <div className="personality-dimension__titles">
            <div className="personality-dimension__title-row">
              <span className="personality-dimension__label">{info.label}</span>
              <span className="personality-dimension__english">{info.english}</span>
            </div>
            <span className="personality-dimension__short-desc">{info.shortDesc}</span>
          </div>
        </div>
        <div className="personality-dimension__value-group">
          <span className={`personality-dimension__value ${isNeutral ? "neutral" : isHigh ? "high" : "low"}`}>
            {value}
          </span>
          <span className="personality-dimension__tendency">
            {isNeutral ? "平衡" : isHigh ? info.highLabel : info.lowLabel}
          </span>
        </div>
      </div>

      <div className="personality-dimension__slider-area">
        <div className="personality-dimension__endpoint personality-dimension__endpoint--left">
          <span className="endpoint-label">{info.lowLabel}</span>
          <span className="endpoint-desc">{info.lowDesc}</span>
        </div>

        <div className="personality-dimension__track-wrapper">
          <input
            type="range"
            min={0}
            max={100}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="personality-dimension__range"
          />
          <div className="personality-dimension__markers">
            <span>0</span>
            <span>25</span>
            <span className="marker-center">50</span>
            <span>75</span>
            <span>100</span>
          </div>
        </div>

        <div className="personality-dimension__endpoint personality-dimension__endpoint--right">
          <span className="endpoint-label">{info.highLabel}</span>
          <span className="endpoint-desc">{info.highDesc}</span>
        </div>
      </div>

      <div className="personality-dimension__impact">
        <span className="impact-label">💡 影响</span>
        <span className="impact-text">{info.impact}</span>
      </div>
    </div>
  );
}

