import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const documentId = "3c1c9c8d-4bc5-4f39-8ac4-9bb70c58f40d";

const findings = [
  {
    id: "95ab4249-e7ef-41a4-a4a9-e3a936c64964",
    category: "deadline",
    title: "Prazo para envio das propostas",
    value: "13 de novembro de 2026, às 18h",
    evidence_status: "supported",
    confidence: 0.94,
    citations: [{ chunk_id: "dcbcb76b-e864-4b42-80c7-f4808de8fdbf", page_number: 4, excerpt: "As propostas serão recebidas até 13 de novembro de 2026, às 18h." }],
  },
  {
    id: "50bb078a-8b35-4aae-a386-c9c0bd378799",
    category: "sanction",
    title: "Percentual de multa",
    value: "Não confirmado",
    evidence_status: "unsupported",
    confidence: 0.21,
    citations: [],
  },
];

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8000/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const cors = {
      "access-control-allow-origin": "http://127.0.0.1:3000",
      "access-control-allow-headers": "Content-Type, X-Session-ID, Last-Event-ID",
      "access-control-allow-methods": "GET, POST, OPTIONS",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: cors });
      return;
    }
    if (url.pathname === "/api/v1/documents" && request.method() === "POST") {
      await route.fulfill({
        status: 201,
        headers: { ...cors, "content-type": "application/json" },
        body: JSON.stringify({ id: documentId, filename: "edital-teste.pdf", status: "indexed", created_at: "2026-11-05T12:00:00Z", expires_at: "2026-11-06T12:00:00Z" }),
      });
      return;
    }
    if (url.pathname.endsWith("/analysis") && request.method() === "POST") {
      await route.fulfill({
        status: 202,
        headers: { ...cors, "content-type": "application/json" },
        body: JSON.stringify({ id: "4c65b593-9b98-41d7-b39c-a2b33c1cb293", document_id: documentId, status: "running", created_at: "2026-11-05T12:00:01Z" }),
      });
      return;
    }
    if (url.pathname.endsWith("/events")) {
      await route.fulfill({
        status: 200,
        headers: { ...cors, "content-type": "text/event-stream" },
        body: [
          "id: 1\nevent: analysis.started\ndata: {}",
          "id: 2\nevent: analysis.extraction.completed\ndata: {\"finding_count\":2}",
          "id: 3\nevent: analysis.external_validation.completed\ndata: {\"validation_count\":1,\"validation_status_counts\":{\"verified\":0,\"not_found\":0,\"unavailable\":1,\"invalid\":0}}",
          "id: 4\nevent: analysis.evidence_critic.completed\ndata: {\"supported_count\":1,\"unsupported_count\":1}",
          "id: 5\nevent: analysis.synthesis.completed\ndata: {\"finding_count\":2}",
          "id: 6\nevent: analysis.completed\ndata: {}",
          "",
        ].join("\n\n"),
      });
      return;
    }
    if (url.pathname.endsWith("/findings")) {
      await route.fulfill({ status: 200, headers: { ...cors, "content-type": "application/json" }, body: JSON.stringify(findings) });
      return;
    }
    if (url.pathname.endsWith("/chat")) {
      await route.fulfill({
        status: 200,
        headers: { ...cors, "content-type": "application/json" },
        body: JSON.stringify({ text: "O prazo informado é 13 de novembro de 2026, às 18h.", citations: findings[0].citations, confidence: 0.94, grounded: true }),
      });
      return;
    }
    if (url.pathname.endsWith("/report")) {
      if (url.searchParams.get("format") === "json") {
        await route.fulfill({
          status: 200,
          headers: { ...cors, "content-type": "application/json" },
          body: JSON.stringify({
            notice: "Análise preliminar; não substitui parecer jurídico.",
            findings,
          }),
        });
        return;
      }
      await route.fulfill({ status: 200, headers: { ...cors, "content-type": "text/markdown" }, body: "# Relatório GovCheck\n\nAnálise preliminar; não substitui parecer jurídico." });
      return;
    }
    await route.fulfill({ status: 404, headers: cors, body: "not found" });
  });
});

test("revisa um edital com progresso, evidências, pergunta e relatório", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.getByRole("note", { name: "Aviso de uso responsável" })).toContainText("não substitui parecer jurídico");
  await page.getByLabel("Selecionar PDF").setInputFiles({ name: "edital-teste.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-test") });
  await expect(page.getByText("6 de 6 etapas concluídas")).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Consulta PNCP indisponível");

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Achados" }).click();
  }
  await expect(page.getByRole("button", { name: /Prazo para envio das propostas/i })).toBeVisible();
  await page.getByRole("button", { name: /Prazo para envio das propostas/i }).click();
  await expect(page.getByText("Página 4 · trecho exibido").first()).toBeVisible();

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Perguntas" }).click();
  }
  await page.getByLabel("Pergunta sobre o edital").fill("Qual é o prazo?");
  await page.getByRole("button", { name: "Enviar pergunta" }).click();
  await expect(page.getByText("O prazo informado é 13 de novembro de 2026, às 18h.")).toBeVisible();
  await expect(page.getByText("Página 4 · trecho exibido").last()).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar relatório Markdown" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^govcheck-.*\.md$/);
  const reportPath = await download.path();
  expect(reportPath).not.toBeNull();
  expect(await readFile(reportPath!, "utf8")).toContain("Análise preliminar; não substitui parecer jurídico.");

  const jsonDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar JSON" }).click();
  const jsonDownload = await jsonDownloadPromise;
  expect(jsonDownload.suggestedFilename()).toMatch(/^govcheck-.*\.json$/);
  const jsonPath = await jsonDownload.path();
  expect(jsonPath).not.toBeNull();
  const jsonReport = JSON.parse(await readFile(jsonPath!, "utf8")) as { notice: string; findings: unknown[] };
  expect(jsonReport.notice).toBe("Análise preliminar; não substitui parecer jurídico.");
  expect(jsonReport.findings).toHaveLength(2);

  const accessibility = await new AxeBuilder({ page }).analyze();
  const seriousViolations = accessibility.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(seriousViolations, JSON.stringify(seriousViolations, null, 2)).toEqual([]);
});
