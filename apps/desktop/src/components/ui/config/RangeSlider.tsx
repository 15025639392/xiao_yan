import { Slider } from "../slider";

type RangeSliderProps = {
  min: number;
  max: number;
  step?: number;
  value: number;
  disabled?: boolean;
  className?: string;
  onChange: (value: number) => void;
};

export function RangeSlider({
  min,
  max,
  step = 1,
  value,
  disabled = false,
  className,
  onChange,
}: RangeSliderProps) {
  return (
    <Slider
      min={min}
      max={max}
      step={step}
      value={[value]}
      onValueChange={(nextValue) => onChange(nextValue[0] ?? min)}
      disabled={disabled}
      className={className}
    />
  );
}
