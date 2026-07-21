from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Experiment, Run, SearchDocument


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    settings.embedding_cache_path.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(model_name=settings.embedding_model, cache_dir=str(settings.embedding_cache_path))


def embed_text(text: str) -> list[float] | None:
    if not settings.embeddings_enabled or not text.strip():
        return None
    try:
        return next(_model().embed([text])).tolist()
    except Exception:
        # Keyword search remains available if a model cannot be downloaded or loaded.
        return None


def experiment_text(item: Experiment) -> str:
    return "\n".join(
        part for part in [item.display_id, item.title, item.hypothesis, item.reasoning,
                          item.implementation_details, json.dumps(item.configuration, sort_keys=True)] if part
    )


def run_text(item: Run) -> str:
    return "\n".join(
        part for part in [item.display_id, item.name, item.hypothesis, item.reasoning,
                          item.change_summary, item.result_summary, item.conclusion,
                          item.decision_changed, json.dumps(item.configuration, sort_keys=True),
                          json.dumps(item.evidence_used, sort_keys=True)] if part
    )


def index_document(session: Session, item: Experiment | Run) -> None:
    document_type = "experiment" if isinstance(item, Experiment) else "run"
    content = experiment_text(item) if isinstance(item, Experiment) else run_text(item)
    document = session.scalar(
        select(SearchDocument).where(
            SearchDocument.document_type == document_type,
            SearchDocument.source_id == item.id,
        )
    )
    if document is None:
        document = SearchDocument(
            project_id=item.project_id,
            document_type=document_type,
            source_id=item.id,
            content=content,
        )
        session.add(document)
    document.content = content
    is_postgres = session.bind is not None and session.bind.dialect.name == "postgresql"
    document.embedding = embed_text(content) if is_postgres else None


def semantic_matches(session: Session, project_id: str, query: str, limit: int) -> dict[tuple[str, str], float]:
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return {}
    vector = embed_text(query)
    if vector is None:
        return {}
    distance = SearchDocument.embedding.cosine_distance(vector)
    rows = session.execute(
        select(SearchDocument.document_type, SearchDocument.source_id, distance.label("distance"))
        .where(SearchDocument.project_id == project_id, SearchDocument.embedding.is_not(None))
        .order_by(distance)
        .limit(limit * 3)
    ).all()
    return {(kind, source_id): max(0.0, 1.0 - float(value)) for kind, source_id, value in rows}
