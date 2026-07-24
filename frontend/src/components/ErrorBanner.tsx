import type { ReactNode } from "react";

type Props = {
  message: string;
  onRetry?: () => void;
  children?: ReactNode;
};

export function ErrorBanner({ message, onRetry, children }: Props) {
  return (
    <div className="error-banner" role="alert">
      <div>
        <p className="error">{message}</p>
        {children}
      </div>
      {onRetry && (
        <button className="btn" type="button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
