from typing import TypeVar

from src.state.base import BaseState

StateSchema = TypeVar("StateSchema", bound=BaseState)
StateSchemaType = type[StateSchema]
