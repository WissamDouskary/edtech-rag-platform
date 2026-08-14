CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 500


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP, min_chunk_size=MIN_CHUNK_SIZE):
    """Split text into overlapping ~500-1000 character chunks, breaking on
    whitespace near the boundary so words aren't cut mid-way."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = text.rfind(" ", start + min_chunk_size, end)
            if boundary != -1:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(pages):
    """pages: iterable of (page_number, text) -> list of {"page_number", "text"}."""
    result = []
    for page_number, text in pages:
        if not text or not text.strip():
            continue
        for chunk in chunk_text(text):
            result.append({"page_number": page_number, "text": chunk})
    return result
