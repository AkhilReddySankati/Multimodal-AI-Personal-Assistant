"""
Streamlit front end for the multimodal assistant.

Changes in this revision
------------------------
1. The keyword short-circuit is GONE. Previously any question containing the
   word "dashboard" bypassed the agent entirely and returned a hardcoded
   string, so "explain the dashboard" and "write a report on it" produced
   the same canned reply as "create a dashboard". Every question now goes
   to ask_agent, and the agent decides whether to build a dashboard.
2. Dashboards are rendered as artifacts (type "dashboard"), stored in the
   message history, and replayed from memory instead of being rebuilt from
   disk on every rerun.
3. The last dashboard summary is fed back into the next question, so the
   model can answer follow-ups without rebuilding anything.
4. use_container_width is deprecated in current Streamlit; a helper uses
   width="stretch" and falls back automatically on older versions.
"""

import hashlib
import io
import os
from pathlib import Path
import tempfile

import speech_recognition as sr
import streamlit as st
import streamlit.components.v1 as components

from agent import ask_agent
from face_agent import authenticate_user
from tools import index_uploaded_documents


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Multimodal AI Personal Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_FILE_TYPES = [
    "pdf", "txt", "md", "docx",
    "csv", "xlsx", "xls",
    "sql", "py",
]

RAG_FILE_TYPES = {"pdf", "txt", "md", "docx"}

FILE_ROLE = {
    ".pdf": "RAG searchable",
    ".txt": "RAG searchable",
    ".md": "RAG searchable",
    ".docx": "RAG searchable",
    ".csv": "Dataset analysis + dashboard",
    ".xlsx": "Dataset analysis + dashboard",
    ".xls": "Dataset analysis + dashboard",
    ".sql": "SQL analysis + ER diagram",
    ".py": "Python inspection",
}


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "authenticated": False,
    "authenticated_user": None,
    "messages": [],
    "uploaded_files": [],
    "processed_audio_hash": None,
    "indexed_files": set(),
    "last_dashboard_summary": None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        if isinstance(value, set):
            st.session_state[key] = set()
        elif isinstance(value, list):
            st.session_state[key] = []
        else:
            st.session_state[key] = value


def reset_state():
    for key, value in DEFAULT_STATE.items():
        if isinstance(value, set):
            st.session_state[key] = set()
        elif isinstance(value, list):
            st.session_state[key] = []
        else:
            st.session_state[key] = value


# ============================================================
# STYLES AND HEADER
# ============================================================

