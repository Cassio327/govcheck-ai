import asyncio
from datetime import timedelta
from typing import Literal
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from govcheck.application.analysis.nodes import build_nodes
from govcheck.application.analysis.state import AnalysisDependencies, AnalysisState
from govcheck.domain.documents import AnalysisJob, utc_now
from govcheck.domain.repositories import ActiveAnalysisConflict


def build_analysis_graph(dependencies: AnalysisDependencies):
    extract, external_validation, validation_skipped, evidence_critic, synthesize = build_nodes(
        dependencies
    )
    graph = StateGraph(AnalysisState)
    graph.add_node("extract", extract)
    graph.add_node("external_validation", external_validation)
    graph.add_node("validation_skipped", validation_skipped)
    graph.add_node("evidence_critic", evidence_critic)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "extract")

    def route_validation(state: AnalysisState) -> Literal["validate", "skip"]:
        if any(draft.external_identifier for draft in state["drafts"]):
            return "validate"
        return "skip"

    graph.add_conditional_edges(
        "extract",
        route_validation,
        {"validate": "external_validation", "skip": "validation_skipped"},
    )
    graph.add_edge("external_validation", "evidence_critic")
    graph.add_edge("validation_skipped", "evidence_critic")
    graph.add_edge("evidence_critic", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


class DocumentNotAccessible(LookupError):
    """Does not disclose cross-session document existence."""


class AnalysisAlreadyRunning(RuntimeError):
    """Raised when a session already owns an active analysis job."""


class RunAnalysis:
    def __init__(
        self,
        dependencies: AnalysisDependencies,
        *,
        active_job_timeout_minutes: int = 10,
    ) -> None:
        if active_job_timeout_minutes < 1:
            raise ValueError("active_job_timeout_minutes must be positive")
        self._dependencies = dependencies
        self._graph = build_analysis_graph(dependencies)
        self._start_lock = asyncio.Lock()
        self._active_job_timeout = timedelta(minutes=active_job_timeout_minutes)

    async def start(self, session_id: str, document_id: UUID) -> AnalysisJob:
        job = AnalysisJob(document_id=document_id, session_id=session_id, status="running")
        async with self._start_lock:
            try:
                async with self._dependencies.unit_of_work_factory() as unit_of_work:
                    document = await unit_of_work.documents.get_owned(document_id, session_id)
                    if document is None:
                        raise DocumentNotAccessible("document not found")
                    await unit_of_work.events.fail_stale_for_session(
                        session_id,
                        utc_now() - self._active_job_timeout,
                    )
                    if await unit_of_work.events.active_for_session(session_id) is not None:
                        raise AnalysisAlreadyRunning("session already has an active analysis")
                    await unit_of_work.events.add_job(job)
                    await unit_of_work.events.append(job.id, "analysis.started", {})
                    await unit_of_work.commit()
            except ActiveAnalysisConflict as error:
                raise AnalysisAlreadyRunning("session already has an active analysis") from error
        return job

    async def run(self, job: AnalysisJob) -> AnalysisJob:
        initial_state: AnalysisState = {
            "job_id": job.id,
            "document_id": job.document_id,
            "session_id": job.session_id,
            "evidence": [],
            "drafts": [],
            "validations": {},
            "findings": [],
        }
        try:
            await self._graph.ainvoke(initial_state)
        except Exception:
            await self._finish(job.id, "failed", "analysis.failed")
            raise
        await self._finish(job.id, "completed", "analysis.completed")
        return job.model_copy(update={"status": "completed"})

    async def execute(self, session_id: str, document_id: UUID) -> AnalysisJob:
        job = await self.start(session_id, document_id)
        return await self.run(job)

    async def _finish(self, job_id: UUID, status: str, event_type: str) -> None:
        async with self._dependencies.unit_of_work_factory() as unit_of_work:
            await unit_of_work.events.update_job_status(job_id, status)
            await unit_of_work.events.append(job_id, event_type, {})
            await unit_of_work.commit()


__all__ = [
    "AnalysisAlreadyRunning",
    "AnalysisDependencies",
    "RunAnalysis",
    "build_analysis_graph",
]
