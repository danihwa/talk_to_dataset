import asyncio
import os
import re
from urllib.parse import urlparse

import streamlit as st

from src.agent import run_question
from src.cli import load_secrets

st.set_page_config(page_title="Data Q&A Agent", layout="wide")

st.markdown(
    """
    <style>
    h1 {
        background: linear-gradient(90deg, #7C3AED 0%, #A78BFA 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent;
        letter-spacing: -0.02em;
    }
    .block-container { padding-top: 3rem; }
    [data-testid="stChatMessage"]:has([data-testid*="Assistant"]) {
        border-left: 3px solid #7C3AED;
        background: rgba(124, 58, 237, 0.04);
    }
    [data-testid="stChatMessage"] pre {
        background: #0B0E13;
        border-left: 2px solid #7C3AED;
        border-radius: 6px;
        padding: 12px 14px;
    }
    [data-testid="stChatMessage"] code {
        font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: 0.875rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

load_secrets()

missing = [k for k in ("OPENAI_API_KEY", "SUPABASE_DB_URL") if not os.environ.get(k)]
if missing:
    st.error(f"Set {' and '.join(missing)} in ~/secrets/.env or your host's secrets.")
    st.stop()


def _project_label(url: str) -> str:
    """Pull a friendly Supabase project ref from the connection URL for the sidebar."""
    host = urlparse(url).hostname or ""
    m = re.search(r"db\.([a-z0-9]+)\.supabase\.co", host)
    if m:
        return m.group(1)
    m = re.search(r"\.([a-z0-9-]+)\.pooler\.supabase\.com", host)
    if m:
        return host
    return host or "(unknown)"


st.session_state.setdefault("messages", [])
st.session_state.setdefault("agent_history", [])

with st.sidebar:
    project = _project_label(os.environ["SUPABASE_DB_URL"])
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;font-size:0.875rem;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:#22C55E;'
        f'box-shadow:0 0 8px rgba(34,197,94,0.6);"></span>'
        f"<span>Connected to <strong>{project}</strong></span></div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("**About**")
    st.caption(
        "Natural-language Q&A over a Supabase Postgres database. "
        "The agent inspects the schema, writes a `SELECT`, runs it through "
        "a read-only role, and replies with the answer plus the SQL it ran."
    )
    st.divider()
    if st.button(
        "Clear chat", disabled=not st.session_state.messages, use_container_width=True
    ):
        st.session_state.messages = []
        st.session_state.agent_history = []
    st.divider()
    st.caption("Built with Streamlit + OpenAI Agents SDK")
    st.caption("Powered by AI — answers can be wrong; verify important results.")

st.title("Data Q&A Agent")
st.caption(
    "Ask questions in plain English or Czech — answered with live SQL against your Supabase database."
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not st.session_state.messages:
    with st.expander("Try an example", expanded=True):
        examples = [
            "What are three highest-rated dramas with at least 10,000 watchers?",
            "Show me the most-watched historical dramas",
            "Which genres tend to have higher ratings?",
        ]
        cols = st.columns(len(examples))
        for col, ex in zip(cols, examples):
            if col.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state["pending_question"] = ex
                st.rerun()

# Streamlit can't programmatically fill st.chat_input, so example buttons
# stash their text under "pending_question" and trigger a rerun; here we
# pop it (single-read) so the click takes effect on the next pass only.
question = st.chat_input("Ask a question about your data") or st.session_state.pop(
    "pending_question", None
)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer, st.session_state.agent_history = asyncio.run(
                    run_question(question, st.session_state.agent_history)
                )
            except Exception as exc:
                answer = f"⚠️ Something went wrong: {exc}"
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
