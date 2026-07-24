import type { ReactNode } from "react";

type Props = {
  title: string;
  children: ReactNode;
  action?: ReactNode;
};

export function EmptyState({ title, children, action }: Props) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <div className="muted">{children}</div>
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}
