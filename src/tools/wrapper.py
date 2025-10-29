import re
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, InjectedToolCallId, ToolException, tool
from langgraph.errors import GraphInterrupt
from langgraph.types import interrupt
from pydantic import BaseModel

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


async def _handle_approval_logic(
    tool_name: str,
    kwargs: dict,
    config: RunnableConfig,
    name_only: bool,
    always_approve: bool,
    format_args_fn: Callable[[dict], dict] | None,
    render_args_fn: Callable[[dict, RunnableConfig], str] | None = None,
):
    """Common approval logic for both functions and BaseTool instances.

    Returns:
        One of the approval constants: ALLOW, ALWAYS_ALLOW, DENY, ALWAYS_DENY, or None for execute without asking
    """
    # Get approval mode and working directory from config
    configurable = config.get("configurable", {})
    approval_mode = ApprovalMode(configurable.get("approval_mode"))
    working_dir = configurable.get("working_dir")

    if not working_dir or not approval_mode:
        raise ToolException("Missing working_dir or approval_mode in RunnableConfig")

    # Load approval configuration
    config_file = Path(working_dir) / CONFIG_APPROVAL_FILE_NAME
    approval_config = ToolApprovalConfig.from_json_file(config_file)

    # Apply args formatting if provided
    if format_args_fn:
        kwargs = format_args_fn(kwargs)

    # Check if this tool call is pre-approved or denied
    approval_decision = (
        always_approve
        or check_approval_mode_bypass(approval_mode, approval_config, tool_name, kwargs)
        or check_approval(approval_config, tool_name, kwargs)
    )

    if approval_decision:
        return ALLOW
    elif approval_decision is False:
        return DENY

    # No rule found - ask user for approval
    question = f"Allow running {tool_name} ?"

    # Apply args rendering if provided
    if not name_only or render_args_fn:
        rendered = render_args_fn(kwargs, config) if render_args_fn else kwargs
        question += f" : {rendered}"

    interrupt_payload = InterruptPayload(
        question=question,
        options=[ALLOW, ALWAYS_ALLOW, DENY, ALWAYS_DENY],
    )
    user_response = interrupt(interrupt_payload)

    # Handle the response and save decisions if needed
    if user_response == ALWAYS_ALLOW:
        save_approval_decision(
            approval_config,
            config_file,
            tool_name,
            kwargs if not name_only else None,
            True,
        )
    elif user_response == ALWAYS_DENY:
        save_approval_decision(
            approval_config,
            config_file,
            tool_name,
            kwargs if not name_only else None,
            False,
        )

    return user_response


