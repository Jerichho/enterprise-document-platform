import { useEffect, useId, useRef, type ReactNode } from "react";

type Props = {
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  busy?: boolean;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmBanner({
  title,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  busy = false,
  danger = true,
  onConfirm,
  onCancel,
}: Props) {
  const titleId = useId();
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);

  return (
    <div className="confirm-banner" role="alertdialog" aria-labelledby={titleId} aria-modal="true">
      <p id={titleId}>{title}</p>
      <div className="confirm-banner-body">{children}</div>
      <div className="button-row">
        <button
          ref={confirmRef}
          className={`btn ${danger ? "danger" : "primary"}`}
          type="button"
          disabled={busy}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
        <button className="btn ghost" type="button" disabled={busy} onClick={onCancel}>
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}
