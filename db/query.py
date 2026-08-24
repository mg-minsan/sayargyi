from db.db import get_db_connection
from datetime import datetime, timezone


def save_conversation(conversation: dict) -> str:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                    prompt, answer, model,
                    input_tokens, output_tokens, total_tokens,
                    llm_calls, cost, response_time
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    conversation["prompt"],
                    conversation["answer"],
                    conversation["model"],
                    conversation["input_tokens"],
                    conversation["output_tokens"],
                    conversation["total_tokens"],
                    conversation["llm_calls"],
                    conversation["cost"],
                    conversation["response_time"],
                ),
            )
            conversation_id = cur.fetchone()[0]
        conn.commit()
        return str(conversation_id)
    finally:
        conn.close()


def save_feedback(conversation_id: str, source: str, relevance: str = None, explanation: str = None, score: int = None) -> int:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (
                    conversation_id, source, relevance, explanation, score, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (conversation_id, source, relevance, explanation, score, datetime.now(timezone.utc)),
            )
            feedback_id = cur.fetchone()[0]
        conn.commit()
        return feedback_id
    finally:
        conn.close()
