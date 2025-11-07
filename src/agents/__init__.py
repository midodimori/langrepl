from typing import TypeVar

from src.agents.context import AgentContext
from src.agents.state import AgentState

StateSchema = TypeVar("StateSchema", bound=AgentState)
StateSchemaType = type[StateSchema]

ContextSchema = TypeVar("ContextSchema", bound=AgentContext)
ContextSchemaType = type[ContextSchema]
