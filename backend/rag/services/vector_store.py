from functools import lru_cache

import chromadb
from django.conf import settings

CHUNKS_COLLECTION_NAME = "document_chunks"


@lru_cache(maxsize=1)
def get_chroma_client():
    return chromadb.PersistentClient(path=str(settings.CHROMA_PERSIST_DIR))


def get_chunks_collection():
    return get_chroma_client().get_or_create_collection(CHUNKS_COLLECTION_NAME)


def add_chunks(vector_ids, embeddings, documents, metadatas):
    if not vector_ids:
        return
    get_chunks_collection().add(
        ids=vector_ids, embeddings=embeddings, documents=documents, metadatas=metadatas
    )


def delete_document_vectors(document_id):
    get_chunks_collection().delete(where={"document_id": document_id})


def query_chunks(query_embedding, n_results=5, where=None):
    return get_chunks_collection().query(
        query_embeddings=[query_embedding], n_results=n_results, where=where
    )
