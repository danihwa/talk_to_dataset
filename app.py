import asyncio
import os
import re
from urllib.parse import urlparse

import streamlit as st

from src.agent import run_question
from src.cli import load_secrets

st.set_page_config(page_title="Data Q&A Agent", layout="wide")
load_secrets()

missing = [k for k in ("OPENAI_API_KEY", "SUPABASE_DB_URL") if not os.environ.get(k)]
if missing:
    st.error(f"Set {' and '.join(missing)} in ~/secrets/.env or your host's secrets.")
    st.stop()


def _project_label(url: str) -> str:
    host = urlparse(url).hostname or ""
    m = re.search(r"db\.([a-z0-9]+)\.supabase\.co", host)
    if m:
        return m.group(1)
    m = re.search(r"\.([a-z0-9-]+)\.pooler\.supabase\.com", host)
    if m:
        return host
    return host or "(unknown)"


st.session_state.setdefault("messages", [])

with st.sidebar:
    st.caption(f"Connected to **{_project_label(os.environ['SUPABASE_DB_URL'])}**")
    if st.button("Clear chat", disabled=not st.session_state.messages):
        st.session_state.messages = []

st.title("Data Q&A Agent")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Ask a question about your data")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer = asyncio.run(run_question(question))
            except Exception as exc:
                answer = f"⚠️ Something went wrong: {exc}"
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
