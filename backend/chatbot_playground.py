from __future__ import annotations

import sys
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from app.routes.sessions import get_session
from app.schemas.chat import ChatAnswer, ChatQuestionRequest  
from app.services import chatbot_service 

st.set_page_config(page_title="Perpetuity AI (Alpha)", layout="wide")

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
MAX_TABLES_TO_RETREIVE = 3
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def get_session_id_from_url() -> str | None:
    params = st.query_params
    value = params.get("session_id")
    if isinstance(value, list):
        return value[0] if value else None
    return value

session_id = get_session_id_from_url()

if not session_id:
    st.error("No session_id provided in the URL. Please open this app via the main application.")
    st.stop()

# Optional: cache to avoid re-fetching every rerun
# @st.cache_data(show_spinner=True)
def load_session_payload(session_id: str):
    if session_id == 'sample':
        data = json.load(open('backend/app/constants/mapped_sample.json', 'r'))
    else:
        data = asyncio.run(get_session(session_id))
        print('Session-data:', data)
    return data

st.session_state["session_payload"] = load_session_payload(session_id)

if st.session_state["session_payload"] is None:
    st.error("Could not load data for this session. It may have expired or be invalid.")
    st.stop()

def _reset_conversation(payload_label: str, session_payload: Dict[str, Any]) -> None:
    st.session_state["session_payload"] = session_payload
    st.session_state["payload_label"] = payload_label
    st.session_state["chat_history"] = []


from typing import Any, Dict, List


def _table_overview(payload: Dict[str, Any]) -> List[Dict[str, int]]:
    """
    Returns a list of records: [{table, rows, columns}, ...]
    for use with st.table / st.dataframe.
    """
    overview: List[Dict[str, int]] = []

    for name, value in payload.items():
        # Normalize into list[dict] rows
        if isinstance(value, list):
            rows = [r for r in value if isinstance(r, dict)]
        elif isinstance(value, dict):
            if all(isinstance(v, dict) for v in value.values()):
                rows = list(value.values())
            else:
                # treat scalar-group as single row
                rows = [value]
        else:
            rows = []

        row_count = len(rows)

        # Column count from union of keys across rows
        cols = set()
        for r in rows:
            if isinstance(r, dict):
                cols.update(r.keys())
        col_count = len(cols)

        overview.append(
            {
                "table": name,
                "rows": row_count,
                "columns": col_count,
            }
        )

    return overview


def _render_answer_details(answer: ChatAnswer) -> None:
    with st.expander("Answer details", expanded=False):
        st.markdown("**Tables used**")
        if answer.tables_used:
            for name in answer.tables_used:
                st.write(f"- {name}")
        else:
            st.write("- None")
        st.markdown("**Guardrail messages**")
        if answer.guardrail_messages:
            for msg in answer.guardrail_messages:
                st.write(f"- {msg}")
        else:
            st.write("- None")
        st.markdown("**Table metadata**")
        for table, meta in answer.table_metadata.items():
            st.write(f"- {table}: rows={meta.row_count} truncated={meta.truncated}")


st.title("Perpetuity AI (Alpha)")
st.caption(
    "Ask questions from the extracted data from your Perplexity Model. "
    f"Session ID: {session_id}"
)

if "session_payload" not in st.session_state:
    st.session_state["session_payload"] = None
if "payload_label" not in st.session_state:
    st.session_state["payload_label"] = "No payload loaded"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []  # type: ignore[assignment]

# Depricated since pullling directly from the session-id now
# with st.sidebar:
#     st.header("1. Load JSON")
#     uploaded = st.file_uploader("Upload mapping JSON", type=["json"])
#     if uploaded:
#         try:
#             session_payload = json.load(uploaded)
#             # session_payload = {"mapping": {"mapped": payload}}
#             _reset_conversation(uploaded.name or "uploaded.json", session_payload)
#             st.success(f"Loaded {uploaded.name}")
#         except Exception as exc:  # noqa: BLE001
#             st.error(f"Failed to parse JSON: {exc}")

#     if st.button("Use sample JSON", use_container_width=True):
#         try:
#             payload = _load_sample_payload()
#             session_payload = {"mapping": {"mapped": payload}}
#             _reset_conversation("dev/extracted_sample.json", session_payload)
#             st.success("Loaded dev/extracted_sample.json")
#         except FileNotFoundError:
#             st.error("Sample file not found at dev/extracted_sample.json")

#     st.divider()
#     st.header("2. Prompt options")
#     top_k = st.slider("Max tables per answer", min_value=1, max_value=5, value=3, step=1)
#     metadata_only = st.toggle("Metadata-only mode", value=False, help="Only include schema descriptions.")

current_payload = st.session_state.get("session_payload")

def set_sidebar_width(width: int = 350):
    st.markdown(
        f"""
        <style>
            [data-testid="stSidebar"] {{
                min-width: {width}px;
                max-width: {width}px;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# Call it early in your app:
set_sidebar_width(450)  # adjust width here

with st.sidebar:
    st.header("Loaded Data")
    if not current_payload:
        st.info("No data received from the session.")
    else:
        canonical = current_payload.get("mapping", {}).get("mapped", {})
        if not canonical:
            st.warning("Payload is empty")
        else:
            overview = _table_overview(canonical)
            if overview:
                st.table(overview)
            with st.expander("Raw Data", expanded=False):
                st.json(canonical)

# payload_col, chat_col = st.columns([1, 2], gap="large")

# with payload_col:
#     st.subheader("Loaded JSON")
#     st.write(st.session_state.get("payload_label", "No payload"))
#     if not current_payload:
#         st.info("Upload a mapping JSON to begin.")
#     else:
#         canonical = current_payload.get("mapping", {}).get("mapped", {})
#         if not canonical:
#             st.warning("Payload is empty. Upload a JSON containing canonical tables.")
#         else:
#             for line in _humanize_table_overview(canonical):
#                 st.write(line)
#             with st.expander("Raw JSON", expanded=False):
#                 st.json(canonical)

# with chat_col:
st.subheader("Chat")

if not current_payload:
    st.info("Waiting for Session data...")
else:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    question = st.chat_input("Ask a question about the session data")

    if question:
        st.session_state.chat_history = []
        
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()

            try:
                with st.spinner("Thinking…"):
                    request = ChatQuestionRequest(
                        question=question,
                        top_k_tables=MAX_TABLES_TO_RETREIVE,
                        force_metadata_only=False,
                    )
                    answer = chatbot_service.answer_session_question(current_payload, request)

                # Replace spinner with final answer
                message_placeholder.markdown(answer.answer)
                _render_answer_details(answer)

                # Save only this turn (single-question mode)
                st.session_state.chat_history.append(
                    {"role": "user", "content": question}
                )
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": answer.answer,
                        "meta": answer.model_dump(),
                    }
                )

            except Exception as exc:  # noqa: BLE001
                error_msg = f":warning: Error: {exc}"
                message_placeholder.markdown(error_msg)
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": error_msg}
                )
                st.error(f"Chatbot error: {exc}")

    