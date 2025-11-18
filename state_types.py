# state_types.py

from typing import Literal, List, Dict, Any
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    """
    Extende MessagesState (que já tem o campo 'messages').

    - board: plano colaborativo da Semana da Computação
    - stage: fase do processo (coordenação)
    - user_actions: log de ações de cada usuário
    """
    board: str
    stage: Literal["brainstorm", "research", "draft", "review"]
    user_actions: List[Dict[str, Any]]  # logs: {user_id, action, message, timestamp}
