import re
from dataclasses import dataclass


VOICE_PILLARS = [
    "Be calm, grounded, and emotionally present.",
    "Validate feelings before offering guidance.",
    "Be specific and human, never generic or clinical.",
    "Protect user agency: suggest, do not command.",
]

FORBIDDEN_PATTERNS = [
    "No diagnoses, medical claims, or emergency instructions.",
    "No guilt-inducing language, shame, or pressure.",
    "No robotic filler or repetitive opening lines.",
    "No over-promising outcomes or certainty.",
]

SIGNATURE_PHRASING_STYLE = [
    "Open with a short emotional acknowledgment.",
    "Use one reflective sentence that mirrors the core feeling.",
    "Offer one gentle reframe or one concrete next step.",
    "Close with a soft invitation, not a demand.",
]


@dataclass(frozen=True)
class EmotionalPlan:
    state: str
    strategy: str
    choreography: str


def build_persona_constitution() -> str:
    """Return stable personality constitution for system prompting."""
    pillars = "\n".join(f"- {p}" for p in VOICE_PILLARS)
    forbidden = "\n".join(f"- {p}" for p in FORBIDDEN_PATTERNS)
    style = "\n".join(f"- {p}" for p in SIGNATURE_PHRASING_STYLE)
    return (
        "Persona Constitution (CalmNest):\n"
        "Voice pillars:\n"
        f"{pillars}\n"
        "Forbidden patterns:\n"
        f"{forbidden}\n"
        "Signature phrasing style:\n"
        f"{style}"
    )


def infer_emotional_state(text: str) -> str:
    """Classify user's current emotional state using lightweight rules."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return "neutral"

    overwhelmed_patterns = r"\b(overwhelmed|too much|can't handle|burned out|exhausted)\b"
    lonely_patterns = r"\b(lonely|alone|no one|isolated|left out)\b"
    hopeful_patterns = r"\b(hopeful|better|progress|improving|finally|proud|grateful)\b"
    numb_patterns = r"\b(numb|empty|nothing|flat|detached)\b"
    anxious_patterns = r"\b(anxious|anxiety|panic|worried|scared|afraid)\b"
    sad_patterns = r"\b(sad|down|low|hurt|crying|heartbroken)\b"
    angry_patterns = r"\b(angry|frustrated|mad|annoyed|furious)\b"

    if re.search(overwhelmed_patterns, lowered):
        return "overwhelmed"
    if re.search(lonely_patterns, lowered):
        return "lonely"
    if re.search(hopeful_patterns, lowered):
        return "hopeful"
    if re.search(numb_patterns, lowered):
        return "numb"
    if re.search(anxious_patterns, lowered):
        return "anxious"
    if re.search(sad_patterns, lowered):
        return "sad"
    if re.search(angry_patterns, lowered):
        return "angry"
    return "neutral"


def infer_response_intent(text: str) -> str:
    """Infer user intent to drive response choreography."""
    lowered = (text or "").strip().lower()
    if re.search(r"\b(what should i do|help me|next step|plan|how do i|advice)\b", lowered):
        return "concrete_next_step"
    if re.search(r"\b(i feel|i am|i'm|it feels|i've been|vent)\b", lowered):
        return "validation_first"
    if "?" in lowered:
        return "reflective_summary"
    return "gentle_reframe"


def build_emotional_plan(text: str) -> EmotionalPlan:
    """Map emotional state + intent to a response strategy."""
    state = infer_emotional_state(text)
    intent = infer_response_intent(text)

    if state in {"overwhelmed", "anxious"}:
        strategy = "stabilize"
        choreography = "validation-first, reflective-summary, concrete-next-step"
    elif state in {"lonely", "sad", "numb"}:
        strategy = "connection"
        choreography = "validation-first, reflective-summary, gentle-reframe"
    elif state == "hopeful":
        strategy = "reinforce_progress"
        choreography = "reflective-summary, milestone-acknowledgment, concrete-next-step"
    elif state == "angry":
        strategy = "de-escalate"
        choreography = "validation-first, gentle-reframe, concrete-next-step"
    else:
        strategy = "supportive_clarity"
        choreography = "reflective-summary, concrete-next-step"

    if intent == "concrete_next_step" and "concrete-next-step" not in choreography:
        choreography += ", concrete-next-step"
    if intent == "validation_first" and "validation-first" not in choreography:
        choreography = f"validation-first, {choreography}"

    return EmotionalPlan(state=state, strategy=strategy, choreography=choreography)


def build_choreography_instruction(
    latest_user_text: str,
    ritual_hints: list[str] | None = None,
    relational_hints: list[str] | None = None,
) -> str:
    """Build dynamic response choreography instructions for the model."""
    plan = build_emotional_plan(latest_user_text)
    rituals = ritual_hints or []
    relation = relational_hints or []

    lines = [
        "Dynamic response guidance:",
        f"- Emotional state: {plan.state}",
        f"- Strategy: {plan.strategy}",
        f"- Choreography: {plan.choreography}",
        "- Keep one clear takeaway in the response.",
    ]

    if relation:
        lines.append("- Personalization hints:")
        lines.extend(f"  - {item}" for item in relation[:6])

    if rituals:
        lines.append("- Continuity rituals to apply when natural:")
        lines.extend(f"  - {item}" for item in rituals[:4])

    return "\n".join(lines)