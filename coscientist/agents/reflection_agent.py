"""
Reflection agent
---------------
- Full review with web search
- Simulation review
- Tournament review
- Deep verification

More details:
- Fully reviews a hypothesis with web search
- Observation review checks to see if there is unexplained observational
data that would be explained by the hypothesis.
- Simulation does a step-by-step rollout of a proposed mechanism of
action or experiment.
- Tournament review uses the output from the Ranking agent to find
recurring issues and opportunities for improvement.
TODO: Break the assumptions from the generation agent into additional assumptions
and sub-assumptions.
TODO: Add the observation reflection and simulation prompts. Figure out how to web search
for the observations to review.
"""

import functools
import asyncio
import os
import re
from typing import Optional, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from coscientist.services.common import load_prompt, truncate_text
from coscientist.models.custom_types import ParsedHypothesis, ReviewedHypothesis
from coscientist.retrieval.search import research_assumption
from coscientist.configs.config import settings


class ReflectionState(TypedDict):
    """
    Represents the state of the reflection process.

    Parameters
    ----------
    hypothesis_to_review: ParsedHypothesis
        The parsed hypothesis being evaluated
    passed_initial_filter: bool
        Whether the hypothesis passed the initial desk rejection filter
    initial_filter_assessment: str
        The assessment from the desk rejection filter
    _causal_reasoning: str
        The causal trace from hypothesis simulation (private)
    _refined_assumptions: str
        The refined assumptions output (private)
    _parsed_assumptions: dict[str, list[str]]
        Dictionary of parsed assumptions and sub-assumptions (private)
    _assumption_research_results: dict[str, str]
        Research results for each assumption (private)
    reviewed_hypothesis: Optional[ReviewedHypothesis]
        The final reviewed hypothesis with all verification results
    """

    hypothesis_to_review: ParsedHypothesis
    initial_filter_assessment: str
    passed_initial_filter: bool
    _causal_reasoning: str
    _refined_assumptions: str
    _parsed_assumptions: dict[str, list[str]]
    _assumption_research_results: dict[str, str]
    reviewed_hypothesis: Optional[ReviewedHypothesis]


def parse_assumption_decomposition(markdown_text: str) -> dict[str, list[str]]:
    """
    Parse the assumption decomposition markdown into a dictionary.

    Parameters
    ----------
    markdown_text : str
        The markdown output from assumption_decomposer prompt

    Returns
    -------
    dict[str, list[str]]
        Dictionary where keys are primary assumptions and values are lists of sub-assumptions
    """
    assumptions_dict = {}

    # Split by numbered assumption headers (1. **[Assumption]** or similar)
    # This regex looks for: number, period, space, **[text]**
    sections = re.split(r"\n\d+\.\s+\*\*([^*]+)\*\*", markdown_text)

    # The first section is usually intro text, skip it
    # Pairs are: (assumption_text, section_content)
    for i in range(1, len(sections), 2):
        if i + 1 < len(sections):
            assumption = sections[i].strip()
            content = sections[i + 1].strip()

            # Extract sub-assumptions from bullet points or dashes
            # Look for lines starting with - or * followed by sub-assumption text
            sub_assumptions = []
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    # Remove the bullet point marker and any sub-assumption prefix
                    sub_assumption = line[2:].strip()
                    # Remove "Sub-assumption X.Y:" prefix if present
                    sub_assumption = re.sub(
                        r"^Sub-assumption\s+\d+\.\d+:\s*", "", sub_assumption
                    )
                    if sub_assumption:
                        sub_assumptions.append(sub_assumption)

            if assumption and sub_assumptions:
                # Clean up the assumption text - remove brackets if present
                assumption = re.sub(r"^\[([^\]]+)\]$", r"\1", assumption)
                assumptions_dict[assumption] = sub_assumptions

    return assumptions_dict


