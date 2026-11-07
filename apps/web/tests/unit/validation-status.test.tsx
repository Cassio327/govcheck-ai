import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ValidationStatus } from "../../src/features/findings/validation-status";

describe("ValidationStatus", () => {
  it("makes external-tool failure explicit", () => {
    render(<ValidationStatus status="unavailable" />);

    expect(screen.getByRole("status")).toHaveTextContent("Consulta PNCP indisponível");
    expect(screen.getByRole("status")).toHaveTextContent("não foi tratada como validação");
  });

  it("does not present mixed external results as verified", () => {
    render(<ValidationStatus status="mixed" />);

    expect(screen.getByRole("status")).toHaveTextContent("Resultados mistos");
    expect(screen.getByRole("status")).toHaveTextContent("relatório");
    expect(screen.getByRole("status")).not.toHaveTextContent("resultado verificado");
  });
});
