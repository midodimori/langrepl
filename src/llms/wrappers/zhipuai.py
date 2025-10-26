"""Custom ChatZhipuAI wrapper with reasoning content support.

This wrapper extends langchain_community's ChatZhipuAI to properly extract
reasoning_content from non-streaming responses when thinking mode is enabled.

When langchain_community adds native support, this wrapper can be removed and
the import can be changed directly to langchain_community.chat_models.
"""

from typing import Any

from langchain_community.chat_models import ChatZhipuAI as _BaseChatZhipuAI
from langchain_community.chat_models.zhipuai import _convert_dict_to_message
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ChatZhipuAI(_BaseChatZhipuAI):
    """ChatZhipuAI with reasoning content extraction support."""

    def __init__(self, **kwargs):
        thinking = kwargs.pop("thinking", None)
        super().__init__(**kwargs)
        self._thinking_config = thinking

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        stream: bool | None = None,
        **kwargs: Any,
    ):
        if self._thinking_config and "thinking" not in kwargs:
            kwargs["thinking"] = self._thinking_config
        return await super()._agenerate(messages, stop, run_manager, stream, **kwargs)

    def _create_chat_result(self, response):
        if not isinstance(response, dict):
            response = response.model_dump()

        generations = []
        for choice in response["choices"]:
            msg_dict = choice["message"]
            message = _convert_dict_to_message(msg_dict)

            # Extract reasoning_content and format as thinking
            if isinstance(message, AIMessage) and msg_dict.get("reasoning_content"):
                message.additional_kwargs = message.additional_kwargs or {}
                message.additional_kwargs["thinking"] = {
                    "text": msg_dict["reasoning_content"]
                }

            generations.append(
                ChatGeneration(
                    message=message,
                    generation_info={"finish_reason": choice.get("finish_reason")},
                )
            )

        return ChatResult(
            generations=generations,
            llm_output={
                "token_usage": response.get("usage", {}),
                "model_name": self.model_name,
            },
        )
