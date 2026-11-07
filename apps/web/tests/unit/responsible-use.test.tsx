import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResponsibleUse } from "../../src/components/responsible-use";

describe("ResponsibleUse", () => {
  it("keeps the legal-use boundary visible", () => {
    render(<ResponsibleUse />);

    expect(screen.getByRole("note")).toHaveTextContent("Análise preliminar");
    expect(screen.getByRole("note")).toHaveTextContent("não substitui parecer jurídico");
  });
});
