# graph.py – LangGraph + Gemini (via langchain-google-genai) + RAG local

from typing import List
import os
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from state_types import AgentState
from rag_tools import pdf_rag_search


# ---------- Configuração do Gemini via LangChain ----------

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "A variável de ambiente GOOGLE_API_KEY não está definida. "
        "Defina sua chave do Gemini antes de rodar o app."
    )

# Use um modelo suportado pela sua conta; 1.5-flash é leve e barato
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.4,
)


# ---------- Nós do grafo ----------

def log_action(state: AgentState) -> AgentState:
    """
    Nó de Comunicação: registra a última mensagem do usuário no log de ações.
    """
    state = dict(state)

    actions = list(state.get("user_actions", []))

    last_human = None
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            last_human = m
            break

    if last_human:
        user_id = last_human.additional_kwargs.get("user_id", "anônimo")
        actions.append(
            {
                "user_id": user_id,
                "action": "message",
                "message": last_human.content,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "stage": state.get("stage", "brainstorm"),
            }
        )

    state["user_actions"] = actions
    return state


def coordination_router_pass(state: AgentState) -> AgentState:
    """
    Nó de Coordenação 'vazio' – só passa o estado adiante.
    O roteamento de fato é feito em route_by_stage.
    """
    return state


def route_by_stage(state: AgentState) -> str:
    """
    Decide o próximo nó com base na fase (stage) do processo colaborativo.
    """
    stage = state.get("stage", "brainstorm")

    if stage == "research":
        return "rag_retrieval"
    elif stage == "review":
        return "review_decision"
    else:
        # brainstorm e draft caem aqui
        return "synthesis"


def rag_retrieval(state: AgentState) -> AgentState:
    """
    Nó de ferramenta (RAG): busca trechos relevantes nos PDFs
    com base na última pergunta do usuário.
    """
    state = dict(state)

    last_human = None
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            last_human = m
            break

    if not last_human:
        state["retrieved_context"] = "Nenhuma pergunta do usuário encontrada."
        return state

    query = last_human.content
    context = pdf_rag_search(query, k=4)
    state["retrieved_context"] = context
    return state


def synthesis(state: AgentState) -> AgentState:
    """
    Nó de Colaboração: usa o Gemini para construir respostas e
    atualizar o 'board' colaborativo, usando (quando existir)
    o contexto recuperado via RAG.
    """
    state = dict(state)

    messages: List[HumanMessage | AIMessage] = list(state.get("messages", []))
    board = state.get("board", "")
    stage = state.get("stage", "brainstorm")
    context = state.get("retrieved_context", "")

    system_prompt = f"""
Você é um assistente colaborativo ajudando um grupo a planejar a Semana da Computação.

- O campo 'board' é o plano colaborativo atual.
- A etapa atual (stage) é: {stage}.
- Use a conversa dos usuários e, se houver, o contexto dos PDFs para propor atualizações.

Objetivos:
- Comunicação: responder de forma clara às mensagens.
- Colaboração: ajudar a construir coletivamente o plano de atividades.
- Coordenação: sugerir próximos passos para o grupo (quem faz o quê, prazos, tarefas).

Plano atual (board):
{board or 'Nenhum plano definido ainda.'}
"""

    lc_messages: List[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=system_prompt)
    ] + messages

    if context:
        lc_messages.append(
            HumanMessage(
                content=(
                    "Use também estes trechos dos PDFs como referência:\n\n"
                    f"{context}"
                )
            )
        )

    ai_answer = llm.invoke(lc_messages)

    messages.append(ai_answer)
    state["messages"] = messages
    state["board"] = ai_answer.content

    return state


def review_decision(state: AgentState) -> AgentState:
    """
    Nó de revisão: o Gemini faz uma checagem do plano atual
    e sugere ajustes finais.
    """
    state = dict(state)

    board = state.get("board", "")
    messages: List[HumanMessage | AIMessage] = list(state.get("messages", []))

    review_prompt = f"""
Você está na fase de REVISÃO do plano colaborativo da Semana da Computação.

Plano atual:
{board or 'Ainda não há um plano claro.'}

Tarefas:
- Apontar possíveis problemas ou pontos de melhoria.
- Sugerir ajustes finais concretos.
- Verificar se as responsabilidades e etapas estão bem coordenadas.

Responda em português, em tom construtivo.
"""

    lc_messages: List[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=review_prompt)
    ] + messages

    ai_review = llm.invoke(lc_messages)

    messages.append(ai_review)
    state["messages"] = messages
    state["board"] = ai_review.content

    return state


def build_graph():
    """
    Monta o grafo do LangGraph com nós de:
    - Comunicação (log_action)
    - Coordenação (coordination_router + roteamento por estágio)
    - Colaboração (synthesis, review_decision)
    - Ferramenta RAG (rag_retrieval)

    Cada execução termina em END (sem loop infinito).
    """
    graph = StateGraph(AgentState)

    graph.add_node("log_action", log_action)
    graph.add_node("coordination_router", coordination_router_pass)
    graph.add_node("rag_retrieval", rag_retrieval)
    graph.add_node("synthesis", synthesis)
    graph.add_node("review_decision", review_decision)

    # Fluxo básico
    graph.add_edge(START, "log_action")
    graph.add_edge("log_action", "coordination_router")

    # Coordenação decide o próximo nó
    graph.add_conditional_edges(
        "coordination_router",
        route_by_stage,
        {
            "rag_retrieval": "rag_retrieval",
            "synthesis": "synthesis",
            "review_decision": "review_decision",
        },
    )

    # Depois de RAG, sempre vai para síntese
    graph.add_edge("rag_retrieval", "synthesis")

    # Uma rodada de síntese termina no END
    graph.add_edge("synthesis", END)

    # Revisão também termina a rodada
    graph.add_edge("review_decision", END)

    app = graph.compile()
    return app
