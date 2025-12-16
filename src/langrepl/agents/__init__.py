from typing import TypeVar

from langrepl.agents.context import AgentContext
from langrepl.agents.state import AgentState

StateSchema = TypeVar("StateSchema", bound=AgentState)
StateSchemaType = type[StateSchema]

ContextSchema = TypeVar("ContextSchema", bound=AgentContext)
ContextSchemaType = type[ContextSchema]
