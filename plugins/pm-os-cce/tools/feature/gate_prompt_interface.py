"""
PM-OS CCE Gate Prompt Interface (v5.0)

User prompt interface for approval gates following PRD A.2.
Formats gate prompts for display, parses user responses, and handles
different action types with optional inputs.

Usage:
    from pm_os_cce.tools.feature.gate_prompt_interface import GatePromptInterface, ParsedResponse
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_cce.tools.feature.input_gate import GateAction, GateResult, GateState, InputGate
except ImportError:
    from feature.input_gate import GateAction, GateResult, GateState, InputGate

# Box drawing characters for prompt formatting
BOX_TOP_LEFT = "+"
BOX_TOP_RIGHT = "+"
BOX_BOTTOM_LEFT = "+"
BOX_BOTTOM_RIGHT = "+"
BOX_HORIZONTAL = "-"
BOX_VERTICAL = "|"
BOX_SEPARATOR = "+"

# Unicode alternatives (for rich terminal support)
UNICODE_BOX = {
    "top_left": "\u250c",
    "top_right": "\u2510",
    "bottom_left": "\u2514",
    "bottom_right": "\u2518",
    "horizontal": "\u2500",
    "vertical": "\u2502",
    "separator_left": "\u251c",
    "separator_right": "\u2524",
}

# Default prompt width
DEFAULT_WIDTH = 65


class ResponseType(Enum):
    """Types of parsed user responses."""

    ACTION = "action"
    INPUT = "input"
    OPTION = "option"
    INVALID = "invalid"


@dataclass
class OptionalInput:
    """Optional input that can be added during gate approval."""

    name: str
    description: str
    input_type: str  # text, url, date, name_date
    value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "input_type": self.input_type,
            "value": self.value,
        }


@dataclass
class ParsedResponse:
    """Result of parsing a user response."""

    response_type: ResponseType
    action: Optional[GateAction] = None
    value: Optional[str] = None
    optional_inputs: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if response is valid."""
        return self.response_type != ResponseType.INVALID

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "response_type": self.response_type.value,
            "is_valid": self.is_valid,
        }
        if self.action:
            result["action"] = self.action.value
        if self.value:
            result["value"] = self.value
        if self.optional_inputs:
            result["optional_inputs"] = self.optional_inputs
        if self.error_message:
            result["error_message"] = self.error_message
        return result


@dataclass
class ActionDetails:
    """Details needed to execute a gate action."""

    action: GateAction
    display_name: str
    shortcut: str
    description: str
    requires_input: bool = False
    input_prompt: Optional[str] = None
    input_type: Optional[str] = None  # text, date, url
    optional_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action.value,
            "display_name": self.display_name,
            "shortcut": self.shortcut,
            "description": self.description,
            "requires_input": self.requires_input,
            "input_prompt": self.input_prompt,
            "input_type": self.input_type,
            "optional_fields": self.optional_fields,
        }


# Action configuration
ACTION_DETAILS: Dict[GateAction, ActionDetails] = {
    GateAction.APPROVE: ActionDetails(
        action=GateAction.APPROVE,
        display_name="Approve",
        shortcut="A",
        description="proceed to next phase",
        requires_input=False,
        optional_fields=["stakeholder_approval", "notes"],
    ),
    GateAction.REQUEST_CHANGES: ActionDetails(
        action=GateAction.REQUEST_CHANGES,
        display_name="Request Changes",
        shortcut="C",
        description="specify what needs updating",
        requires_input=True,
        input_prompt="What changes are needed?",
        input_type="text",
    ),
    GateAction.REJECT: ActionDetails(
        action=GateAction.REJECT,
        display_name="Reject",
        shortcut="R",
        description="archive feature with reason",
        requires_input=True,
        input_prompt="Reason for rejection:",
        input_type="text",
    ),
    GateAction.DEFER: ActionDetails(
        action=GateAction.DEFER,
        display_name="Defer",
        shortcut="D",
        description="pause, set reminder date",
        requires_input=True,
        input_prompt="When to revisit? (YYYY-MM-DD or description):",
        input_type="date",
        optional_fields=["defer_reason"],
    ),
    GateAction.RESUME: ActionDetails(
        action=GateAction.RESUME,
        display_name="Resume",
        shortcut="U",
        description="continue from deferred state",
        requires_input=False,
    ),
    GateAction.INITIATE: ActionDetails(
        action=GateAction.INITIATE,
        display_name="Initiate",
        shortcut="I",
        description="begin the approval process",
        requires_input=False,
    ),
}


