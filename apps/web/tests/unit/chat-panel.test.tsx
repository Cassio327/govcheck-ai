import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatPanel } from "../../src/features/chat/chat-panel";

describe("ChatPanel", () => {
  it("distinguishes a transport failure from a grounded no-evidence answer", () => {
    render(
      <ChatPanel
        enabled
        busy={false}
        onAsk={vi.fn()}
        messages={[
          { id: "error", role: "assistant", text: "Serviço temporariamente indisponível.", state: "error" },
        ]}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Serviço temporariamente indisponível");
    expect(screen.queryByText("Não há evidência suficiente no PDF para responder.")).not.toBeInTheDocument();
  });
});
