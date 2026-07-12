import uuid

from pydantic import BaseModel, Field


class ParsedHypothesis(BaseModel):
    """Structured output for parsed hypothesis."""

    uid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the hypothesis",
    )
    hypothesis: str = Field(description="The main hypothesis statement")
    predictions: list[str] = Field(
        description="A list of predictions that could be tested to disprove the hypothesis"
    )
    assumptions: list[str] = Field(
        description="A list of assumptions that are implicit or explicit in the hypothesis"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="A list of supporting literature sources"
    )
    elo: float = Field(
        default=1200.0,
        description="Elo score for tournament ranking"
    )
    novelty_score: float = Field(
        default=0.0,
        description="Optional proxy score for novelty"
    )
    parent_uid: str | None = Field(
        default=None,
        description="The unique identifier of the parent hypothesis, if applicable",
    )


class ReviewedHypothesis(ParsedHypothesis):
    """Structured output for reviewed hypothesis."""

    causal_reasoning: str = Field(description="The causal reasoning for the hypothesis")
    correctness_flag: bool = Field(default=True, description="Flag indicating if the hypothesis is scientifically valid")
    novelty_flag: bool = Field(default=True, description="Flag indicating if the hypothesis is novel")
    critique: str = Field(default="", description="Detailed critique notes from reflection")
    assumption_research_results: dict[str, str] = Field(
        default_factory=dict,
        description="A dictionary of assumption research results"
    )
    verification_result: str = Field(
        default="",
        description="The result of the deep verification process"
    )


class RankingMatchResult(BaseModel):
    """Result of a match between two hypotheses."""

    hypoA_id: str = Field(description="Unique identifier for the first hypothesis")
    hypoB_id: str = Field(description="Unique identifier for the second hypothesis")
    winner_id: str = Field(description="The unique identifier of the winning hypothesis")
    rationale: str = Field(description="The debate/rationale explaining the winner")
