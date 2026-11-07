import type { ValidationState } from "./validation-state";

export function ValidationStatus({ status }: { status: ValidationState }) {
  if (status === "verified") return <p className="validation-note success" role="status">Consulta PNCP concluída com resultado verificado. Confira a proveniência no relatório.</p>;
  if (status === "skipped") return <p className="validation-note" role="status">Nenhum identificador externo foi solicitado nesta análise.</p>;
  if (status === "not_found") return <p className="validation-note warning" role="status"><strong>Identificador não localizado no PNCP.</strong> Isso não confirma nem invalida o conteúdo do edital.</p>;
  if (status === "invalid") return <p className="validation-note warning" role="status"><strong>Identificador inválido para consulta.</strong> O dado externo não foi tratado como verificado.</p>;
  if (status === "mixed") return <p className="validation-note warning" role="status"><strong>Resultados mistos na consulta PNCP.</strong> Verifique cada resultado e sua proveniência no relatório.</p>;
  return <p className="validation-note warning" role="status"><strong>Consulta PNCP indisponível.</strong> A ausência de resposta não foi tratada como validação.</p>;
}
