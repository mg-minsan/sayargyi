from dotenv import load_dotenv
from db.query import save_conversation, save_feedback
from judge import evaluate_relevance
from rag import RAG

def main():
    print("Initializing RAG system...")
    rag = RAG(model="deepseek-v4-flash", provider="deepseek")
    print("RAG system initialized. Running test query...")
    answer = rag.rag("What is bitcoin?")
    print(answer)
    print(rag.last_usage)
    conversation_id = save_conversation(rag.last_usage)
    save_feedback(conversation_id, source="user", relevance="relevant", explanation="The answer is relevant to the question about bitcoin.", score=1)
    relevance, score, explanation = evaluate_relevance("What is bitcoin?", answer)
    save_feedback(conversation_id, source="judge", relevance=relevance, explanation=explanation, score=score)

if __name__ == "__main__":
    load_dotenv()
    main()
