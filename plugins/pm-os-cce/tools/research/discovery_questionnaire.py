"""
PM-OS CCE DiscoveryQuestionnaire (v5.0)

Interactive feature context gathering through a branching questionnaire flow.
Supports one-pager import, new/existing product branching, and deep research
opt-in. Runs during the QUESTIONNAIRE phase of the feature lifecycle.

Usage:
    from pm_os_cce.tools.research.discovery_questionnaire import (
        DiscoveryQuestionnaire, QuestionnaireResult
    )
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QuestionType(Enum):
    """Types of questions in the questionnaire flow."""

    YES_NO = "yes_no"
    TEXT = "text"
    MULTI_SELECT = "multi_select"
    SINGLE_SELECT = "single_select"
    OPTIONAL_TEXT = "optional_text"


@dataclass
class Question:
    """
    A single question in the questionnaire flow.

    Attributes:
        id: Unique identifier for the question
        text: The question text displayed to the user
        question_type: Type of input expected
        options: Available options for select-type questions
        required: Whether the question must be answered
        branch_on: Maps answer values to next question IDs for branching
        help_text: Additional guidance for the user
    """

    id: str
    text: str
    question_type: QuestionType
    options: List[str] = field(default_factory=list)
    required: bool = True
    branch_on: Optional[Dict[str, str]] = None
    help_text: str = ""


@dataclass
class QuestionnaireResult:
    """
    Structured output of the discovery questionnaire.

    Contains all answers collected during the questionnaire flow,
    mapped to standard fields for use by the research plan generator
    and context document generator.

    Serializable to dict for storage in feature-state.yaml.
    """

    # Initial routing
    has_one_pager: bool = False
    one_pager_content: Optional[str] = None
    is_new_product: bool = False

    # Core feature information
    users: str = ""
    user_problem: str = ""
    business_problem: str = ""
    feature_description: str = ""

    # Product context
    product: str = ""
    brand: str = ""
    market: str = ""
    platform: str = ""

    # Optional context
    page_component: Optional[str] = None
    competitors: Optional[List[str]] = None

    # Deep research opt-in
    wants_deep_research: bool = False

    # Design/code context (optional)
    target_repo: Optional[str] = None
    figma_link: Optional[str] = None

    # Raw answers for audit trail
    raw_answers: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for YAML/JSON serialization."""
        result: Dict[str, Any] = {
            "has_one_pager": self.has_one_pager,
            "is_new_product": self.is_new_product,
            "users": self.users,
            "user_problem": self.user_problem,
            "business_problem": self.business_problem,
            "feature_description": self.feature_description,
            "product": self.product,
            "brand": self.brand,
            "market": self.market,
            "platform": self.platform,
            "wants_deep_research": self.wants_deep_research,
        }

        if self.one_pager_content:
            result["one_pager_content"] = self.one_pager_content

        if self.page_component:
            result["page_component"] = self.page_component

        if self.competitors:
            result["competitors"] = self.competitors

        if self.target_repo:
            result["target_repo"] = self.target_repo

        if self.figma_link:
            result["figma_link"] = self.figma_link

        if self.raw_answers:
            result["raw_answers"] = self.raw_answers

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuestionnaireResult":
        """Create QuestionnaireResult from dictionary."""
        return cls(
            has_one_pager=data.get("has_one_pager", False),
            one_pager_content=data.get("one_pager_content"),
            is_new_product=data.get("is_new_product", False),
            users=data.get("users", ""),
            user_problem=data.get("user_problem", ""),
            business_problem=data.get("business_problem", ""),
            feature_description=data.get("feature_description", ""),
            product=data.get("product", ""),
            brand=data.get("brand", ""),
            market=data.get("market", ""),
            platform=data.get("platform", ""),
            page_component=data.get("page_component"),
            competitors=data.get("competitors"),
            wants_deep_research=data.get("wants_deep_research", False),
            target_repo=data.get("target_repo"),
            figma_link=data.get("figma_link"),
            raw_answers=data.get("raw_answers", {}),
        )


# ============================================================================
# QUESTION DEFINITIONS
# ============================================================================

# Initial routing questions (asked for all features)
INITIAL_QUESTIONS = [
    Question(
        id="has_one_pager",
        text="Do you have a 1-pager already done?",
        question_type=QuestionType.YES_NO,
        help_text=(
            "If you have an existing document describing this feature, "
            "I can extract the key information from it."
        ),
        branch_on={"yes": "_one_pager_import", "no": "is_new_product"},
    ),
    Question(
        id="is_new_product",
        text="Is this for a new product or an existing one?",
        question_type=QuestionType.SINGLE_SELECT,
        options=["Existing product", "New product"],
        branch_on={
            "Existing product": "_existing_flow",
            "New product": "_new_flow",
        },
    ),
]

