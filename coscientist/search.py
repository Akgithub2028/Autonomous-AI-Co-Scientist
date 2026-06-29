import asyncio
import logging
from typing import List, Dict, Any
from tavily import TavilyClient

from .config import settings
from .cache import global_cache
from .model_gateway import gateway, safe_ainvoke

logger = logging.getLogger(__name__)

# Initialize Tavily client
tavily_client = None
if settings.TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Tavily client: {e}")

async def search_and_summarize(query: str, max_results: int = 3, topic_context: str = "") -> str:
    """Search Tavily and summarize the results."""
    if not tavily_client:
        return "Search is unavailable due to missing API key."

    # Check cache first
    cache_key = f"search_{query}_{max_results}_{topic_context}"
    cached_result = global_cache.get("search", cache_key)
    if cached_result:
        return cached_result

    try:
        # Run Tavily search in thread pool since it's synchronous
        # Ensure query is under 400 characters for Tavily
        tavily_query = query[:400]
        loop = asyncio.get_event_loop()
        search_response = await loop.run_in_executor(
            None, 
            lambda: tavily_client.search(query=tavily_query, search_depth="basic", max_results=max_results)
        )
        
        results = search_response.get("results", [])
        if not results:
            return "No relevant information found."
            
        # Format results for LLM
        formatted_results = "\n\n".join([
            f"Source: {r.get('url', 'Unknown')}\nTitle: {r.get('title', 'Unknown')}\nContent: {r.get('content', '')}"
            for r in results
        ])
        
        # Summarize with fast LLM
        llm = gateway.get_groq_llm()
        prompt = (
            f"Synthesize the following search results to answer the query: '{query}'\n"
            f"Context: {topic_context}\n\n"
            f"Search Results:\n{formatted_results}\n\n"
            "Provide a concise, factual summary of the key findings. Cite sources by URL where appropriate."
        )
        
        response = await safe_ainvoke(llm, prompt)
        summary = response.content
        
        # Save to cache
        global_cache.set("search", cache_key, summary)
        
        return summary
    except Exception as e:
        logger.error(f"Search failed for query '{query}': {e}")
        return f"Error conducting search: {str(e)}"

async def research_subtopic(subtopic: str, goal: str) -> str:
    """Replacement for GPTResearcher subtopic reports."""
    # We use search_and_summarize to do a deep search
    summary = await search_and_summarize(
        query=f"Latest scientific research on {subtopic} in context of {goal}",
        max_results=5,
        topic_context=goal
    )
    return summary

async def research_assumption(assumption: str, sub_assumptions: list[str]) -> str:
    """Replacement for GPTResearcher assumption research."""
    query = assumption
    if sub_assumptions:
        query += " " + " ".join(sub_assumptions[:2])
        
    summary = await search_and_summarize(
        query=f"Scientific evidence validating or refuting this assumption: {query}",
        max_results=3
    )
    return summary
