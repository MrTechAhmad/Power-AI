import streamlit as st

from services import assistant_service
from ui.common import show_error, show_table

EXAMPLES = ["Which products are low on stock?", "How are sales today?",
            "Forecast for milk", "What goes with bread?"]


def render_ai_assistant_page():
    st.title("💬 AI Assistant")
    st.caption("Ask about stock, sales, forecasts and recommendations. "
               "Every question is logged in MongoDB (ai_logs).")

    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "assistant", "text": assistant_service.HELP_TEXT, "table": None}]

    # Example buttons
    cols = st.columns(len(EXAMPLES))
    clicked = None
    for col, example in zip(cols, EXAMPLES):
        if col.button(example, width="stretch"):
            clicked = example

    # Chat history
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])
            if msg["table"] is not None:
                show_table(msg["table"])

    question = st.chat_input("Ask a question...") or clicked
    if question:
        try:
            text, table, _ = assistant_service.answer(question)
        except Exception as e:
            show_error(e)
            return
        st.session_state.chat.append({"role": "user", "text": question, "table": None})
        st.session_state.chat.append({"role": "assistant", "text": text, "table": table})
        st.rerun()

    if len(st.session_state.chat) > 1 and st.button("Clear chat"):
        del st.session_state["chat"]
        st.rerun()
