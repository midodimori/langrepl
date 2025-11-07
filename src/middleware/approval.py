"""Middleware for tool approval flow in agents."""

import re
from collections.abc import Callable
from pathlib import Path

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphInterrupt
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from src.agents import AgentState
from src.agents.context import AgentContext
from src.core.config import ApprovalMode, ToolApprovalConfig, ToolApprovalRule
from src.core.constants import CONFIG_APPROVAL_FILE_NAME
from src.core.logging import get_logger
from src.utils.render import format_tool_response, truncate_text

logger = get_logger(__name__)

ALLOW = "allow"
ALWAYS_ALLOW = "always allow"
DENY = "deny"
ALWAYS_DENY = "always deny"


class InterruptPayload(BaseModel):
    question: str
    options: list[str]


class ApprovalMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware to handle tool approval flow.

    Checks approval rules and mode, interrupts for user confirmation if needed, persists rules.
    """

    @staticmethod
    def _check_approval_rules(
        config: ToolApprovalConfig, tool_name: str, tool_args: dict
    ) -> bool | None:
        """Check if a tool call should be automatically approved or denied."""
        for rule in config.always_deny:
            if rule.matches_call(tool_name, tool_args):
                return False

        for rule in config.always_allow:
            if rule.matches_call(tool_name, tool_args):
                return True

        return None

    @staticmethod
    def _check_approval_mode_bypass(
        approval_mode: ApprovalMode,
        config: ToolApprovalConfig,
        tool_name: str,
        tool_args: dict,
    ) -> bool:
        """Check if approval should be bypassed based on current approval mode."""
        if approval_mode == ApprovalMode.SEMI_ACTIVE:
            return False
        elif approval_mode == ApprovalMode.ACTIVE:
            for rule in config.always_deny:
                if rule.matches_call(tool_name, tool_args):
                    return False
            return True
        elif approval_mode == ApprovalMode.AGGRESSIVE:
            return True
        return False

    @staticmethod
    def _save_approval_decision(
        config: ToolApprovalConfig,
        config_file: Path,
        tool_name: str,
        tool_args: dict | None,
        allow: bool,
    ):
        """Save an approval decision to the configuration."""
        rule = ToolApprovalRule(name=tool_name, args=tool_args)

        config.always_allow = [
            r
            for r in config.always_allow
            if not (r.name == tool_name and r.args == tool_args)
        ]
        config.always_deny = [
            r
            for r in config.always_deny
            if not (r.name == tool_name and r.args == tool_args)
        ]

        if allow:
            config.always_allow.append(rule)
            logger.info(f"Added '{tool_name}' to always allow list")
        else:
            config.always_deny.append(rule)
            logger.info(f"Added '{tool_name}' to always deny list")

        config.save_to_json_file(config_file)

    def _handle_approval(self, request: ToolCallRequest) -> str:
        """Handle approval logic and return user decision."""
        context = request.runtime.context
        if not isinstance(context, AgentContext):
            raise TypeError(
                f"Runtime context must be an {type(AgentContext)} instead of {type(context)}"
            )
        tool_name = request.tool_call["name"]
        tool_args = request.tool_call.get("args", {})

        tool_metadata = (request.tool.metadata or {}) if request.tool else {}
        tool_config = tool_metadata.get("approval_config", {})
        format_args_fn = tool_config.get("format_args_fn")
        render_args_fn = tool_config.get("render_args_fn")
        name_only = tool_config.get("name_only", False)
        always_approve = tool_config.get("always_approve", False)

        if always_approve:
            return ALLOW

        config_file = Path(context.working_dir) / CONFIG_APPROVAL_FILE_NAME
        approval_config = ToolApprovalConfig.from_json_file(config_file)

        formatted_args = format_args_fn(tool_args) if format_args_fn else tool_args

        approval_decision = self._check_approval_mode_bypass(
            context.approval_mode, approval_config, tool_name, formatted_args
        ) or self._check_approval_rules(approval_config, tool_name, formatted_args)

        if approval_decision:
            return ALLOW
        elif approval_decision is False:
            return DENY

        question = f"Allow running {tool_name} ?"
        if not name_only:
            if render_args_fn:
                rendered_config = {"configurable": {"working_dir": context.working_dir}}
                rendered = render_args_fn(tool_args, rendered_config)
                question += f" : {rendered}"
            else:
                question += f" : {tool_args}"

        interrupt_payload = InterruptPayload(
            question=question,
            options=[ALLOW, ALWAYS_ALLOW, DENY, ALWAYS_DENY],
        )
        user_response = interrupt(interrupt_payload)

        args_to_save = None if name_only else formatted_args

        if user_response == ALWAYS_ALLOW:
            self._save_approval_decision(
                approval_config, config_file, tool_name, args_to_save, True
            )
        elif user_response == ALWAYS_DENY:
            self._save_approval_decision(
                approval_config, config_file, tool_name, args_to_save, False
            )

        return user_response

    @staticmethod
    def _create_tool_message(
        tool_name: str,
        tool_call_id: str,
        content: str,
        is_error: bool = False,
        return_direct: bool = False,
    ) -> ToolMessage:
        """Create a ToolMessage with proper formatting."""
        short_content = truncate_text(content, 200) if not is_error else content
        return ToolMessage(
            name=tool_name,
            content=content,
            tool_call_id=tool_call_id,
            short_content=short_content,
            is_error=is_error,
            return_direct=return_direct,
        )

    async def awrap_tool_call(
        self, request: ToolCallRequest, handler: Callable
    ) -> ToolMessage | Command:
        """Async tool call interception for approval."""
        try:
            user_response = self._handle_approval(request)

            if user_response in (ALLOW, ALWAYS_ALLOW):
                result = await handler(request)
                if isinstance(result, Command):
                    return result

                content, short_content = format_tool_response(result)
                short_content = short_content or truncate_text(content, 200)
                tool_call_id = str(request.tool_call["id"])
                return ToolMessage(
                    name=request.tool_call["name"],
                    content=content,
                    tool_call_id=tool_call_id,
                    short_content=short_content,
                )
            else:
                tool_call_id = str(request.tool_call["id"])
                return self._create_tool_message(
                    request.tool_call["name"],
                    tool_call_id,
                    "Action denied by user.",
                    is_error=True,
                    return_direct=True,
                )
        except GraphInterrupt:
            raise
        except Exception as e:
            tool_call_id = str(request.tool_call["id"])
            return self._create_tool_message(
                request.tool_call["name"],
                tool_call_id,
                f"Failed to execute tool: {str(e)}",
                is_error=True,
            )


def create_field_extractor(field_patterns: dict[str, str]) -> Callable[[dict], dict]:
    """Create a generic pattern generator that extracts patterns from any fields.

    Args:
        field_patterns: Dict mapping field names to regex patterns with named groups

    Returns:
        A pattern generator function that extracts matched groups

    Example:
        # Extract any command base and ignore arguments
        extractor = create_field_extractor({
            "command": r"(?P<command>\\S+)", # First word only
            "path": r"(?P<path>[^/]+)$" # Filename only
        })

        # Usage with tool metadata
        tool.metadata["approval_config"] = {
            "format_args_fn": extractor
        }
    """

    def pattern_generator(args: dict) -> dict:
        result = args.copy()

        for field, pattern in field_patterns.items():
            if field in args:
                value = str(args[field])
                match = re.search(pattern, value)
                if match:
                    result.update(match.groupdict())

        return result

    return pattern_generator


def create_field_transformer(
    field_transforms: dict[str, Callable[[str], str]],
) -> Callable[[dict], dict]:
    """Create a generic pattern generator using transformation functions.

    Args:
        field_transforms: Dict mapping field names to transformation functions

    Returns:
        A pattern generator function that applies transformations

    Example:
        # Transform any fields generically
        transformer = create_field_transformer({
            "command": lambda x: x.split()[0],  # First word only
            "file_path": lambda x: os.path.basename(x),  # Filename only
            "url": lambda x: urlparse(x).netloc  # Domain only
        })

        # Usage with tool metadata
        tool.metadata["approval_config"] = {
            "format_args_fn": transformer
        }
    """

    def pattern_generator(args: dict) -> dict:
        result = args.copy()

        for field, transform_func in field_transforms.items():
            if field in args:
                try:
                    result[field] = transform_func(str(args[field]))
                except Exception:
                    # If transformation fails, keep original value
                    pass

        return result

    return pattern_generator
