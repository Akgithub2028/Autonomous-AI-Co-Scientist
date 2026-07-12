import os
import asyncio
import logging
import time
from typing import Any, Union, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from coscientist.configs.config import settings

logger = logging.getLogger(__name__)

class MetricsTracker:
    def __init__(self):
        self.total_tokens: Dict[str, int] = {"gemini": 0, "fast": 0}
        self.api_calls: Dict[str, int] = {"gemini": 0, "fast": 0}
        self.total_latency: float = 0.0
        self.agent_tokens: Dict[str, int] = {
            "generation": 0,
            "evolution": 0,
            "reflection": 0,
            "supervisor": 0,
            "ranking": 0,
            "meta_review": 0,
            "other": 0
        }
        self.current_agent_role: str = "other"
        self.rate_limit_events: int = 0

    def reset(self):
        self.total_tokens = {"gemini": 0, "fast": 0}
        self.api_calls = {"gemini": 0, "fast": 0}
        self.total_latency = 0.0
        self.agent_tokens = {k: 0 for k in self.agent_tokens.keys()}
        self.current_agent_role = "other"
        self.rate_limit_events = 0

metrics_tracker = MetricsTracker()

class ModelGateway:
    def __init__(self):
        # Explicit models for routing based on the new architecture
        self.gemini_model = self._init_model(settings.STRONG_MODEL, settings.MAX_STRONG_TOKENS)
        self.fast_model = self._init_model(settings.FAST_MODEL, settings.MAX_FAST_TOKENS)

    def _init_model(self, model_name: str, max_tokens: int) -> BaseChatModel:
        # Route ALL traffic through Puter's OpenAI-compatible endpoint
        from langchain_openai import ChatOpenAI
        
        # Puter handles translation to Google/OpenAI natively
        return ChatOpenAI(
            model=model_name,
            api_key=settings.PUTER_API_KEY,
            base_url="https://api.puter.com/puterai/openai/v1",
            max_retries=settings.RETRY_MAX_ATTEMPTS,
            max_tokens=max_tokens,
            temperature=0.7,
        )

    def get_gemini_llm(self) -> BaseChatModel:
        return self.gemini_model
        
    def get_groq_llm(self) -> BaseChatModel:
        # Legacy fallback, now returns the fast model (Puter/GPT-4o-mini)
        return self.fast_model
        
    def get_fast_llm(self) -> BaseChatModel:
        return self.fast_model

    def get_strong_llm(self) -> BaseChatModel:
        return self.gemini_model

gateway = ModelGateway()

def _update_metrics(llm: BaseChatModel, response: BaseMessage, elapsed: float):
    metrics_tracker.total_latency += elapsed
    model_name = getattr(llm, "model_name", getattr(llm, "model", "")).lower()
    model_type = "gemini" if "gemini" in model_name else "fast"
    
    metrics_tracker.api_calls[model_type] += 1
    
    if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
        token_usage = response.response_metadata["token_usage"]
        # Different models structure token usage differently, try to get total
        total_tokens = token_usage.get("total_tokens", 
                        token_usage.get("totalTokens", 
                        token_usage.get("total_tokens", 0)))
        metrics_tracker.total_tokens[model_type] += total_tokens
        
        # Track per-agent role
        role = metrics_tracker.current_agent_role
        if role in metrics_tracker.agent_tokens:
            metrics_tracker.agent_tokens[role] += total_tokens
        else:
            metrics_tracker.agent_tokens["other"] += total_tokens

def _record_retry(retry_state):
    """Callback for tenacity to log rate limits / retries."""
    if retry_state.attempt_number > 1:
        metrics_tracker.rate_limit_events += 1
        logger.warning(f"Rate limit or API error encountered. Retry attempt: {retry_state.attempt_number}")

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True,
    after=_record_retry
)
async def safe_ainvoke(llm: BaseChatModel, prompt: Union[str, list[BaseMessage]]) -> BaseMessage:
    """Safely invoke an LLM asynchronously with exponential backoff and metrics tracking."""
    await asyncio.sleep(2.0)
    start_time = time.time()
    try:
        response = await llm.ainvoke(prompt)
        elapsed = time.time() - start_time
        _update_metrics(llm, response, elapsed)
        return response
    except Exception as e:
        logger.warning(f"Error invoking LLM: {e}. Retrying...")
        raise

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True,
    after=_record_retry
)
def safe_invoke(llm: BaseChatModel, prompt: Union[str, list[BaseMessage]]) -> BaseMessage:
    """Safely invoke an LLM synchronously with exponential backoff and metrics tracking."""
    time.sleep(2.0)
    start_time = time.time()
    try:
        response = llm.invoke(prompt)
        elapsed = time.time() - start_time
        _update_metrics(llm, response, elapsed)
        return response
    except Exception as e:
        logger.warning(f"Error invoking LLM: {e}. Retrying...")
        raise
