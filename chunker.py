from config import CHUNK_OVERLAP, CHUNK_SIZE


def normalize_chunk_source(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    clean_text = normalize_chunk_source(text)
    if not clean_text:
        return []

    chunks = []
    start = 0

    while start < len(clean_text):
        end = min(start + chunk_size, len(clean_text))
        chunks.append(clean_text[start:end])

        if end == len(clean_text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def chunk_pages(pages: list[dict[str, str]]) -> list[dict[str, str | int]]:
    documents = []

    for page in pages:
        for index, chunk in enumerate(chunk_text(page["text"]), start=1):
            documents.append(
                {
                    "title": page["title"],
                    "url": page["url"],
                    "chunk_index": index,
                    "content": chunk,
                }
            )

    return documents