st.markdown(
    """
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; margin-bottom: .2rem; }
    .subtitle { color: #777; margin-bottom: 1.5rem; }
    .auth-box { padding: 20px; border-radius: 12px; border: 1px solid #ddd; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">🤖 Multimodal AI Personal Assistant</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Face Authentication • File Upload • Text • '
    'Voice • RAG • Agentic AI • Analytics Dashboard</div>',
    unsafe_allow_html=True,
)


# ============================================================
# WIDTH HELPERS
# use_container_width is deprecated in recent Streamlit but
# width="stretch" does not exist in older versions, so try both.
# ============================================================

def show_chart(figure, key):
    try:
        st.plotly_chart(figure, width="stretch", key=key)
    except TypeError:
        st.plotly_chart(figure, use_container_width=True, key=key)


def show_dataframe(dataframe):
    try:
        st.dataframe(dataframe, width="stretch")
    except TypeError:
        st.dataframe(dataframe, use_container_width=True)


def wide_button(label, key=None):
    try:
        return st.button(label, width="stretch", key=key)
    except TypeError:
        return st.button(label, use_container_width=True, key=key)


# ============================================================
# RENDERERS
# ============================================================

def render_mermaid(mermaid_source, height=520):
    """Render a Mermaid diagram, with the source available below it."""

    if not mermaid_source:
        return

    escaped = (
        str(mermaid_source)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    components.html(
        f"""
        <div class="mermaid">{escaped}</div>
        <script type="module">
            import mermaid from
                "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
            mermaid.initialize({{ startOnLoad: true }});
        </script>
        """,
        height=height,
        scrolling=True,
    )

    with st.expander("Mermaid source"):
        st.code(mermaid_source, language="text")


def render_dashboard(dashboard, key_prefix="dashboard"):
    """Render KPI cards, charts, insights and the underlying data."""

    if not dashboard:
        st.warning("No dashboard data available.")
        return

    st.markdown("## 📊 Automated Analytics Dashboard")

    # KPI cards
    kpis = dashboard.get("kpis") or []

    if kpis:
        columns = st.columns(len(kpis))

        for index, item in enumerate(kpis):
            try:
                title, value, description = item
            except Exception:
                continue

            with columns[index]:
                st.metric(title, value)
                st.caption(description)

    # Charts, two per row
    figures = dashboard.get("figures") or []

    for index in range(0, len(figures), 2):

        row = st.columns(2)

        with row[0]:
            show_chart(figures[index], f"{key_prefix}_chart_{index}")

        if index + 1 < len(figures):
            with row[1]:
                show_chart(
                    figures[index + 1],
                    f"{key_prefix}_chart_{index + 1}",
                )

    # Insights
    insights = dashboard.get("insights") or []

    if insights:
        st.markdown("### 💡 Key Insights")
        for insight in insights:
            st.markdown(f"- {insight}")

    # Underlying data
    dataframe = dashboard.get("dataframe")

    if dataframe is not None:
        with st.expander("🔎 View analyzed data"):
            show_dataframe(dataframe)


def render_artifacts(artifacts, key_prefix):
    """Render everything the agent produced: dashboards, charts, diagrams."""

    if not artifacts:
        return

    for index, artifact in enumerate(artifacts):

        if not isinstance(artifact, dict):
            continue

        kind = artifact.get("type")

        if kind == "dashboard" and artifact.get("dashboard"):
            render_dashboard(
                artifact["dashboard"],
                key_prefix=f"{key_prefix}_dash_{index}",
            )

        elif kind == "plotly" and artifact.get("figure") is not None:
            show_chart(artifact["figure"], f"{key_prefix}_plot_{index}")

        elif kind == "mermaid" and artifact.get("mermaid"):
            render_mermaid(artifact["mermaid"])


# ============================================================
# FACE AUTHENTICATION
# ============================================================

if not st.session_state.authenticated:

    st.warning(
        "🔐 Please authenticate using your face before accessing "
        "the AI assistant."
    )

    st.markdown('<div class="auth-box">', unsafe_allow_html=True)
    st.subheader("📷 Face Authentication")
    st.write("Look at the camera and capture your image.")

    camera_image = st.camera_input("Camera", key="authentication_camera")

    st.markdown("</div>", unsafe_allow_html=True)

    if camera_image is not None:

        with st.spinner("🔍 Recognizing face..."):

            temp_image_path = None

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".jpg"
                ) as tmp:
                    tmp.write(camera_image.getvalue())
                    temp_image_path = tmp.name

                user_name = authenticate_user(temp_image_path)

                if user_name:
                    st.session_state.authenticated = True
                    st.session_state.authenticated_user = user_name
                    st.success(
                        f"✅ Authentication successful. Welcome {user_name}!"
                    )
                    st.rerun()
                else:
                    st.error("❌ Unknown person detected.")
                    st.info(
                        "🔒 Assistant access is blocked for unknown users."
                    )

            except Exception as error:
                st.error(f"❌ Face authentication error: {error}")

            finally:
                if temp_image_path and os.path.exists(temp_image_path):
                    try:
                        os.remove(temp_image_path)
                    except OSError:
                        pass

    st.stop()


st.success(
    f"🔓 Authenticated user: **{st.session_state.authenticated_user}**"
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Assistant")
    st.write(f"👤 **User:** {st.session_state.authenticated_user}")
    st.divider()

    st.subheader("📁 Upload Files")

    uploaded_files = st.file_uploader(
        "Choose one or more files",
        type=SUPPORTED_FILE_TYPES,
        accept_multiple_files=True,
        help="Supported: PDF, TXT, MD, DOCX, CSV, XLSX, XLS, SQL and PY",
    )

    # --------------------------------------------------------
    # Save uploads. Assigned every run, so clearing the uploader
    # also clears the agent's file list.
    # --------------------------------------------------------

    current_file_paths = []

    for uploaded_file in uploaded_files or []:

        save_path = UPLOAD_DIR / Path(uploaded_file.name).name

        try:
            with open(save_path, "wb") as file:
                file.write(uploaded_file.getvalue())

            current_file_paths.append(str(save_path))

        except Exception as error:
            st.error(f"❌ Could not save {uploaded_file.name}: {error}")

    st.session_state.uploaded_files = current_file_paths

    # --------------------------------------------------------
    # RAG indexing
    # --------------------------------------------------------

    rag_files = [
        path
        for path in current_file_paths
        if Path(path).suffix.lower().lstrip(".") in RAG_FILE_TYPES
        and path not in st.session_state.indexed_files
    ]

    if rag_files:

        with st.spinner("📚 Indexing documents for RAG..."):

            try:
                indexing_result = index_uploaded_documents(rag_files)
                st.session_state.indexed_files.update(rag_files)

                st.success("✅ Documents indexed.")

                with st.expander("Indexing details"):
                    st.text(indexing_result)

            except Exception as error:
                st.error(f"❌ RAG indexing error: {error}")

    # --------------------------------------------------------
    # Current files
    # --------------------------------------------------------

    st.divider()
    st.subheader("📄 Current Files")

    if current_file_paths:

        for file_path in current_file_paths:
            path = Path(file_path)
            st.write(f"📄 {path.name}")
            st.caption(FILE_ROLE.get(path.suffix.lower(), "Uploaded"))

        st.caption(f"📦 {len(current_file_paths)} file(s) loaded")

    else:
        st.info("No files uploaded.")

    st.divider()

    if wide_button("🗑️ Clear Conversation", key="clear_chat"):
        st.session_state.messages = []
        st.session_state.last_dashboard_summary = None
        st.rerun()

    if wide_button("🔒 Logout", key="logout"):
        reset_state()
        st.rerun()


# ============================================================
# LAYOUT
# ============================================================

chat_col, info_col = st.columns([2.2, 1])


with info_col:

    st.subheader("📂 File Information")

    if st.session_state.uploaded_files:

        for file_path in st.session_state.uploaded_files:

            path = Path(file_path)

            st.markdown(f"**{path.name}**")

            try:
                st.caption(f"Size: {path.stat().st_size / 1024:.2f} KB")
            except OSError:
                pass

            st.caption(FILE_ROLE.get(path.suffix.lower(), "Uploaded"))
            st.divider()

    else:
        st.info("Upload a file from the sidebar.")
        st.caption("You can still ask general questions without a file.")


with chat_col:

    st.subheader("💬 AI Assistant")

    # --------------------------------------------------------
    # Chat history. Artifacts are replayed from memory, so no
    # dashboard is ever rebuilt on a rerun.
    # --------------------------------------------------------

    for message_index, message in enumerate(st.session_state.messages):

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            render_artifacts(
                message.get("artifacts", []),
                key_prefix=f"history_{message_index}",
            )

    st.markdown("---")
    st.write("### 🎙️ Ask Your Assistant")
    st.caption("Type your question or use the microphone.")

    text_question = st.text_input(
        "Type your question",
        placeholder="Ask anything, or ask about your uploaded files...",
        key="text_question",
    )

    audio_value = st.audio_input(
        "🎤 Record your question",
        key="voice_input",
    )

    send_button = wide_button("➤ Send", key="send")


# ============================================================
# COLLECT THE QUESTION
# ============================================================

question = None

if send_button and text_question.strip():
    question = text_question.strip()

if question is None and audio_value is not None:

    audio_bytes = audio_value.getvalue()
    audio_hash = hashlib.md5(audio_bytes).hexdigest()

    if audio_hash != st.session_state.processed_audio_hash:

        st.session_state.processed_audio_hash = audio_hash

        try:
            recognizer = sr.Recognizer()

            with st.spinner("🎤 Converting speech to text..."):

                with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                    audio_data = recognizer.record(source)

                question = recognizer.recognize_google(audio_data)

            st.success(f"👤 You said: **{question}**")

        except sr.UnknownValueError:
            st.session_state.processed_audio_hash = None
            st.error(
                "❌ I could not understand the audio. "
                "Please speak clearly and try again."
            )

        except sr.RequestError:
            st.session_state.processed_audio_hash = None
            st.error("❌ Speech recognition service is unavailable.")

        except Exception as error:
            st.session_state.processed_audio_hash = None
            st.error(f"❌ Voice processing error: {error}")


# ============================================================
# ASK THE AGENT
# ============================================================

if question:

    st.session_state.messages.append(
        {"role": "user", "content": question, "artifacts": []}
    )

    with chat_col:

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):

            artifacts = []

            # ------------------------------------------------
            # Give the model the previous dashboard so follow-up
            # questions ("explain it", "write a report on it")
            # work without rebuilding anything.
            # ------------------------------------------------

            agent_question = question

            previous = st.session_state.last_dashboard_summary

            if previous:
                agent_question = (
                    f"{question}\n\n"
                    f"[Context: a dashboard is already on screen. "
                    f"Use this summary to answer questions about it and do "
                    f"not rebuild it unless a NEW dashboard is requested.]\n"
                    f"{previous}"
                )

            with st.spinner("🤖 Thinking..."):

                try:
                    answer = ask_agent(
                        agent_question,
                        uploaded_files=st.session_state.uploaded_files,
                        artifacts=artifacts,
                    )

                except Exception as error:
                    answer = f"❌ Agent error: {error}"

            answer = str(answer) if answer else (
                "I could not generate an answer."
            )

            st.markdown(answer)

            render_artifacts(artifacts, key_prefix="live")

            # ------------------------------------------------
            # Remember the newest dashboard summary
            # ------------------------------------------------

            for artifact in artifacts:
                if artifact.get("type") == "dashboard":
                    st.session_state.last_dashboard_summary = artifact.get(
                        "summary"
                    )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "artifacts": artifacts,
        }
    )

    st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "🤖 Multimodal AI Assistant | Face Authentication + Text + Voice + "
    "RAG + Agentic AI + Automated Dashboards"
)