def approval_tool(
    name_only: bool = False,
    always_approve: bool = False,
    format_args_fn: Callable[[dict], dict] | None = None,
    render_args_fn: Callable[[dict, RunnableConfig], str] | None = None,
):
    """Decorator to handle tool with user approval

    Args:
        name_only: If True, only match on tool name, ignore arguments
        always_approve: If True, always approve without asking
        format_args_fn: Optional function that takes tool args and returns
                         a modified args dict for pattern matching
        render_args_fn: Optional function that takes tool args and config, returns
                         a formatted string for display purposes
    """

    def decorator(func_or_tool: Callable | BaseTool) -> Callable | BaseTool:
        # Handle BaseTool instances
        if isinstance(func_or_tool, BaseTool):
            original_tool = func_or_tool

            class ApprovedBaseTool(BaseTool):
                """Wrapper for BaseTool that adds approval functionality."""

                original_tool: BaseTool

                def __init__(self, **kwargs):
                    # Keep original args_schema - we'll handle injection manually
                    super().__init__(
                        name=original_tool.name,
                        description=original_tool.description,
                        args_schema=original_tool.args_schema,
                        handle_tool_error=True,
                        original_tool=original_tool,
                        **kwargs,
                    )

                def _parse_input(
                    self, tool_input: str | dict, tool_call_id: str | None
                ) -> str | dict[str, Any]:
                    """Override to inject tool_call_id for dict schemas"""
                    # Call parent's parsing first
                    parsed_input = super()._parse_input(tool_input, tool_call_id)

                    # If it's a dict, and we have a tool_call_id, inject it
                    if isinstance(parsed_input, dict) and tool_call_id is not None:
                        parsed_input = {**parsed_input, "tool_call_id": tool_call_id}

                    return parsed_input

                def _run(self, config: RunnableConfig, *args, **kwargs) -> Any:
                    """Sync version - delegate to original tool."""
                    return self.original_tool._run(config=config, *args, **kwargs)

                async def _arun(
                    self,
                    config: RunnableConfig,
                    *args,
                    **kwargs,
                ) -> Any:
                    """Async execution with approval logic - reuses the common approval logic."""
                    try:
                        user_response = await _handle_approval_logic(
                            self.name,
                            kwargs,
                            config,
                            name_only,
                            always_approve,
                            format_args_fn,
                            render_args_fn,
                        )

                        if user_response in (ALLOW, ALWAYS_ALLOW):
                            result = await self.original_tool._arun(
                                config=config, *args, **kwargs
                            )
                            content, short_content = format_tool_response(result)
                            short_content = short_content or truncate_text(content, 200)
                            return ToolMessage(
                                name=self.name,
                                content=content,
                                tool_call_id=kwargs.get("tool_call_id"),
                                short_content=short_content,
                            )
                        else:  # DENY or ALWAYS_DENY
                            # noinspection PyTypeChecker
                            return ToolMessage(
                                name=self.name,
                                content="Action denied by user.",
                                tool_call_id=kwargs.get("tool_call_id"),
                                return_direct=True,
                                is_error=True,
                            )

                    except GraphInterrupt:
                        # Let LangGraph interrupts bubble up - don't catch them
                        raise
                    except Exception as e:
                        raise ToolException(f"Failed to {self.name}: {str(e)}")

            return ApprovedBaseTool()

        # Handle functions
        else:
            func = func_or_tool

            @tool()
            @wraps(func)
            async def wrapper(
                config: RunnableConfig,
                tool_call_id: Annotated[str, InjectedToolCallId],
                *args,
                **kwargs,
            ) -> Any:
                try:
                    user_response = await _handle_approval_logic(
                        func.__name__,
                        kwargs,
                        config,
                        name_only,
                        always_approve,
                        format_args_fn,
                        render_args_fn,
                    )

                    if user_response in (ALLOW, ALWAYS_ALLOW):
                        result = await func(config, tool_call_id, *args, **kwargs)
                        content, short_content = format_tool_response(result)
                        short_content = short_content or truncate_text(content, 200)
                        return ToolMessage(
                            name=func.__name__,
                            content=content,
                            tool_call_id=tool_call_id,
                            short_content=short_content,
                        )
                    else:  # DENY or ALWAYS_DENY
                        # noinspection PyTypeChecker
                        return ToolMessage(
                            name=func.__name__,
                            content="Action denied by user.",
                            tool_call_id=tool_call_id,
                            return_direct=True,
                            is_error=True,
                        )
                except GraphInterrupt:
                    # Let LangGraph interrupts bubble up - don't catch them
                    raise
                except Exception as e:
                    raise ToolException(f"Failed to {func.__name__}: {str(e)}")

            return wrapper

    return decorator


def check_approval(
    config: ToolApprovalConfig, tool_name: str, tool_args: dict
) -> bool | None:
    """Check if a tool call should be automatically approved or denied"""
    # Check always_deny first (more restrictive)
    for rule in config.always_deny:
        if rule.matches_call(tool_name, tool_args):
            return False

    # Check always_allow
    for rule in config.always_allow:
        if rule.matches_call(tool_name, tool_args):
            return True

    return None


def check_approval_mode_bypass(
    approval_mode: ApprovalMode,
    config: ToolApprovalConfig,
    tool_name: str,
    tool_args: dict,
) -> bool:
    """Check if approval should be bypassed based on current approval mode."""
    if approval_mode == ApprovalMode.SEMI_ACTIVE:
        return False
    elif approval_mode == ApprovalMode.ACTIVE:
        # Bypass everything except always_deny rules
        for rule in config.always_deny:
            if rule.matches_call(tool_name, tool_args):
                return False
        return True
    elif approval_mode == ApprovalMode.AGGRESSIVE:
        # Bypass everything including always_deny rules
        return True
    return False


def save_approval_decision(
    config: ToolApprovalConfig,
    config_file: Path,
    tool_name: str,
    tool_args: dict | None,
    allow: bool,
):
    """Save an approval decision to the configuration"""
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

        # Usage with decorator
        @approval_tool(pattern_generator=extractor)
        def my_tool(command: str, path: str):
            pass
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