# Optional input configurations
OPTIONAL_INPUTS: Dict[str, OptionalInput] = {
    "stakeholder_approval": OptionalInput(
        name="stakeholder_approval",
        description="Add stakeholder approval (name, date)",
        input_type="name_date",
    ),
    "artifact_url": OptionalInput(
        name="artifact_url",
        description="Attach external artifact (URL)",
        input_type="url",
    ),
    "notes": OptionalInput(
        name="notes",
        description="Add notes for next phase",
        input_type="text",
    ),
}


class GatePromptInterface:
    """User prompt interface for approval gates.

    Provides consistent formatting and parsing for gate interactions
    following the PRD A.2 interface design.
    """

    def __init__(self, width: int = DEFAULT_WIDTH, use_unicode: bool = False):
        """Initialize the prompt interface.

        Args:
            width: Width of the prompt box (default 65)
            use_unicode: Use Unicode box characters (default False for compatibility)
        """
        self.width = width
        self.use_unicode = use_unicode

        if use_unicode:
            self.top_left = UNICODE_BOX["top_left"]
            self.top_right = UNICODE_BOX["top_right"]
            self.bottom_left = UNICODE_BOX["bottom_left"]
            self.bottom_right = UNICODE_BOX["bottom_right"]
            self.horizontal = UNICODE_BOX["horizontal"]
            self.vertical = UNICODE_BOX["vertical"]
            self.sep_left = UNICODE_BOX["separator_left"]
            self.sep_right = UNICODE_BOX["separator_right"]
        else:
            self.top_left = BOX_TOP_LEFT
            self.top_right = BOX_TOP_RIGHT
            self.bottom_left = BOX_BOTTOM_LEFT
            self.bottom_right = BOX_BOTTOM_RIGHT
            self.horizontal = BOX_HORIZONTAL
            self.vertical = BOX_VERTICAL
            self.sep_left = BOX_SEPARATOR
            self.sep_right = BOX_SEPARATOR

    # ========== Formatting Methods ==========

    def _make_border(self, border_type: str = "full") -> str:
        """Create a horizontal border line."""
        inner_width = self.width - 2

        if border_type == "top":
            return f"{self.top_left}{self.horizontal * inner_width}{self.top_right}"
        elif border_type == "bottom":
            return (
                f"{self.bottom_left}{self.horizontal * inner_width}{self.bottom_right}"
            )
        elif border_type == "separator":
            return f"{self.sep_left}{self.horizontal * inner_width}{self.sep_right}"
        else:
            return f"{BOX_SEPARATOR}{self.horizontal * inner_width}{BOX_SEPARATOR}"

    def _make_line(self, text: str = "", padding: int = 1) -> str:
        """Create a content line within the box."""
        inner_width = self.width - 2
        padded_text = " " * padding + text
        return f"{self.vertical}{padded_text.ljust(inner_width)}{self.vertical}"

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """Wrap text to fit within max width."""
        if not text:
            return [""]

        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            if current_length + word_length + len(current_line) <= max_width:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [""]

    def format_prompt(
        self,
        gate: InputGate,
        content: str,
        feature_title: Optional[str] = None,
        show_optional: bool = True,
    ) -> str:
        """Format a gate prompt for display following PRD A.2 design."""
        lines = []
        inner_width = self.width - 4

        # === Header Section ===
        lines.append(self._make_border("top"))
        lines.append(self._make_line(f"INPUT REQUIRED: {gate.name}"))

        display_name = feature_title or gate.feature_slug
        lines.append(self._make_line(f"Feature: {display_name}"))
        lines.append(self._make_line(f"Phase: {gate.phase.replace('_', ' ').title()}"))

        if gate.state != GateState.PENDING_INPUT:
            lines.append(
                self._make_line(f"Status: {gate.state.value.replace('_', ' ').title()}")
            )

        lines.append(self._make_border("separator"))

        # === Content Section ===
        lines.append(self._make_line())

        content_lines = self._wrap_text(content, inner_width)
        for line in content_lines:
            lines.append(self._make_line(line))

        lines.append(self._make_line())

        missing_inputs = gate.missing_inputs
        if missing_inputs:
            lines.append(self._make_line("Required Inputs:"))
            for inp in gate.inputs:
                if inp.required:
                    status = "[x]" if inp.value is not None else "[ ]"
                    lines.append(self._make_line(f"  {status} {inp.name}"))
            lines.append(self._make_line())

        lines.append(self._make_border("separator"))

        # === Actions Section ===
        lines.append(self._make_line("Required Action:"))

        valid_actions = gate.get_valid_actions()

        for action in valid_actions:
            if action in ACTION_DETAILS:
                details = ACTION_DETAILS[action]
                action_line = f"  ({details.shortcut}) {details.display_name} - {details.description}"
                lines.append(self._make_line(action_line))

        lines.append(self._make_line())

        # === Optional Section ===
        if show_optional:
            lines.append(self._make_line("Optional:"))
            lines.append(self._make_line("  [ ] Add stakeholder approval (name, date)"))
            lines.append(self._make_line("  [ ] Attach external artifact (URL)"))
            lines.append(self._make_line("  [ ] Add notes for next phase"))
            lines.append(self._make_line())

        lines.append(self._make_border("bottom"))

        return "\n".join(lines)

    def format_compact_prompt(
        self, gate: InputGate, content: Optional[str] = None
    ) -> str:
        """Format a compact version of the gate prompt."""
        lines = [
            f"=== {gate.name} ===",
            f"Feature: {gate.feature_slug}",
            f"Phase: {gate.phase}",
        ]

        if content:
            lines.append(f"\n{content}\n")

        lines.append("\nActions:")
        for action in gate.get_valid_actions():
            if action in ACTION_DETAILS:
                details = ACTION_DETAILS[action]
                lines.append(f"  [{details.shortcut}] {details.display_name}")

        lines.append("\nEnter choice: ")

        return "\n".join(lines)

    # ========== Parsing Methods ==========

    def parse_response(self, response: str) -> ParsedResponse:
        """Parse a user response string."""
        if not response:
            return ParsedResponse(
                response_type=ResponseType.INVALID, error_message="Empty response"
            )

        response = response.strip()

        first_char = response[0].upper()

        for action, details in ACTION_DETAILS.items():
            if details.shortcut == first_char:
                value = None
                optional_inputs = {}

                if ":" in response:
                    value = response.split(":", 1)[1].strip()
                elif len(response) > 1 and response[1] == " ":
                    value = response[2:].strip()

                optional_inputs = self._parse_optional_inputs(response)

                return ParsedResponse(
                    response_type=ResponseType.ACTION,
                    action=action,
                    value=value,
                    optional_inputs=optional_inputs,
                )

        response_lower = response.lower()
        for action, details in ACTION_DETAILS.items():
            if response_lower.startswith(details.display_name.lower()):
                value = None
                rest = response[len(details.display_name) :].strip()
                if rest.startswith(":"):
                    value = rest[1:].strip()
                elif rest:
                    value = rest

                return ParsedResponse(
                    response_type=ResponseType.ACTION,
                    action=action,
                    value=value,
                    optional_inputs=self._parse_optional_inputs(response),
                )

        if response_lower in ("y", "yes"):
            return ParsedResponse(
                response_type=ResponseType.ACTION,
                action=GateAction.APPROVE,
            )
        elif response_lower in ("n", "no"):
            return ParsedResponse(
                response_type=ResponseType.ACTION,
                action=GateAction.REJECT,
                value="User declined",
            )

        return ParsedResponse(
            response_type=ResponseType.INVALID,
            error_message=f"Unknown action: {response}. Use A/C/R/D or full action name.",
        )

    def _parse_optional_inputs(self, response: str) -> Dict[str, Any]:
        """Parse optional inputs from response string (--key=value format)."""
        inputs = {}

        pattern = r'--(\w+)=(?:\'([^\']*?)\'|"([^"]*?)"|(\S+))'

        for match in re.finditer(pattern, response):
            key = match.group(1)
            value = match.group(2) or match.group(3) or match.group(4)
            if value:
                inputs[key] = value

        return inputs

    def parse_multi_step_response(
        self, responses: List[str], action: GateAction
    ) -> ParsedResponse:
        """Parse a multi-step response for actions requiring input."""
        details = ACTION_DETAILS.get(action)
        if not details:
            return ParsedResponse(
                response_type=ResponseType.INVALID,
                error_message=f"Unknown action: {action}",
            )

        value = None
        optional_inputs = {}

        if responses and details.requires_input:
            value = responses[0].strip()

        for i, field_name in enumerate(details.optional_fields):
            if i + 1 < len(responses):
                optional_inputs[field_name] = responses[i + 1].strip()

        return ParsedResponse(
            response_type=ResponseType.ACTION,
            action=action,
            value=value,
            optional_inputs=optional_inputs,
        )

    # ========== Action Details Methods ==========

    def get_action_details(self, action: GateAction) -> Optional[ActionDetails]:
        """Get detailed information about an action."""
        return ACTION_DETAILS.get(action)

    def get_all_action_details(self) -> Dict[str, ActionDetails]:
        """Get details for all supported actions."""
        return {action.value: details for action, details in ACTION_DETAILS.items()}

    def get_input_prompt_for_action(self, action: GateAction) -> Optional[str]:
        """Get the input prompt for an action that requires input."""
        details = ACTION_DETAILS.get(action)
        if details and details.requires_input:
            return details.input_prompt
        return None

    def get_shortcuts(self) -> Dict[str, GateAction]:
        """Get mapping of shortcuts to actions."""
        return {details.shortcut: action for action, details in ACTION_DETAILS.items()}

    # ========== Interaction Processing ==========

    def process_interaction(
        self,
        gate: InputGate,
        user_input: str,
        decided_by: str,
        additional_inputs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[GateResult, ParsedResponse]:
        """Process a complete gate interaction.

        Parses the user input, validates it against the gate state,
        and executes the appropriate transition.

        Args:
            gate: The InputGate to process
            user_input: Raw user input string
            decided_by: Who is taking the action
            additional_inputs: Optional pre-collected inputs

        Returns:
            Tuple of (GateResult, ParsedResponse)
        """
        parsed = self.parse_response(user_input)

        if not parsed.is_valid:
            return (
                GateResult(
                    success=False,
                    new_state=gate.state,
                    message=parsed.error_message or "Invalid response",
                ),
                parsed,
            )

        all_inputs = {**(additional_inputs or {}), **parsed.optional_inputs}

        if parsed.action and not gate.can_transition(parsed.action):
            return (
                GateResult(
                    success=False,
                    new_state=gate.state,
                    message=f"Action '{parsed.action.value}' not valid from state '{gate.state.value}'",
                ),
                parsed,
            )

        details = self.get_action_details(parsed.action)
        if details and details.requires_input and not parsed.value:
            return (
                GateResult(
                    success=False,
                    new_state=gate.state,
                    message=f"Action '{parsed.action.value}' requires input: {details.input_prompt}",
                ),
                parsed,
            )

        defer_until = None
        if parsed.action == GateAction.DEFER and parsed.value:
            defer_until = self._parse_date(parsed.value)

        result = gate.transition(
            action=parsed.action,
            decided_by=decided_by,
            notes=parsed.value,
            defer_until=defer_until,
            metadata=all_inputs if all_inputs else None,
        )

        return result, parsed

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string (YYYY-MM-DD or MM/DD/YYYY)."""
        date_str = date_str.strip()

        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            pass

        return None

    # ========== Validation Methods ==========

    def validate_response_for_gate(
        self, response: ParsedResponse, gate: InputGate
    ) -> Tuple[bool, Optional[str]]:
        """Validate a parsed response against a gate's requirements."""
        if not response.is_valid:
            return False, response.error_message

        if not response.action:
            return False, "No action specified"

        if not gate.can_transition(response.action):
            valid_actions = gate.get_valid_actions()
            valid_str = ", ".join(a.value for a in valid_actions)
            return False, f"Invalid action for current state. Valid: {valid_str}"

        details = self.get_action_details(response.action)
        if details and details.requires_input and not response.value:
            return False, f"Input required: {details.input_prompt}"

        return True, None

    # ========== Help and Documentation ==========

    def get_help_text(self) -> str:
        """Get help text explaining available actions and usage."""
        lines = [
            "=== Gate Prompt Help ===",
            "",
            "Available Actions:",
        ]

        for action, details in ACTION_DETAILS.items():
            lines.append(f"  [{details.shortcut}] {details.display_name}")
            lines.append(f"      {details.description}")
            if details.requires_input:
                lines.append(f"      Requires: {details.input_prompt}")
            lines.append("")

        lines.extend(
            [
                "Response Formats:",
                "  Single letter: A, C, R, D",
                "  With value: R: Not aligned with roadmap",
                "  With options: A --stakeholder='John' --notes='LGTM'",
                "",
                "Optional Inputs:",
                "  --stakeholder='Name' - Add stakeholder approval",
                "  --date='YYYY-MM-DD' - Add date (for approvals or defer)",
                "  --artifact='URL' - Attach external artifact",
                "  --notes='text' - Add notes for next phase",
            ]
        )

        return "\n".join(lines)

    def get_action_help(self, action: GateAction) -> str:
        """Get help text for a specific action."""
        details = self.get_action_details(action)
        if not details:
            return f"Unknown action: {action}"

        lines = [
            f"=== {details.display_name} ===",
            f"Shortcut: [{details.shortcut}]",
            f"Description: {details.description}",
        ]

        if details.requires_input:
            lines.append("Requires Input: Yes")
            lines.append(f"Input Prompt: {details.input_prompt}")
        else:
            lines.append("Requires Input: No")

        if details.optional_fields:
            lines.append(f"Optional Fields: {', '.join(details.optional_fields)}")

        return "\n".join(lines)


# Convenience function for quick formatting
def format_gate_prompt(
    gate: InputGate, content: str, feature_title: Optional[str] = None
) -> str:
    """Quick function to format a gate prompt."""
    interface = GatePromptInterface()
    return interface.format_prompt(gate, content, feature_title)


# Convenience function for quick parsing
def parse_gate_response(response: str) -> ParsedResponse:
    """Quick function to parse a gate response."""
    interface = GatePromptInterface()
    return interface.parse_response(response)
