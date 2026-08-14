from django.conf import settings

from .embeddings import embed_text
from .vector_store import query_chunks


def retrieve_chunks(owner_id, document_ids, query_text, top_k=None):
    """Top-k similarity search scoped to the given owner and (optionally) a
    specific set of document ids. `document_ids=None` searches the whole
    workspace (still scoped to that owner's vectors only)."""
    top_k = top_k or settings.RAG_TOP_K
    embedding = embed_text(query_text)

    if document_ids:
        where = {"$and": [{"owner_id": owner_id}, {"document_id": {"$in": list(document_ids)}}]}
    else:
        where = {"owner_id": owner_id}

    results = query_chunks(embedding, n_results=top_k, where=where)

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks = []
    for vector_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        chunks.append(
            {
                "vector_id": vector_id,
                "text": text,
                "document_id": metadata["document_id"],
                "page_number": metadata["page_number"],
                "distance": distance,
            }
        )
    return chunks
