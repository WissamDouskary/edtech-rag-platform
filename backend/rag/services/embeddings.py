from functools import lru_cache

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384


@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_texts(texts):
    model = get_embedding_model()
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()


def embed_text(text):
    return embed_texts([text])[0]
