import { getHealthColor } from "../../lib/utils";

type HealthRingProps = {
  score: number;
  grade: string;
};

export function HealthRing({ score, grade }: HealthRingProps) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = getHealthColor(score);

  return (
    <div className="health-ring" title={`健康度 ${score.toFixed(0)} 分 (${grade})`}>
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="var(--border-default)" strokeWidth="4" />
        <circle
          cx="22"
          cy="22"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 22 22)"
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <span className="health-ring__score" style={{ color }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}
