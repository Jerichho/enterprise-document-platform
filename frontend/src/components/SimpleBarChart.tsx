type BarItem = {
  label: string;
  value: number;
};

type Props = {
  items: BarItem[];
  emptyLabel?: string;
};

export function SimpleBarChart({ items, emptyLabel = "No data in this range." }: Props) {
  if (!items.length) {
    return <p className="muted">{emptyLabel}</p>;
  }

  const max = Math.max(...items.map((item) => item.value), 1);

  return (
    <ul className="simple-bar-chart" aria-label="Bar chart">
      {items.map((item) => (
        <li key={item.label}>
          <div className="simple-bar-label">
            <span>{item.label}</span>
            <span className="muted">{item.value}</span>
          </div>
          <div className="simple-bar-track" aria-hidden="true">
            <div
              className="simple-bar-fill"
              style={{ width: `${Math.max((item.value / max) * 100, item.value > 0 ? 4 : 0)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
