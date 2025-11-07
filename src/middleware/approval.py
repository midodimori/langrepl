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
        """
        Determine if a tool call matches configured approval rules and return the resulting decision.
        
        Returns:
            `True` if an allow rule matches, `False` if a deny rule matches, `None` if no rule applies.
        """
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
        """
        Determine whether the approval prompt can be bypassed for a tool call based on the current approval mode and configured deny rules.
        
        Parameters:
            approval_mode (ApprovalMode): Current approval mode controlling bypass behavior.
            config (ToolApprovalConfig): Approval configuration containing `always_deny` rules to evaluate in ACTIVE mode.
            tool_name (str): Name of the tool being called.
            tool_args (dict): Arguments passed to the tool, used to match against deny rules.
        
        Returns:
            bool: `True` if the approval flow may be bypassed (no user interrupt required), `False` otherwise.
        
        Behavior:
            - SEMI_ACTIVE: never bypass (returns `False`).
            - ACTIVE: bypass unless any rule in `config.always_deny` matches the tool call (returns `False` if a match is found, `True` otherwise).
            - AGGRESSIVE: always bypass (returns `True`).
            - Any other mode: do not bypass (returns `False`).
        """
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
        """
        Persist an approval decision by updating the provided approval config and writing it to disk.
        
        Removes any existing rule entries for the same tool name and exact args, then appends the decision
        to either the `always_allow` or `always_deny` list and saves the updated config to `config_file`.
        
        Parameters:
            config (ToolApprovalConfig): Mutable approval configuration to update.
            config_file (Path): Filesystem path where the updated config will be saved as JSON.
            tool_name (str): Name of the tool the decision applies to.
            tool_args (dict | None): Exact tool arguments to match/store; use `None` to represent name-only rules.
            allow (bool): If `True`, add an allow rule; if `False`, add a deny rule.
        """
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
        """
        Determine whether a tool call should be allowed, denied, or requires prompting the user.
        
        Evaluates per-tool metadata and stored approval rules, applies approval-mode bypass logic, and—if no automatic decision is reached—constructs an interrupt question to obtain the user's choice. Persists decisions when the user selects always-allow or always-deny.
        
        Raises:
            TypeError: If the runtime context is not an AgentContext.
        
        Returns:
            str: One of `ALLOW`, `DENY`, `ALWAYS_ALLOW`, or `ALWAYS_DENY` indicating the approval outcome.
        """
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
        """
        Create a ToolMessage representing a tool invocation result.
        
        Parameters:
            is_error (bool): If True, preserve the full `content` in `short_content`; otherwise `short_content` is the `content` truncated to 200 characters.
            return_direct (bool): When True, mark the message to be returned directly to the caller.
        
        Returns:
            ToolMessage: A message containing `name`, `content`, `tool_call_id`, `short_content`, `is_error`, and `return_direct`.
        """
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
        """
        Intercept a tool call, enforce approval rules, and either execute the tool or return a ToolMessage describing denial or error.
        
        If approval is granted (ALLOW or ALWAYS_ALLOW) this will invoke the provided handler and return its Command result or a ToolMessage containing the formatted tool response. If approval is denied, returns an error ToolMessage indicating the action was denied. On unexpected exceptions it returns an error ToolMessage describing the failure.
        
        Returns:
        	Command or ToolMessage: a Command if the handler produced one; otherwise a ToolMessage with the tool's result or an error/denial message.
        
        Raises:
        	GraphInterrupt: re-raises GraphInterrupt exceptions thrown by approval handling or the handler.
        """
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
    """
    Create a pattern-based extractor function that adds regex named-group captures from specified fields into a copy of the input args.
    
    Parameters:
        field_patterns (dict[str, str]): Mapping of argument field names to regex patterns. Patterns should include named groups for values to extract.
    
    Returns:
        extractor (Callable[[dict], dict]): A function that takes an args dict, copies it, and for each configured field that exists and matches its pattern merges the pattern's named-group captures into the returned dict. Fields with no match are left unchanged.
    """

    def pattern_generator(args: dict) -> dict:
        """
        Extract named capture groups from specified fields in `args` using the regex patterns provided when the generator was created, and merge those captures into a copy of the original arguments.
        
        Parameters:
            args (dict): Mapping of argument names to values. For each field that has a corresponding pattern, the value is converted to a string and matched against the pattern.
        
        Returns:
            dict: A shallow copy of `args` updated with any named groups extracted from matching fields. If a pattern matches, its named capture groups are added or overwrite existing keys in the returned dict.
        """
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
    """
    Create a transformer factory that applies string-based transformations to specified fields.
    
    Parameters:
        field_transforms (dict[str, Callable[[str], str]]): Mapping of field names to functions that accept a string and return a transformed string.
    
    Returns:
        Callable[[dict], dict]: A function that, given an args dict, returns a new dict where each listed field is replaced by the result of applying its transform to the field's string value. If a transform raises an exception, the original field value is retained.
    """

    def pattern_generator(args: dict) -> dict:
        """
        Apply configured transform functions to matching fields in the given arguments dictionary.
        
        For each field present in `args` that has an associated transform function, the function replaces that field's value with the transform result (transform is called with the field value converted to `str`). If a transform raises an exception, the original value is left unchanged.
        
        Parameters:
            args (dict): Original argument mapping whose values may be transformed.
        
        Returns:
            dict: A new dictionary with the same keys as `args` where fields with configured transforms are replaced by their transformed values; all other keys remain unchanged.
        """
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