# Questions for existing product features
EXISTING_PRODUCT_QUESTIONS = [
    Question(
        id="users",
        text="Who are the users of this product/feature?",
        question_type=QuestionType.TEXT,
        help_text="Describe the target user personas.",
    ),
    Question(
        id="user_problem",
        text="What is the problem of the user?",
        question_type=QuestionType.TEXT,
        help_text="What pain point or unmet need does this address?",
    ),
    Question(
        id="business_problem",
        text="What is the problem of the business?",
        question_type=QuestionType.TEXT,
        help_text="What business metric or goal is impacted?",
    ),
    Question(
        id="feature_description",
        text="Describe the feature in a paragraph -- what are we trying to achieve?",
        question_type=QuestionType.TEXT,
        help_text="A concise description of the feature's purpose and expected outcome.",
    ),
    Question(
        id="product",
        text="Which product is this for?",
        question_type=QuestionType.TEXT,
        help_text="Enter the product name or identifier.",
    ),
    Question(
        id="brand",
        text="Which brand?",
        question_type=QuestionType.TEXT,
        help_text="Enter the brand name.",
    ),
    Question(
        id="market",
        text="Which market?",
        question_type=QuestionType.TEXT,
        help_text="Enter the target market or region.",
    ),
    Question(
        id="platform",
        text="Which platform?",
        question_type=QuestionType.SINGLE_SELECT,
        options=["Web", "iOS", "Android", "All"],
    ),
    Question(
        id="page_component",
        text="Which page/component does this impact?",
        question_type=QuestionType.OPTIONAL_TEXT,
        required=False,
        help_text="Optional. Enter the page or component name, or skip.",
    ),
    Question(
        id="competitors",
        text="Do similar features & products exist among competitors? Please list them.",
        question_type=QuestionType.OPTIONAL_TEXT,
        required=False,
        help_text="Optional. List competitor products/features, or skip.",
    ),
]

# Questions for new product features
NEW_PRODUCT_QUESTIONS = [
    Question(
        id="users",
        text="Who are the users of this product/feature?",
        question_type=QuestionType.TEXT,
        help_text="Describe the target user personas.",
    ),
    Question(
        id="user_problem",
        text="What is the problem of the user?",
        question_type=QuestionType.TEXT,
        help_text="What pain point or unmet need does this address?",
    ),
    Question(
        id="business_problem",
        text="What is the problem of the business?",
        question_type=QuestionType.TEXT,
        help_text="What business goal or opportunity is this pursuing?",
    ),
    Question(
        id="feature_description",
        text="Describe the feature in a paragraph -- what are we trying to achieve?",
        question_type=QuestionType.TEXT,
        help_text="A concise description of the product/feature's purpose and expected outcome.",
    ),
    Question(
        id="brand",
        text="Which brand?",
        question_type=QuestionType.TEXT,
        help_text="Enter the brand name, or TBD if not yet decided.",
    ),
    Question(
        id="market",
        text="Which market?",
        question_type=QuestionType.TEXT,
        help_text="Enter the target market or region.",
    ),
    Question(
        id="platform",
        text="Which platform?",
        question_type=QuestionType.SINGLE_SELECT,
        options=["Web", "iOS", "Android", "All"],
    ),
    Question(
        id="page_component",
        text="Which page/component does this impact?",
        question_type=QuestionType.OPTIONAL_TEXT,
        required=False,
        help_text="Optional. Enter the page or component name, or skip.",
    ),
    Question(
        id="competitors",
        text="Do similar features & products exist? Please list them.",
        question_type=QuestionType.OPTIONAL_TEXT,
        required=False,
        help_text="Optional. List any existing products/features in the market, or skip.",
    ),
]

# Optional design/code context questions
TARGET_REPO_QUESTION = Question(
    id="target_repo",
    text="Which repo should we target for code review?",
    question_type=QuestionType.OPTIONAL_TEXT,
    required=False,
    help_text=(
        "Optional. If specified, deep research will analyze this repo's "
        "architecture and component patterns. Can be skipped."
    ),
)

FIGMA_LINK_QUESTION = Question(
    id="figma_link",
    text="Is there a Figma link for this feature?",
    question_type=QuestionType.OPTIONAL_TEXT,
    required=False,
    help_text=(
        "Optional. Paste the Figma URL if a design file exists for this "
        "feature. Can be skipped."
    ),
)

# Final question (asked for all flows)
DEEP_RESEARCH_QUESTION = Question(
    id="wants_deep_research",
    text=(
        "Do you want me to perform deep research across available resources "
        "to generate additional context?"
    ),
    question_type=QuestionType.YES_NO,
    help_text=(
        "I'll search configured internal systems and external sources to "
        "build a comprehensive research document before creating the context file."
    ),
)


