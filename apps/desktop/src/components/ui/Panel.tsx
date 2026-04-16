import type { ReactNode } from "react";
import { Card, CardContent, CardHeader } from "./card";

type PanelProps = {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
};

export function Panel({ icon, title, subtitle, actions, className, children }: PanelProps) {
  return (
    <Card className={`panel${className ? ` ${className}` : ""}`}>
        <CardHeader className="panel__header">
        <div className="panel__title-group">
          {icon ? <div className="panel__icon">{icon}</div> : null}
          <div>
            <h2 className="panel__title">{title}</h2>
            {subtitle ? <p className="panel__subtitle">{subtitle}</p> : null}
          </div>
        </div>
        {actions ? <div>{actions}</div> : null}
        </CardHeader>
        <CardContent className="panel__content">{children}</CardContent>
    </Card>
  );
}
