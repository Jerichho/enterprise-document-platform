import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SimpleBarChart } from "./SimpleBarChart";

describe("SimpleBarChart", () => {
  it("renders empty state when there are no items", () => {
    render(<SimpleBarChart items={[]} emptyLabel="Nothing yet" />);
    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
  });

  it("renders labels and values for bars", () => {
    render(
      <SimpleBarChart
        items={[
          { label: "HR", value: 3 },
          { label: "IT", value: 1 },
        ]}
      />,
    );
    expect(screen.getByText("HR")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("IT")).toBeInTheDocument();
  });
});
