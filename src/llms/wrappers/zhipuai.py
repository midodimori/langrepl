"""Custom ChatZhipuAI wrapper with reasoning content support.

This wrapper extends langchain_community's ChatZhipuAI to properly extract
reasoning_content from both streaming and non-streaming responses when thinking
mode is enabled.

When langchain_community adds native support, this wrapper can be removed and
the import can be changed directly to langchain_community.chat_models.
"""

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_community.chat_models import ChatZhipuAI as _BaseChatZhipuAI
from langchain_community.chat_models.zhipuai import (
    _convert_delta_to_message_chunk,
    _convert_dict_to_message,
    _get_jwt_token,
    _truncate_params,
    aconnect_sse,
    connect_sse,
)
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class ChatZhipuAI(_BaseChatZhipuAI):
    """ChatZhipuAI with reasoning content extraction support."""

    def __init__(self, **kwargs):
        thinking = kwargs.pop("thinking", None)
        super().__init__(**kwargs)
        self._thinking_config = thinking

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        stream: bool | None = None,
        **kwargs: Any,
    ):
        if self._thinking_config and "thinking" not in kwargs:
            kwargs["thinking"] = self._thinking_config
        return super()._generate(messages, stop, run_manager, stream, **kwargs)

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

            # Strip leading newline from content
            if isinstance(message, AIMessage) and isinstance(message.content, str):
                message.content = message.content.lstrip("\n")

            # Extract reasoning_content and format as thinking
            if isinstance(message, AIMessage) and msg_dict.get("reasoning_content"):
                message.additional_kwargs = message.additional_kwargs or {}
                message.additional_kwargs["thinking"] = {
                    "text": msg_dict["reasoning_content"].lstrip("\n")
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

    def _prepare_streaming_request(
        self, messages: list[BaseMessage], stop: list[str] | None, kwargs: dict
    ) -> tuple[dict, dict, str]:
        if self.zhipuai_api_key is None:
            raise ValueError("Did not find zhipuai_api_key.")
        if self.zhipuai_api_base is None:
            raise ValueError("Did not find zhipu_api_base.")

        message_dicts, params = self._create_message_dicts(messages, stop)
        payload = {**params, **kwargs, "messages": message_dicts, "stream": True}
        _truncate_params(payload)
        headers = {
            "Authorization": _get_jwt_token(self.zhipuai_api_key),
            "Accept": "application/json",
        }
        return payload, headers, self.zhipuai_api_base

    def _process_sse_chunk(
        self,
        chunk_data: dict,
        default_chunk_class: type,
        first_content: bool,
    ) -> tuple[ChatGenerationChunk | None, bool, bool]:
        if len(chunk_data["choices"]) == 0:
            return None, False, first_content

        choice = chunk_data["choices"][0]
        delta = choice["delta"]
        usage = chunk_data.get("usage", None)
        model_name = chunk_data.get("model", "")

        chunk = _convert_delta_to_message_chunk(delta, default_chunk_class)

        updated_first_content = first_content
        if isinstance(chunk.content, str):
            if chunk.content == "\n":
                chunk.content = ""
            elif first_content and chunk.content:
                chunk.content = chunk.content.lstrip("\n")
                updated_first_content = False

        reasoning_text = delta.get("reasoning_content", "")
        if isinstance(chunk, AIMessageChunk) and reasoning_text.strip():
            chunk.additional_kwargs = chunk.additional_kwargs or {}
            if "thinking" not in chunk.additional_kwargs:
                chunk.additional_kwargs["thinking"] = {"text": ""}
            if not chunk.additional_kwargs["thinking"]["text"]:
                reasoning_text = reasoning_text.lstrip("\n")
            chunk.additional_kwargs["thinking"]["text"] += reasoning_text

        finish_reason = choice.get("finish_reason", None)
        generation_info = (
            {
                "finish_reason": finish_reason,
                "token_usage": usage,
                "model_name": model_name,
            }
            if finish_reason is not None
            else None
        )

        generation_chunk = ChatGenerationChunk(
            message=chunk, generation_info=generation_info
        )

        should_break = finish_reason is not None
        return generation_chunk, should_break, updated_first_content

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        if self._thinking_config and "thinking" not in kwargs:
            kwargs["thinking"] = self._thinking_config

        payload, headers, api_base = self._prepare_streaming_request(
            messages, stop, kwargs
        )

        default_chunk_class = AIMessageChunk
        import httpx

        first_content = True
        with httpx.Client(headers=headers, timeout=60) as client:
            with connect_sse(client, "POST", api_base, json=payload) as event_source:
                for sse in event_source.iter_sse():
                    if not sse.data:
                        continue
                    try:
                        chunk_data = json.loads(sse.data)
                    except json.JSONDecodeError:
                        continue
                    generation_chunk, should_break, first_content = (
                        self._process_sse_chunk(
                            chunk_data, default_chunk_class, first_content
                        )
                    )

                    if generation_chunk is None:
                        continue

                    if run_manager:
                        run_manager.on_llm_new_token(
                            generation_chunk.text, chunk=generation_chunk
                        )
                    yield generation_chunk

                    if should_break:
                        break

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if self._thinking_config and "thinking" not in kwargs:
            kwargs["thinking"] = self._thinking_config

        payload, headers, api_base = self._prepare_streaming_request(
            messages, stop, kwargs
        )

        default_chunk_class = AIMessageChunk
        import httpx

        first_content = True
        async with httpx.AsyncClient(headers=headers, timeout=60) as client:
            async with aconnect_sse(
                client, "POST", api_base, json=payload
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    if not sse.data:
                        continue
                    try:
                        chunk_data = json.loads(sse.data)
                    except json.JSONDecodeError:
                        continue
                    generation_chunk, should_break, first_content = (
                        self._process_sse_chunk(
                            chunk_data, default_chunk_class, first_content
                        )
                    )

                    if generation_chunk is None:
                        continue

                    if run_manager:
                        await run_manager.on_llm_new_token(
                            generation_chunk.text, chunk=generation_chunk
                        )
                    yield generation_chunk

                    if should_break:
                        break
