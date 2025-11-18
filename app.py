# app.py

import os
import tempfile
from typing import List, Dict, Any

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

from graph import build_graph
from rag_tools import build_vectorstore_from_pdfs


st.set_page_config(page_title="Sistema Colaborativo - Semana da Computação", layout="wide")


def init_state():
    """
    Inicializa o estado compartilhado do LangGraph / sessão.
    """
    if "state" not in st.session_state:
        st.session_state.state = {
            "messages": [],
            "board": "",
            "stage": "brainstorm",
            "user_actions": [],
        }

    if "app_graph" not in st.session_state:
        st.session_state.app_graph = build_graph()


def save_uploaded_pdfs(uploaded_files) -> List[str]:
    """
    Salva os arquivos enviados para o /tmp e retorna a lista de paths.
    """
    paths = []
    for f in uploaded_files:
        suffix = ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(f.read())
            paths.append(tmp.name)
    return paths


def main():
    st.title("📚 Sistema Colaborativo com LangGraph, RAG e Streamlit")
    st.markdown(
        """
Este sistema simula um ambiente de **trabalho em grupo** para planejar a
**Semana da Computação**, usando:

- **Comunicação**: chat entre usuários e agente.
- **Colaboração**: construção coletiva do plano (board).
- **Coordenação**: controle de etapas e uso de RAG em PDFs.
"""
    )

    init_state()

    # === SIDEBAR: PDFs e estágio ===
    st.sidebar.header("Configurações")

    st.sidebar.subheader("📄 Upload de PDFs (até 5)")
    uploaded_files = st.sidebar.file_uploader(
        "Envie os PDFs de referência (por exemplo, regulamentos, editais, atas de reuniões)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        if len(uploaded_files) > 5:
            st.sidebar.error("Envie no máximo 5 arquivos PDF.")
        else:
            paths = save_uploaded_pdfs(uploaded_files)
            build_vectorstore_from_pdfs(paths)
            st.sidebar.success(f"{len(paths)} PDF(s) indexado(s) para RAG!")

    st.sidebar.subheader("🧭 Etapa (Coordenação)")
    stage = st.sidebar.selectbox(
        "Selecione a etapa do trabalho em grupo:",
        options=["brainstorm", "research", "draft", "review"],
        format_func=lambda s: {
            "brainstorm": "Brainstorm (ideias iniciais)",
            "research": "Pesquisa (usar PDFs)",
            "draft": "Rascunho do plano",
            "review": "Revisão final",
        }[s],
    )
    st.session_state.state["stage"] = stage

    # === LAYOUT PRINCIPAL ===
    col_chat, col_board = st.columns([2, 1])

    # ---------- COLUNA DO CHAT ----------
    with col_chat:
        st.subheader("💬 Chat colaborativo")

        user_name = st.text_input("Seu nome", value="Participante")

        st.markdown("### Histórico de conversa")
        for msg in st.session_state.state.get("messages", []):
            if isinstance(msg, HumanMessage):
                st.markdown(f"**{msg.additional_kwargs.get('user_id', 'Usuário')}**: {msg.content}")
            elif isinstance(msg, AIMessage):
                st.markdown(f"**Agente (LLM)**: {msg.content}")

        st.markdown("---")
        user_input = st.text_area("Digite sua mensagem para o grupo/agente:")

        if st.button("Enviar mensagem"):
            if not user_input.strip():
                st.warning("Digite uma mensagem antes de enviar.")
            else:
                msgs = list(st.session_state.state.get("messages", []))
                msgs.append(
                    HumanMessage(
                        content=user_input.strip(),
                        additional_kwargs={"user_id": user_name},
                    )
                )
                st.session_state.state["messages"] = msgs

                app = st.session_state.app_graph
                new_state = app.invoke(st.session_state.state)
                st.session_state.state = new_state

                st.rerun()


    # ---------- COLUNA DO BOARD ----------
    with col_board:
        st.subheader("📋 Plano colaborativo da Semana da Computação")

        board_text = st.session_state.state.get("board", "")
        if board_text:
            st.text_area(
                "Plano atual (gerado/atualizado coletivamente):",
                value=board_text,
                height=450,
            )
        else:
            st.info("O plano ainda não foi iniciado. Comece conversando no chat!")

        st.markdown("---")
        st.subheader("🧾 Log de ações (Coordenação)")
        actions: List[Dict[str, Any]] = st.session_state.state.get("user_actions", [])
        if not actions:
            st.write("Nenhuma ação registrada ainda.")
        else:
            for a in reversed(actions[-15:]):
                st.markdown(
                    f"- **{a['timestamp']}** – `{a['user_id']}` na etapa `{a['stage']}`: _{a['message']}_"
                )
    


if __name__ == "__main__":
    main()
