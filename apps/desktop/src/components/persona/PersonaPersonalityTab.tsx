import { DimensionSlider } from "./DimensionSlider";
import { Button } from "../ui";

type PersonaPersonalityTabProps = {
  openness: number;
  conscientiousness: number;
  extraversion: number;
  agreeableness: number;
  neuroticism: number;
  saving: boolean;
  onOpennessChange: (value: number) => void;
  onConscientiousnessChange: (value: number) => void;
  onExtraversionChange: (value: number) => void;
  onAgreeablenessChange: (value: number) => void;
  onNeuroticismChange: (value: number) => void;
  onSave: () => void;
};

export function PersonaPersonalityTab({
  openness,
  conscientiousness,
  extraversion,
  agreeableness,
  neuroticism,
  saving,
  onOpennessChange,
  onConscientiousnessChange,
  onExtraversionChange,
  onAgreeablenessChange,
  onNeuroticismChange,
  onSave,
}: PersonaPersonalityTabProps) {
  return (
    <div className="persona-form">
      <div className="personality-intro">
        <span className="personality-intro__icon">🧬</span>
        <div className="personality-intro__content">
          <p className="personality-intro__title">大五人格模型（OCEAN）</p>
          <p className="personality-intro__text">
            五个核心维度共同塑造数字人的性格特征。每个维度 0~100，50 为中性平衡点。
            调整后会直接影响数字人的情绪反应、表达方式和行为倾向。
          </p>
        </div>
      </div>

      <div className="personality-dimensions">
        <DimensionSlider dimensionKey="openness" value={openness} onChange={onOpennessChange} />
        <DimensionSlider dimensionKey="conscientiousness" value={conscientiousness} onChange={onConscientiousnessChange} />
        <DimensionSlider dimensionKey="extraversion" value={extraversion} onChange={onExtraversionChange} />
        <DimensionSlider dimensionKey="agreeableness" value={agreeableness} onChange={onAgreeablenessChange} />
        <DimensionSlider dimensionKey="neuroticism" value={neuroticism} onChange={onNeuroticismChange} />
      </div>

      <div className="persona-form__actions">
        <Button type="button" variant="default" onClick={onSave} disabled={saving}>
          {saving ? "保存中..." : "保存性格"}
        </Button>
      </div>
    </div>
  );
}
