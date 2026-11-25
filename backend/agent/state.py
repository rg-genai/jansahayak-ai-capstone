"""LangGraph AgentState and Pydantic models for JanSahayak AI."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


class CitizenProfile(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None
    state: str | None = None
    annual_income_inr: int | None = Field(default=None, ge=0)
    social_category: str | None = None  # SC, ST, OBC, EWS, General, Minority
    occupation: str | None = None
    is_bpl: bool | None = None
    is_pwd: bool | None = None
    education_level: str | None = None
    preferred_language: str = "en"

    def merge(self, updates: dict[str, Any] | None) -> "CitizenProfile":
        if not updates:
            return self
        data = self.model_dump()
        for k, v in updates.items():
            if k in data and v is not None and v != "":
                data[k] = v
        return CitizenProfile.model_validate(data)

    def non_empty_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None and v != ""}


class PlannedToolCall(BaseModel):
    tool_name: Literal[
        "search_schemes",
        "check_eligibility",
        "web_search_gov_schemes",
        "draft_grievance",
        "submit_or_track_grievance",
    ]
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    intent: Literal[
        "CONVERSATION_HELP",
        "SCHEME_QA",
        "ELIGIBILITY_CHECK",
        "GRIEVANCE_DRAFT",
        "GRIEVANCE_TRACK",
        "OUT_OF_SCOPE",
    ] = "SCHEME_QA"
    profile_updates: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[PlannedToolCall] = Field(default_factory=list)
    reasoning: str = ""
    # Set when this message answers the assistant's clarifying question: the original request it continues.
    continues_request: str | None = None

    @field_validator("continues_request", mode="before")
    @classmethod
    def _non_text_continuation_is_empty(cls, value: Any) -> Any:
        """Fault eval FI-03..05: Qwen3-8B's JSON repair filled this text field with true/false, failing the whole plan."""
        return value if value is None or isinstance(value, str) else None


class ReflectionOutput(BaseModel):
    """Reflector decision after observing one round of tool results."""

    decision: Literal["answer", "search_again", "check_eligibility", "ask_user"] = "answer"
    new_query: str | None = None
    scheme_slugs: list[str] = Field(default_factory=list)
    question: str | None = None
    reason: str = ""


class CriticOutput(BaseModel):
    passed: bool = True
    issues: list[str] = Field(default_factory=list)
    needs_revision: bool = False
    revision_instructions: str | None = None


class AgentState(TypedDict, total=False):
    session_id: str
    trace_id: str
    user_message_raw: str
    user_message_masked: str
    ui_language: str
    detected_lang: str
    query_en: str
    citizen_profile: dict[str, Any]
    history: list[dict[str, str]]
    conversation_summary: str
    active_scheme_slugs: list[str]
    pending_grievance_draft_id: str | None

    # Guardrail state
    guardrail_blocked: bool
    guardrail_category: str | None
    guardrail_flags: list[str]
    pii_warning: str | None

    # Planner / Executor / Synthesizer / Critic outputs
    planner_output: dict[str, Any]
    tool_calls_log: list[dict[str, Any]]
    retrieved_chunks: list[dict[str, Any]]
    web_results: list[dict[str, Any]]
    eligibility_cards: list[dict[str, Any]]
    grievance_draft: dict[str, Any] | None
    grievance_receipt: dict[str, Any] | None
    hitl_paused: bool

    # Agent loop (Reflector) state
    reflection_round: int
    reflections: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]  # tool calls requested by the Reflector for the next round
    searched_queries: list[str]
    clarifying_question: str | None

    draft_answer_en: str
    critic_output: dict[str, Any]
    revision_count: int
    final_answer: str
    citations: list[dict[str, Any]]

    # Telemetry & Langfuse-style Spans
    prompt_tokens: int
    completion_tokens: int
    step_latencies: dict[str, float]
    spans: list[dict[str, Any]]
    trace_start_monotonic: float
    status: str
    cache_hit: str
    query_embedding: Any
    prompt_strategy: str  # P1 | P2 | P3 (defaults to P3)
    skip_critic_llm: bool
