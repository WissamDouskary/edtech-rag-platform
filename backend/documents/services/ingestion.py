import logging

from django.db import transaction

from rag.services.embeddings import embed_texts
from rag.services.vector_store import add_chunks, delete_document_vectors

from .chunking import chunk_pages
from .extraction import PdfExtractionError, extract_pages_text
from .storage import delete_object, get_object_bytes

logger = logging.getLogger(__name__)


def ingest_document(document):
    from ..models import Document, DocumentChunk

    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status", "updated_at"])

    try:
        pdf_bytes = get_object_bytes(document.storage_key)
        pages = extract_pages_text(pdf_bytes)

        chunks = chunk_pages(pages)
        if not chunks:
            raise PdfExtractionError(
                "Aucun contenu exploitable n'a été trouvé dans le document."
            )

        texts = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)

        vector_ids = [f"doc{document.id}-chunk{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": document.id,
                "owner_id": document.owner_id,
                "page_number": chunk["page_number"],
                "chunk_index": i,
            }
            for i, chunk in enumerate(chunks)
        ]

        # Clear any leftover vectors from a previous failed/retried attempt.
        delete_document_vectors(document.id)
        add_chunks(vector_ids, embeddings, texts, metadatas)

        try:
            with transaction.atomic():
                DocumentChunk.objects.filter(document=document).delete()
                DocumentChunk.objects.bulk_create(
                    [
                        DocumentChunk(
                            document=document,
                            chunk_index=i,
                            page_number=chunk["page_number"],
                            char_count=len(chunk["text"]),
                            vector_id=vector_id,
                        )
                        for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids))
                    ]
                )
                document.page_count = pages[-1][0] if pages else 0
                document.status = Document.Status.READY
                document.failure_reason = ""
                document.save(
                    update_fields=["page_count", "status", "failure_reason", "updated_at"]
                )
        except Exception:
            delete_document_vectors(document.id)
            raise

    except PdfExtractionError as exc:
        logger.warning("Ingestion failed for document %s: %s", document.id, exc)
        document.status = Document.Status.FAILED
        document.failure_reason = str(exc)
        document.save(update_fields=["status", "failure_reason", "updated_at"])
    except Exception:
        logger.exception("Unexpected ingestion error for document %s", document.id)
        document.status = Document.Status.FAILED
        document.failure_reason = "Erreur interne lors du traitement du document."
        document.save(update_fields=["status", "failure_reason", "updated_at"])

    return document


def delete_document_fully(document):
    delete_document_vectors(document.id)
    try:
        delete_object(document.storage_key)
    except Exception:
        logger.warning("Could not delete MinIO object for document %s", document.id, exc_info=True)
    document.delete()
