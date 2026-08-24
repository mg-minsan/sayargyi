import json
import os
from pathlib import Path

import psycopg
import meilisearch
from dotenv import load_dotenv
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

load_dotenv()

PAPERS_DIR = Path(__file__).parent.parent / "papers"
_model = SentenceTransformer("all-MiniLM-L6-v2", backend="onnx", model_kwargs={"file_name": "onnx/model_qint8_arm64.onnx", "provider": "CPUExecutionProvider"})


def embed(texts: list[str]) -> list[list[float]]:
    return _model.encode(texts, convert_to_numpy=True).tolist()


def get_meili_client():
    return meilisearch.Client(
        os.getenv("MEILI_HOST", "http://localhost:7700"),
        os.getenv("MEILI_MASTER_KEY", "masterkey"),
    )


STOP_WORDS = [
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "doing", "would", "should",
    "could", "ought", "i", "you", "he", "she", "it", "we", "they", "them",
    "his", "her", "its", "our", "their", "this", "that", "these", "those",
    "what", "which", "who", "whom", "how", "why", "where", "when",
    "not", "no", "nor", "as", "of", "so", "than", "too", "very", "can",
    "will", "just", "there", "here", "all", "any", "both", "each", "more",
    "most", "other", "some", "such", "only", "own", "same", "also",
]


def setup_meili_index():
    client = get_meili_client()
    index = client.index("paper_chunks")
    tasks = [
        index.update_searchable_attributes(["title", "tags", "content"]),
        index.update_filterable_attributes(["paper_id", "tags", "title"]),
        index.update_stop_words(STOP_WORDS),
        index.update_ranking_rules([
            "words",
            "typo",
            "attribute",
            "proximity",
            "exactness",
        ]),
    ]
    for task in tasks:
        result = client.wait_for_task(task.task_uid)
        if result.status != "succeeded":
            print(f"  [meili] settings update FAILED: {result.error}")


def ingest_meili(paper_id, title, tags, content, filename, chunks):
    client = get_meili_client()
    index = client.index("paper_chunks")
    safe_id = paper_id.replace("/", "_").replace(" ", "_")
    documents = [
        {
            "id": f"{safe_id}_{i}",
            "paper_id": paper_id,
            "title": title,
            "tags": tags,
            "filename": filename,
            "chunk_index": i,
            "content": chunk,
        }
        for i, chunk in enumerate(chunks)
    ]
    task = index.add_documents(documents, primary_key="id")
    print(f"  [meili] queued {len(documents)} docs for '{paper_id}', taskUid={task.task_uid}")
    result = client.wait_for_task(task.task_uid, timeout_in_ms=120000)
    if result.status != "succeeded":
        print(f"  [meili] FAILED for '{paper_id}': {result.error}")
    else:
        print(f"  [meili] OK '{paper_id}'")


def ingest_paper(conn, filepath: Path) -> int:
    with open(filepath) as f:
        paper = json.load(f)

    title = paper.get("title", "")
    tags = paper.get("tags", [])
    content = paper.get("content", "")
    filename = paper.get("source_pdf", "")
    paper_id = filepath.stem

    if not content:
        return 0

    return ingest_vector(conn, paper_id, title, tags, content, filename)


def ingest_vector(conn, paper_id, title, tags, content, filename):
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[
        ("#", "section"),
        ("##", "subsection"),
    ])
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    header_docs = header_splitter.split_text(content)
    chunks = char_splitter.split_text("\n\n".join(d.page_content if hasattr(d, "page_content") else d for d in header_docs))
    ingest_meili(paper_id, title, tags, content, filename, chunks)
    embeddings = embed(chunks)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM paper_chunks WHERE paper_id = %s", (paper_id,)
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                """
                INSERT INTO paper_chunks (paper_id, title, tags, filename, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (paper_id, title, tags, filename, i, chunk, embedding),
            )
    conn.commit()
    return len(chunks)

def main():
    conn = psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        dbname=os.getenv("POSTGRES_DB", "sayargyi"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )
    client = get_meili_client()
    task = client.delete_index("paper_chunks")
    client.wait_for_task(task.task_uid, timeout_in_ms=120000)
    task = client.create_index("paper_chunks", {"primaryKey": "id"})
    client.wait_for_task(task.task_uid, timeout_in_ms=120000)
    print("Recreated Meilisearch index")
    setup_meili_index()
    with conn:
        files = sorted(PAPERS_DIR.glob("*.json"))
        print(f"Found {len(files)} papers")

        total_chunks = 0
        for filepath in files:
            try:
                n = ingest_paper(conn, filepath)
                print(f"  {filepath.name}: {n} chunks")
                total_chunks += n
            except Exception as e:
                print(f"  ERROR {filepath.name}: {e}")

        print(f"\nDone. {total_chunks} total chunks ingested.")


if __name__ == "__main__":
    main()
