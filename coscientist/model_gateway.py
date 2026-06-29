import os
import asyncio
import logging
from typing import Any, Union
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from .config import settings

logger = logging.getLogger(__name__)

class ModelGateway:
    def __init__(self):
        # Explicit models for routing
        self.gemini_model = self._init_model("gemini-3.1-pro-preview", settings.MAX_STRONG_TOKENS)
        self.groq_model = self._init_model("llama-3.3-70b-versatile", settings.MAX_FAST_TOKENS)

    def _init_model(self, model_name: str, max_tokens: int) -> BaseChatModel:
        if "gemini" in model_name.lower():
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                max_output_tokens=max_tokens,
                temperature=0.7,
            )
        elif "llama" in model_name.lower() or "mixtral" in model_name.lower() or "gemma" in model_name.lower():
            try:
                from langchain_groq import ChatGroq
                return ChatGroq(
                    model=model_name,
                    max_retries=settings.RETRY_MAX_ATTEMPTS,
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
            except ImportError:
                logger.error("langchain-groq not installed but groq model requested")
                raise
        elif "gpt" in model_name.lower() or "o1" in model_name.lower() or "o3" in model_name.lower():
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                max_retries=settings.RETRY_MAX_ATTEMPTS,
                max_tokens=max_tokens,
                temperature=0.7,
            )
        elif "claude" in model_name.lower():
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_name,
                max_retries=settings.RETRY_MAX_ATTEMPTS,
                max_tokens=max_tokens,
                temperature=0.7,
            )
        else:
            raise ValueError(f"Unsupported model: {model_name}")

    def get_gemini_llm(self) -> BaseChatModel:
        return self.gemini_model
        
    def get_groq_llm(self) -> BaseChatModel:
        return self.groq_model
        
    # Legacy aliases
    def get_strong_llm(self) -> BaseChatModel:
        return self.gemini_model
        
    def get_fast_llm(self) -> BaseChatModel:
        return self.groq_model

gateway = ModelGateway()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True
)
async def safe_ainvoke(llm: BaseChatModel, prompt: Union[str, list[BaseMessage]]) -> BaseMessage:
    """Safely invoke an LLM asynchronously with exponential backoff."""
    # Small delay to spread out requests
    await asyncio.sleep(2.0)
    try:
        response = await llm.ainvoke(prompt)
        return response
    except Exception as e:
        logger.warning(f"Error invoking LLM: {e}. Retrying...")
        raise

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True
)
def safe_invoke(llm: BaseChatModel, prompt: Union[str, list[BaseMessage]]) -> BaseMessage:
    """Safely invoke an LLM synchronously with exponential backoff."""
    import time
    time.sleep(2.0)
    try:
        response = llm.invoke(prompt)
        return response
    except Exception as e:
        logger.warning(f"Error invoking LLM: {e}. Retrying...")
        raise