async def desk_reject_node(state: ReflectionState, llm: BaseChatModel) -> ReflectionState:
    """
    Evaluates a hypothesis using the desk_reject.md prompt to determine if it
    should proceed for deeper analysis.

    Parameters
    ----------
    state: ReflectionState
        The current state of the reflection process
    llm: BaseChatModel
        The language model to use for evaluation

    Returns
    -------
    ReflectionState
        Updated state with the passed_initial_filter field updated
    """
    prompt = load_prompt(
        "desk_reject", hypothesis=state["hypothesis_to_review"].hypothesis
    )
    response = await llm.ainvoke(prompt)
    passed = "pass" in response.content.split("FINAL EVALUATION:")[-1].lower()

    return {
        "passed_initial_filter": passed,
        "initial_filter_assessment": response.content,
    }


async def hypothesis_simulation_node(
    state: ReflectionState, llm: BaseChatModel
) -> ReflectionState:
    """
    Performs step-by-step simulation of a hypothesis using the hypothesis_simulation.md prompt.

    Parameters
    ----------
    state: ReflectionState
        The current state of the reflection process
    llm: BaseChatModel
        The language model to use for simulation

    Returns
    -------
    ReflectionState
        Updated state with the _causal_reasoning field populated
    """
    prompt = load_prompt(
        "cause_and_effect", hypothesis=state["hypothesis_to_review"].hypothesis
    )
    response = await llm.ainvoke(prompt)

    return {"_causal_reasoning": response.content}


async def assumption_decomposer_node(
    state: ReflectionState, llm: BaseChatModel
) -> ReflectionState:
    """
    Decomposes a hypothesis into detailed assumptions and sub-assumptions.

    Parameters
    ----------
    state: ReflectionState
        The current state of the reflection process
    llm: BaseChatModel
        The language model to use for decomposition

    Returns
    -------
    ReflectionState
        Updated state with the _parsed_assumptions field populated
    """
    prompt = load_prompt(
        "assumption_decomposer",
        hypothesis=state["hypothesis_to_review"].hypothesis,
        assumptions="\n".join(state["hypothesis_to_review"].assumptions),
    )
    response = await llm.ainvoke(prompt)

    # Parse the assumptions into structured format
    parsed_assumptions = parse_assumption_decomposition(response.content)

    return {
        "_refined_assumptions": response.content,
        "_parsed_assumptions": parsed_assumptions,
    }


async def deep_verification_node(
    state: ReflectionState, llm: BaseChatModel
) -> ReflectionState:
    """
    Performs deep verification of a hypothesis using the deep_verification.md prompt.

    Parameters
    ----------
    state: ReflectionState
        The current state of the reflection process
    llm: BaseChatModel
        The language model to use for verification

    Returns
    -------
    ReflectionState
        Updated state with the reviewed_hypothesis populated
    """
    # Debug: Check what keys are actually in the state
    available_keys = list(state.keys())

    # More informative assertions
    assert (
        "_assumption_research_results" in state
    ), f"Missing '_assumption_research_results'. Available keys: {available_keys}"
    assert (
        "_causal_reasoning" in state
    ), f"Missing '_causal_reasoning'. Available keys: {available_keys}"

    # Combine assumption research results into a single string
    assumption_research = "\n\n".join(state["_assumption_research_results"].values())
    assumption_research = truncate_text(assumption_research, 500)

    prompt = load_prompt(
        "deep_verification",
        hypothesis=state["hypothesis_to_review"].hypothesis,
        reasoning=state["_causal_reasoning"],
        assumption_research=assumption_research,
    )
    response = await llm.ainvoke(prompt)

    # Create a ReviewedHypothesis instance
    reviewed_hypothesis = ReviewedHypothesis(
        uid=state["hypothesis_to_review"].uid,
        hypothesis=state["hypothesis_to_review"].hypothesis,
        predictions=state["hypothesis_to_review"].predictions,
        assumptions=state["hypothesis_to_review"].assumptions,
        parent_uid=state["hypothesis_to_review"].parent_uid,
        causal_reasoning=state["_causal_reasoning"],
        assumption_research_results=state["_assumption_research_results"],
        verification_result=response.content,
    )

    return {
        "reviewed_hypothesis": reviewed_hypothesis,
    }


