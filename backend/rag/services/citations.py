import re

CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def extract_citations(answer_text, enriched_chunks):
    """enriched_chunks: list of dicts (1 per retrieved passage, in prompt order)
    each with document_id, document_filename, chunk_id, page_number, text.
    Returns only the citation numbers actually referenced in the answer."""
    used_indexes = sorted(
        {
            int(n)
            for n in CITATION_PATTERN.findall(answer_text)
            if 1 <= int(n) <= len(enriched_chunks)
        }
    )
    citations = []
    for idx in used_indexes:
        chunk = enriched_chunks[idx - 1]
        citations.append(
            {
                "index": idx,
                "document_id": chunk["document_id"],
                "document_filename": chunk["document_filename"],
                "page_number": chunk["page_number"],
                "chunk_id": chunk["chunk_id"],
                "excerpt": chunk["text"][:240],
            }
        )
    return citations
