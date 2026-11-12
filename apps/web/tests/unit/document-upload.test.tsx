import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentUpload } from "../../src/features/upload/document-upload";

describe("DocumentUpload", () => {
  it("accepts a PDF and exposes both reviewer paths", async () => {
    const user = userEvent.setup();
    const onFile = vi.fn();
    render(<DocumentUpload document={null} busy={false} onFile={onFile} onExample={vi.fn()} />);

    const file = new File(["%PDF-test"], "edital.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Selecionar PDF"), file);

    expect(onFile).toHaveBeenCalledWith(file);
    expect(screen.getByRole("button", { name: "Usar edital de exemplo" })).toBeEnabled();
  });

  it("locks actions while the document is being processed", () => {
    render(<DocumentUpload document={null} busy onFile={vi.fn()} onExample={vi.fn()} />);

    expect(screen.getByText("Processando PDF…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Usar edital de exemplo" })).toBeDisabled();
  });
});
