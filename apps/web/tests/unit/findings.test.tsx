import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FindingList } from "../../src/features/findings/finding-list";
import type { Finding } from "../../src/lib/contracts";

const findings: Finding[] = [
  {
    id: "finding-1",
    category: "deadline",
    title: "Prazo para envio",
    value: "13 de novembro",
    evidence_status: "supported",
    confidence: 0.9,
    citations: [
      { chunk_id: "chunk-1", page_number: 4, excerpt: "até 13 de novembro" },
    ],
  },
  {
    id: "finding-2",
    category: "sanction",
    title: "Percentual de multa",
    value: "Não confirmado",
    evidence_status: "unsupported",
    confidence: 0.2,
    citations: [],
  },
  {
    id: "finding-3",
    category: "obligation",
    title: "Cadastro externo",
    value: "Divergência encontrada",
    evidence_status: "conflicting",
    confidence: 0.7,
    citations: [
      { chunk_id: "chunk-3", page_number: 9, excerpt: "identificador cadastral" },
    ],
  },
];

describe("FindingList", () => {
  it("uses text as well as color for evidence states and reveals the source", async () => {
    const user = userEvent.setup();
    render(<FindingList findings={findings} />);

    expect(screen.getAllByText("Suportado").length).toBeGreaterThan(0);
    expect(screen.getByText("Sem evidência")).toBeInTheDocument();
    expect(screen.getByText("Conflito")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Prazo para envio/i }));
    expect(screen.getByText(/até 13 de novembro/)).toBeVisible();
    expect(screen.getAllByText(/Página 4/).length).toBeGreaterThan(0);
  });
});
