import { Icon } from "./icon";

export function ResponsibleUse() {
  return (
    <aside className="responsible-use" role="note" aria-label="Aviso de uso responsável">
      <Icon name="info" />
      <span><strong>Análise preliminar</strong> — não substitui parecer jurídico.</span>
    </aside>
  );
}