class DiscoveryQuestionnaire:
    """
    Manages the branching questionnaire flow for feature discovery.

    Provides question sequences for different flows (new/existing product),
    builds structured results from raw answers, and formats summaries for
    user review.
    """

    def get_initial_questions(self) -> List[Question]:
        """Get the initial routing questions."""
        return list(INITIAL_QUESTIONS)

    def get_question_flow(self, is_new_product: bool) -> List[Question]:
        """
        Get the full question flow for the given product type.

        Args:
            is_new_product: True for new product flow, False for existing

        Returns:
            Ordered list of questions (excludes initial routing questions)
        """
        if is_new_product:
            questions = list(NEW_PRODUCT_QUESTIONS)
        else:
            questions = list(EXISTING_PRODUCT_QUESTIONS)

        # Append optional design/code context questions
        questions.append(TARGET_REPO_QUESTION)
        questions.append(FIGMA_LINK_QUESTION)

        # Append deep research opt-in
        questions.append(DEEP_RESEARCH_QUESTION)

        return questions

    def get_all_questions(self, is_new_product: bool) -> List[Question]:
        """
        Get all questions including initial routing.

        Args:
            is_new_product: True for new product flow, False for existing

        Returns:
            Complete ordered list of all questions
        """
        questions = self.get_initial_questions()
        questions.extend(self.get_question_flow(is_new_product))
        return questions

    def build_result(self, answers: Dict[str, Any]) -> QuestionnaireResult:
        """
        Build a QuestionnaireResult from raw answer dictionary.

        Args:
            answers: Dict mapping question IDs to answer values

        Returns:
            Structured QuestionnaireResult
        """
        # Parse yes/no answers
        has_one_pager = _parse_yes_no(answers.get("has_one_pager", "no"))
        is_new_str = answers.get("is_new_product", "Existing product")
        is_new_product = is_new_str in ("New product", "new", True, "yes")
        wants_deep_research = _parse_yes_no(
            answers.get("wants_deep_research", "no")
        )

        # Parse competitors - split on commas/newlines if string
        competitors_raw = answers.get("competitors")
        competitors = _parse_list_answer(competitors_raw)

        # Parse optional page_component
        page_component = answers.get("page_component")
        if page_component and isinstance(page_component, str):
            page_component = page_component.strip() or None

        # Parse optional target_repo and figma_link
        target_repo = answers.get("target_repo")
        if target_repo and isinstance(target_repo, str):
            target_repo = target_repo.strip() or None

        figma_link = answers.get("figma_link")
        if figma_link and isinstance(figma_link, str):
            figma_link = figma_link.strip() or None

        return QuestionnaireResult(
            has_one_pager=has_one_pager,
            one_pager_content=answers.get("one_pager_content"),
            is_new_product=is_new_product,
            users=str(answers.get("users", "")).strip(),
            user_problem=str(answers.get("user_problem", "")).strip(),
            business_problem=str(answers.get("business_problem", "")).strip(),
            feature_description=str(
                answers.get("feature_description", "")
            ).strip(),
            product=str(answers.get("product", "")).strip(),
            brand=str(answers.get("brand", "")).strip(),
            market=str(answers.get("market", "")).strip(),
            platform=str(answers.get("platform", "")).strip(),
            page_component=page_component,
            competitors=competitors,
            wants_deep_research=wants_deep_research,
            target_repo=target_repo,
            figma_link=figma_link,
            raw_answers=answers,
        )

    def format_summary(self, result: QuestionnaireResult) -> str:
        """
        Format the questionnaire result as a readable Markdown summary.

        Args:
            result: The structured questionnaire result

        Returns:
            Markdown string summarizing all answers
        """
        lines = ["## Discovery Questionnaire Summary\n"]

        # Product type
        product_type = "New Product" if result.is_new_product else "Existing Product"
        lines.append(f"**Type:** {product_type}")

        if result.has_one_pager:
            lines.append("**Source:** 1-pager document (imported)")

        lines.append("")

        # Core information
        lines.append("### Feature Context")
        if result.users:
            lines.append(f"- **Users:** {result.users}")
        if result.user_problem:
            lines.append(f"- **User Problem:** {result.user_problem}")
        if result.business_problem:
            lines.append(f"- **Business Problem:** {result.business_problem}")
        if result.feature_description:
            lines.append(f"- **Description:** {result.feature_description}")

        lines.append("")

        # Product context
        lines.append("### Product Context")
        if result.product:
            lines.append(f"- **Product:** {result.product}")
        if result.brand:
            lines.append(f"- **Brand:** {result.brand}")
        if result.market:
            lines.append(f"- **Market:** {result.market}")
        if result.platform:
            lines.append(f"- **Platform:** {result.platform}")
        if result.page_component:
            lines.append(f"- **Page/Component:** {result.page_component}")

        lines.append("")

        # Competitors
        if result.competitors:
            lines.append("### Competitors / Similar Products")
            for comp in result.competitors:
                lines.append(f"- {comp}")
            lines.append("")

        # Research opt-in
        research_status = "Yes" if result.wants_deep_research else "No"
        lines.append(f"**Deep Research:** {research_status}")

        return "\n".join(lines)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _parse_yes_no(value: Any) -> bool:
    """Parse a yes/no answer to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("yes", "y", "true", "1")
    return False


def _parse_list_answer(value: Any) -> Optional[List[str]]:
    """Parse a list-type answer, splitting strings on commas/newlines."""
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Split on commas, semicolons, or newlines
        items = []
        for delimiter in ["\n", ";", ","]:
            if delimiter in value:
                items = [item.strip() for item in value.split(delimiter)]
                break
        if not items:
            items = [value]
        return [item for item in items if item]
    return None
