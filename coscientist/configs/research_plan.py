"""
Generates a research plan from the user's query.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import logging
from coscientist.services.model_gateway import gateway, safe_invoke

logger = logging.getLogger(__name__)

class ResearchPlanConfig(BaseModel):
    goal: str = Field(..., description="The main research goal")
    preferences: List[str] = Field(default_factory=list, description="User preferences like novelty, safety")
    constraints: List[str] = Field(default_factory=list, description="Constraints like FDA approved only")
    evaluation_criteria: List[str] = Field(default_factory=list, description="Criteria for evaluation")
    
    # Compute weights / budget allocation
    generation_budget: int = Field(default=20000, description="Token budget for generation")
    evolution_budget: int = Field(default=10000, description="Token budget for evolution")
    reflection_budget: int = Field(default=20000, description="Token budget for reflection")

def parse_goal(goal_data: str | Dict[str, Any]) -> ResearchPlanConfig:
    """
    Parses a raw goal string or JSON dict into a ResearchPlanConfig using the fast LLM.
    """
    llm = gateway.get_fast_llm()
    prompt = f"""
Parse the following research goal into a structured JSON configuration.
Extract the main goal, preferences, constraints, and evaluation criteria.
Also allocate token budgets for 'generation_budget', 'evolution_budget', and 'reflection_budget' 
totaling exactly 50,000 tokens based on the implied difficulty of the task (e.g. if many constraints, allocate more to generation/reflection).

Input Goal Data:
{goal_data}

Return ONLY valid JSON matching this schema:
{{
  "goal": "string",
  "preferences": ["string"],
  "constraints": ["string"],
  "evaluation_criteria": ["string"],
  "generation_budget": int,
  "evolution_budget": int,
  "reflection_budget": int
}}
"""
    try:
        response = safe_invoke(llm, prompt).content
        # Clean markdown code block if present
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
            
        data = json.loads(response.strip())
        return ResearchPlanConfig(**data)
    except Exception as e:
        logger.error(f"Failed to parse goal: {e}. Falling back to default.")
        goal_text = goal_data if isinstance(goal_data, str) else str(goal_data.get('goal', goal_data))
        return ResearchPlanConfig(goal=goal_text)
