"""Moonshot ChatOpenAI wrapper with reasoning content support."""

from __future__ import annotations

import openai
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI as _BaseChatOpenAI


class ChatMoonshotAI(_BaseChatOpenAI):
    """ChatOpenAI-compatible Moonshot client that preserves thinking text."""

    @staticmethod
    def _response_to_dict(response: dict | openai.BaseModel) -> dict:
        if isinstance(response, dict):
            return response
        return response.model_dump(
            exclude={"choices": {"__all__": {"message": {"parsed"}}}}
        )

    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> ChatResult:
        response_dict = self._response_to_dict(response)
        result = super()._create_chat_result(response, generation_info)

        for generation, choice in zip(
            result.generations, response_dict.get("choices", []), strict=False
        ):
            message = generation.message
            msg_dict = choice.get("message", {})
            reasoning_text = msg_dict.get("reasoning_content")
            if isinstance(message, AIMessage) and reasoning_text:
                message.additional_kwargs = message.additional_kwargs or {}
                message.additional_kwargs["thinking"] = {
                    "text": reasoning_text.lstrip("\n")
                }

        return result

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if generation_chunk is None:
            return None

        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        if not choices:
            return generation_chunk

        delta = choices[0].get("delta") or {}
        reasoning_text = delta.get("reasoning_content")
        message = generation_chunk.message
        if isinstance(message, AIMessageChunk) and reasoning_text:
            message.additional_kwargs = message.additional_kwargs or {}
            message.additional_kwargs["thinking"] = {"text": reasoning_text}

        return generation_chunk
