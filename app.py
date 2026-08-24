import streamlit as st
from dotenv import load_dotenv
from rag import RAG
from db.query import save_conversation, save_feedback

load_dotenv()

st.set_page_config(page_title="Paper Q&A", page_icon="📚", layout="wide")

MODELS = {
    "gpt-5.4-mini": "openai",
    "gpt-5-nano-2025-08-07": "openai",
    "deepseek-v4-flash": "deepseek",
    "deepseek-v4-pro": "deepseek",
}

if "rag" not in st.session_state:
    st.session_state.rag = RAG()
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gpt-5.4-mini"

if "history" not in st.session_state:
    st.session_state.history = []

st.title("📚 CS Research Paper Q&A")
st.caption("Ask questions about the computer science papers in the database.")

with st.sidebar:
    st.header("⚙️ Model")
    selected_model = st.selectbox(
        "Model",
        options=list(MODELS.keys()),
        index=list(MODELS.keys()).index(st.session_state.selected_model),
        label_visibility="collapsed",
    )
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model
        st.session_state.rag = RAG(model=selected_model, provider=MODELS[selected_model])
        st.session_state.history = []
        st.rerun()

    st.divider()
    st.header("📊 Session stats")
    rag = st.session_state.rag
    col1, col2 = st.columns(2)
    col1.metric("Questions asked", len(rag.usages))
    col2.metric("Total cost", f"${rag.total_cost:.4f}")

    if rag.last_usage:
        st.subheader("Last answer")
        m1, m2 = st.columns(2)
        m1.metric("Response time", f"{rag.last_usage['response_time']:.1f}s")
        m2.metric("LLM calls", rag.last_usage["llm_calls"])
        m3, m4 = st.columns(2)
        m3.metric("Tokens used", f"{rag.last_usage['total_tokens']:,}")
        m4.metric("Cost", f"${rag.last_usage['cost']:.4f}")

    st.divider()
    if st.button("🗑️ Clear history", use_container_width=True):
        st.session_state.rag = RAG(model=st.session_state.selected_model, provider=MODELS[st.session_state.selected_model])
        st.session_state.history = []
        st.rerun()

def render_feedback(entry, index):
    if not entry.get("conversation_id"):
        return
    feedback = entry.get("feedback")
    if feedback:
        st.caption("✅ Thanks for your feedback!" if feedback == "up" else "✅ Thanks, we'll use this to improve.")
        return
    col_up, col_down, _ = st.columns([1, 1, 10])
    if col_up.button("👍", key=f"feedback_up_{index}"):
        save_feedback(entry["conversation_id"], source="user", relevance="RELEVANT", score=1)
        entry["feedback"] = "up"
        st.rerun()
    if col_down.button("👎", key=f"feedback_down_{index}"):
        save_feedback(entry["conversation_id"], source="user", relevance="NON_RELEVANT", score=0)
        entry["feedback"] = "down"
        st.rerun()

for i, entry in enumerate(st.session_state.history):
    with st.chat_message("user", avatar="🧑‍💻"):
        st.write(entry["question"])
    with st.chat_message("assistant", avatar="📚"):
        st.write(entry["answer"])
        if entry["tool_calls"]:
            with st.expander(f"🔍 {len(entry['tool_calls'])} search call(s) made"):
                for call in entry["tool_calls"]:
                    st.markdown(f"**{call['tool']}**")
                    st.json(call["args"])
        st.caption(
            f"⏱️ {entry['usage']['response_time']:.1f}s · "
            f"🔢 {entry['usage']['total_tokens']:,} tokens · "
            f"💵 ${entry['usage']['cost']:.4f}"
        )
        render_feedback(entry, i)

question = st.chat_input("Ask a question about the papers...")

if question:
    with st.chat_message("user", avatar="🧑‍💻"):
        st.write(question)

    with st.chat_message("assistant", avatar="📚"):
        with st.spinner("🔎 Searching papers and thinking..."):
            answer = st.session_state.rag.rag(question)

    rag = st.session_state.rag
    try:
        conversation_id = save_conversation(rag.last_usage)
    except Exception as e:
        conversation_id = None
        st.warning(f"Couldn't save this conversation for monitoring: {e}")

    st.session_state.history.append({
        "question": question,
        "answer": answer,
        "tool_calls": rag.tool_calls,
        "usage": rag.last_usage,
        "conversation_id": conversation_id,
        "feedback": None,
    })
    st.rerun()
