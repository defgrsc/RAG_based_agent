import time
from typing import Any

from chunker import chunk_pages
from config import (
    CRAWL_MAX_PAGES,
    INGEST_EMBED_BATCH_SIZE,
    NTHU_PRIORITY_URLS,
    NTHU_SEED_URLS,
)
from crawler import crawl_pages
from document_metadata import (
    annotate_documents,
    summarize_document_metadata,
    validate_document_metadata,
)
from llm import embed_texts
from qdrant_store import upsert_documents
from wireless_coverage import build_coverage_documents


def _embed_documents(
    documents: list[dict[str, Any]],
    batch_size: int = INGEST_EMBED_BATCH_SIZE,
) -> list[list[float]]:
    if batch_size < 1:
        raise ValueError("embedding batch size must be at least 1")

    vectors: list[list[float]] = []
    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        batch_vectors = embed_texts([document["content"] for document in batch])
        if len(batch_vectors) != len(batch):
            raise ValueError(
                "embedding service returned "
                f"{len(batch_vectors)} vectors for {len(batch)} documents"
            )
        vectors.extend(batch_vectors)
    return vectors


def ingest_nthu_docs(replace: bool = True) -> dict[str, Any]:
    total_start = time.perf_counter()

    crawl_start = time.perf_counter()
    pages = crawl_pages([*NTHU_PRIORITY_URLS, *NTHU_SEED_URLS], CRAWL_MAX_PAGES)
    crawl_time = time.perf_counter() - crawl_start

    documents = annotate_documents([
        *chunk_pages(pages),
        *build_coverage_documents(),
    ])
    if not documents:
        total_time = time.perf_counter() - total_start
        print("Crawler produced 0 chunks. Qdrant was not modified.")
        print(f"Crawler Time: {crawl_time:.3f}s")
        print("Embedding Time: 0.000s")
        print("Qdrant Time: 0.000s")
        print(f"Total Time: {total_time:.3f}s")
        print(f"Pages: {len(pages)}")
        print("Chunks: 0")

        return {
            "updated": False,
            "pages": len(pages),
            "chunks": 0,
            "crawl_time": crawl_time,
            "embedding_time": 0.0,
            "qdrant_time": 0.0,
            "total_time": total_time,
        }

    validate_document_metadata(documents)
    metadata_summary = summarize_document_metadata(documents)

    embedding_start = time.perf_counter()
    vectors = _embed_documents(documents)
    embedding_time = time.perf_counter() - embedding_start

    qdrant_start = time.perf_counter()
    active_collection = upsert_documents(documents, vectors, replace=replace)
    qdrant_time = time.perf_counter() - qdrant_start

    total_time = time.perf_counter() - total_start

    print(f"Crawler Time: {crawl_time:.3f}s")
    print(f"Embedding Time: {embedding_time:.3f}s")
    print(f"Qdrant Time: {qdrant_time:.3f}s")
    print(f"Total Time: {total_time:.3f}s")
    print(f"Pages: {len(pages)}")
    print(f"Chunks: {len(documents)}")
    print(f"Qdrant Replace: {replace}")
    print(f"Metadata: {metadata_summary}")

    return {
        "updated": True,
        "replace": replace,
        "pages": len(pages),
        "chunks": len(documents),
        "crawl_time": crawl_time,
        "embedding_time": embedding_time,
        "qdrant_time": qdrant_time,
        "total_time": total_time,
        "active_collection": active_collection,
        "metadata": metadata_summary,
    }


def ingest_wireless_coverage() -> dict[str, Any]:
    """Upsert only structured coverage records without rebuilding the collection."""
    total_start = time.perf_counter()
    documents = annotate_documents(build_coverage_documents())
    validate_document_metadata(documents)
    metadata_summary = summarize_document_metadata(documents)

    embedding_start = time.perf_counter()
    vectors = _embed_documents(documents)
    embedding_time = time.perf_counter() - embedding_start

    qdrant_start = time.perf_counter()
    active_collection = upsert_documents(documents, vectors, replace=False)
    qdrant_time = time.perf_counter() - qdrant_start
    total_time = time.perf_counter() - total_start

    return {
        "updated": True,
        "replace": False,
        "pages": 2,
        "chunks": len(documents),
        "crawl_time": 0.0,
        "embedding_time": embedding_time,
        "qdrant_time": qdrant_time,
        "total_time": total_time,
        "active_collection": active_collection,
        "metadata": metadata_summary,
    }


if __name__ == "__main__":
    ingest_nthu_docs(replace=True)
