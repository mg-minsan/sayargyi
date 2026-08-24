import os
import meilisearch
from db.db import get_db_connection
from sentence_transformers import SentenceTransformer, CrossEncoder
from langchain_core.tools import tool

_model = SentenceTransformer("all-MiniLM-L6-v2", backend="onnx", model_kwargs={"file_name": "onnx/model_qint8_arm64.onnx", "provider": "CPUExecutionProvider"})
_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def get_meili_client():
    return meilisearch.Client(
        os.getenv("MEILI_HOST", "http://localhost:7700"),
        os.getenv("MEILI_MASTER_KEY", "masterkey"),
    )


def vector_search(query: str, num_results: int = 5) -> list[dict]:
    conn = get_db_connection()
    query_embedding = _model.encode(query, convert_to_numpy=True).tolist()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT paper_id, title, tags, filename, chunk_index, content,
                       embedding <=> %s::vector AS distance
                FROM paper_chunks
                ORDER BY distance
                LIMIT %s
                """,
                (query_embedding, num_results),
            )
            results = cur.fetchall()
            return [
                {
                    "paper_id": row[0],
                    "title": row[1],
                    "tags": row[2],
                    "filename": row[3],
                    "chunk_index": row[4],
                    "content": row[5],
                }
                for row in results
            ]
    finally:
        conn.close()


def fulltext_search(query: str, num_results: int = 5,
                    attributesToSearchOn: list[str] = ["title", "tags", "content"] ,
                    rankingRules: list[str] | None = None,
                    filter_dict: dict | None = None,) -> list[dict]:
    client = get_meili_client()
    filters = " AND ".join(f'{k} = "{v}"' for k, v in (filter_dict or {}).items())
    if rankingRules is not None:
        client.index("paper_chunks").update_ranking_rules(rankingRules)
    
    results = client.index("paper_chunks").search(query, {
        "limit": num_results,
        "attributesToSearchOn": attributesToSearchOn,
        "matchingStrategy": "frequency",
        "filter": filters or None,
        "showRankingScore": True,
    })
    return [
        {
            "paper_id": hit["paper_id"],
            "title": hit["title"],
            "tags": hit["tags"],
            "filename": hit["filename"],
            "chunk_index": hit["chunk_index"],
            "content": hit["content"],
        }
        for hit in results["hits"]
    ]

def rrf(search_results, k=1, num_results=10, weights: list[float] = [1.0, 1.0]) -> list[dict]:
    scores = {}
    doc_map = {}

    if weights is None:
        weights = [1.0] * len(search_results)

    for results, weight in zip(search_results, weights):
        for rank, doc in enumerate(results):
            key = (doc["filename"], doc["chunk_index"])
            if key not in scores:
                scores[key] = 0
                doc_map[key] = doc
            scores[key] += weight / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_map[key] for key, _ in ranked[:num_results]]

@tool
def search(query: str, num_results: int =10) -> list[dict]:
    """
    Search academic paper chunks using hybrid retrieval (keyword + semantic).

    Use this tool to answer questions about computer science research papers.
    Combines full-text search (Meilisearch) and vector similarity search (pgvector)
    using Reciprocal Rank Fusion (RRF) to produce a single ranked result list.

    Args:
        query: The user's question or search query in natural language.
        num_results: Number of results to return. Default is 10.

    Returns:
        list[dict]: Ranked list of relevant paper chunks, each containing:
            - paper_id (str): Unique identifier for the paper.
            - title (str): Title of the paper.
            - tags (list[str]): Topic tags for the paper.
            - filename (str): Source PDF filename.
            - chunk_index (int): Position of this chunk within the paper.
            - content (str): The actual text content of the chunk.
    """
    keyword_results = fulltext_search(query, num_results=(num_results * 2))
    vector_results = vector_search(query, num_results=num_results * 2)
    return reranker(query, rrf([keyword_results, vector_results], num_results=num_results, weights=[0.25, 0.75]), num_results=num_results)

def hybrid_search(query: str, num_results: int =10,
                  weights: list[float] | None = None, rerank: bool = True) -> list[dict]:
    keyword_results = fulltext_search(query, num_results=(num_results * 2))
    vector_results = vector_search(query, num_results=num_results * 2)
    if rerank:
        return reranker(query, rrf([keyword_results, vector_results], num_results=num_results, weights=weights), num_results=num_results)
    else:
        return rrf([keyword_results, vector_results], num_results=num_results, weights=weights)

def reranker(query, candidates, num_results=10):
    pairs = [(query, candidate["content"]) for candidate in candidates]
    scores = _reranker.predict(pairs)
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [candidate for candidate, _ in ranked[:num_results]]
