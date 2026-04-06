import { useEffect, useState } from "react";

type CooldownTimerProps = {
  until: string;
};

export function CooldownTimer({ until }: CooldownTimerProps) {
  const [remaining, setRemaining] = useState("");

  useEffect(() => {
    const calcRemain = () => {
      const diff = new Date(until).getTime() - Date.now();
      if (diff <= 0) return "";
      const min = Math.floor(diff / 60000);
      const sec = Math.floor((diff % 60000) / 1000);
      return `${min}:${sec.toString().padStart(2, "0")}`;
    };

    setRemaining(calcRemain());
    const id = setInterval(() => setRemaining(calcRemain()), 1000);
    return () => clearInterval(id);
  }, [until]);

  if (!remaining) return null;

  return (
    <div className="si-cooldown">
      <span className="si-cooldown-icon">⏱️</span>
      <span>冷却中：{remaining}</span>
    </div>
  );
}

