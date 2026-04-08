"""
CULTR Ventures — Embedding Tasks
GPU-bound tasks for vector embedding generation and similarity search.
Runs on the 'gpu' Celery queue, routed to workers with GPU access.
"""

import logging
from pathlib import Path

import httpx
from celery import shared_task

from app.config import get_settings

logger = logging.getLogger("cultr.embeddings")
settings = get_settings()


@shared_task(
    name="app.workers.embedding_tasks.embed_document",
    queue="gpu",
    time_limit=120,
)
def embed_document(file_path: str, collection: str = "cultr_knowledge") -> dict:
    """
    Generate embeddings for a vault document and upsert into Qdrant.
    Uses local BGE-large-en-v1.5 on GPU node (10.0.0.2:8081).
    """
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    content = path.read_text(encoding="utf-8")

    # Chunk the document (simple paragraph-based chunking)
    chunks = _chunk_document(content, max_chunk_size=512)
    logger.info(f"Chunked {file_path} into {len(chunks)} chunks")

    # Generate embeddings via local model
    embeddings = []
    for chunk in chunks:
        embedding = _get_embedding(chunk)
        if embedding:
            embeddings.append({"text": chunk, "vector": embedding})

    # Upsert to Qdrant
    if embeddings:
        _upsert_to_qdrant(embeddings, collection, source_path=file_path)

    return {
        "status": "completed",
        "file": file_path,
        "chunks": len(chunks),
        "embedded": len(embeddings),
    }


@shared_task(
    name="app.workers.embedding_tasks.embed_vault_batch",
    queue="gpu",
    time_limit=600,
)
def embed_vault_batch(directory: str = "/app/memory") -> dict:
    """Re-embed all .md files in a vault directory."""
    vault = Path(directory)
    files = list(vault.rglob("*.md"))
    results = []

    for f in files:
        result = embed_document(str(f))
        results.append(result)

    total = len(results)
    success = sum(1 for r in results if r["status"] == "completed")
    return {
        "status": "completed",
        "total_files": total,
        "successful": success,
        "failed": total - success,
    }


def _chunk_document(content: str, max_chunk_size: int = 512) -> list[str]:
    """Split document into chunks by paragraphs, respecting max size."""
    # Remove frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]

    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk += ("\n\n" + para if current_chunk else para)
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _get_embedding(text: str) -> list[float] | None:
    """Get embedding vector from local BGE model on GPU node."""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{settings.EMBEDDINGS_URL}/embed",
                json={"inputs": text},
            )
            response.raise_for_status()
            return response.json()[0]  # TEI returns list of embeddings
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return None


def _upsert_to_qdrant(
    embeddings: list[dict],
    collection: str,
    source_path: str,
) -> None:
    """Upsert embedding vectors to Qdrant."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        import uuid

        client = QdrantClient(url=settings.QDRANT_URL)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb["vector"],
                payload={
                    "text": emb["text"],
                    "source_path": source_path,
                },
            )
            for emb in embeddings
        ]

        client.upsert(collection_name=collection, points=points)
        logger.info(f"Upserted {len(points)} vectors to {collection}")

    except Exception as e:
        logger.error(f"Qdrant upsert failed: {e}")
        raise
