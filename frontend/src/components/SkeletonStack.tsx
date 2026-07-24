type Props = {
  rows?: number;
  label?: string;
};

export function SkeletonStack({ rows = 3, label = "Loading" }: Props) {
  return (
    <div className="skeleton-stack" role="status" aria-live="polite" aria-label={label}>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} aria-hidden="true" />
      ))}
    </div>
  );
}
