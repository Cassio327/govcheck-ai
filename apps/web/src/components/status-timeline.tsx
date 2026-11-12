const STEPS = [
  "Leitura do PDF",
  "Indexação",
  "Extração",
  "Validação PNCP",
  "Crítica de evidências",
  "Relatório",
];

export function StatusTimeline({ completed, running = false }: { completed: number; running?: boolean }) {
  const bounded = Math.max(0, Math.min(completed, STEPS.length));
  return (
    <section className="timeline" aria-label="Progresso da análise">
      <p className="timeline-summary">{bounded} de {STEPS.length} etapas concluídas</p>
      <div className="timeline-progress" aria-hidden="true"><span style={{ width: `${(bounded / STEPS.length) * 100}%` }} /></div>
      <ol>
        {STEPS.map((step, index) => (
          <li key={step} className={index < bounded ? "complete" : running && index === bounded ? "active" : ""}>
            <span>{index < bounded ? "✓" : index + 1}</span>
            <small>{step}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}