def build_deep_verification_agent(
    llm: BaseChatModel,
    review_llm: BaseChatModel,
    parallel: bool = False,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    breakpoints: Optional[list[str]] = None,
):
    """
    Builds and configures a multinode LangGraph for comprehensive deep verification with research.

    The graph has four nodes:
    1. start_parallel: Initiates parallel processing
    2. enhanced_assumption_decomposer: Breaks down hypothesis into detailed assumptions and conducts research
    3. hypothesis_simulation: Performs causal reasoning and step-by-step simulation (runs in parallel)
    4. enhanced_deep_verification: Performs final verification using refined assumptions, research, and causal reasoning

    Parameters
    ----------
    llm: BaseChatModel
        The language model to use for simulation and assumption decomposition
    review_llm: BaseChatModel
        The language model to use for final review. Needs to support long context.
    parallel: bool, default=False
        Whether to run assumption research in parallel (True) or sequentially (False)
    checkpointer: Optional[BaseCheckpointSaver], default=None
        Checkpointer to save and restore graph state for debugging and resumption
    breakpoints: Optional[list[str]], default=None
        List of node names to set as breakpoints (execution will pause before these nodes)

    Returns
    -------
    StateGraph
        A compiled LangGraph for the research-enhanced deep verification agent
    """
    graph = StateGraph(ReflectionState)

    # Add a simple pass-through node to enable parallel execution after desk reject
    async def start_parallel(state: ReflectionState) -> ReflectionState:
        return state

    # Add a sync node that waits for both parallel branches to complete
    async def sync_parallel_results(state: ReflectionState) -> ReflectionState:
        # This node just passes through the state after both parallel branches complete
        return state

    # Add nodes
    graph.add_node("desk_reject", functools.partial(desk_reject_node, llm=llm))
    graph.add_node("start_parallel", start_parallel)
    graph.add_node("sync_parallel_results", sync_parallel_results)
    graph.add_node(
        "assumption_decomposer", functools.partial(assumption_decomposer_node, llm=llm)
    )

    # Always use sequential for rate limit safety
    graph.add_node(
        "assumption_researcher",
        _sequential_assumption_research_node,
    )

    graph.add_node(
        "hypothesis_simulation", functools.partial(hypothesis_simulation_node, llm=llm)
    )
    graph.add_node(
        "deep_verification", functools.partial(deep_verification_node, llm=review_llm)
    )

    # Set entry point to desk reject
    graph.set_entry_point("desk_reject")

    # Conditional routing after desk reject
    def should_continue(state: ReflectionState) -> str:
        if state["passed_initial_filter"]:
            return "start_parallel"
        else:
            return END

    graph.add_conditional_edges("desk_reject", should_continue)

    # Create parallel branches from start_parallel
    graph.add_edge("start_parallel", "assumption_decomposer")
    graph.add_edge("start_parallel", "hypothesis_simulation")
    graph.add_edge("assumption_decomposer", "assumption_researcher")

    # Both parallel nodes feed into sync node, then to verification
    graph.add_edge("assumption_researcher", "sync_parallel_results")
    graph.add_edge("hypothesis_simulation", "sync_parallel_results")
    graph.add_edge("sync_parallel_results", "deep_verification")

    # Final verification connects to end
    graph.add_edge("deep_verification", END)

    # Compile with optional checkpointer and breakpoints
    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if breakpoints is not None:
        compile_kwargs["interrupt_before"] = breakpoints

    return graph.compile(**compile_kwargs)


async def _sequential_assumption_research_node(
    state: ReflectionState,
) -> ReflectionState:
    """
    Node that conducts sequential research for all assumptions and sub-assumptions.
    """
    from coscientist.retrieval.retrieval_crag import corrective_rag_search
    
    parsed_assumptions = state["_parsed_assumptions"]
    assumption_research_results = {}

    # Limit to top 3 assumptions to save API calls
    assumptions_to_research = list(parsed_assumptions.items())[:settings.MAX_SUBTOPICS]

    # Process each assumption sequentially
    for assumption, sub_assumptions in assumptions_to_research:
        query = f"Scientific evidence for assumption: {assumption}"
        if sub_assumptions:
            query += " Context: " + " ".join(sub_assumptions[:2])
            
        result = await corrective_rag_search(query, max_iterations=1, context=assumption)
        assumption_research_results[assumption] = result
        
        # Rate limit delay
        await asyncio.sleep(60 / settings.REQUESTS_PER_MINUTE)

    return {"_assumption_research_results": assumption_research_results}
