# agent_context.py
from contextvars import ContextVar
from typing import Optional

# Define a context variable that will hold the session_id for the current task context.
current_session_id_var: ContextVar[Optional[str]] = ContextVar("current_session_id_var", default=None)
