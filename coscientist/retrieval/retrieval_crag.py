import logging
import asyncio
from typing import List, Dict, Any, Tuple

from coscientist.services.model_gateway import gateway, safe_ainvoke
from coscientist.retrieval.search import tavily_client, search_arxiv_sync, search_pubmed_sync

logger = logging.getLogger(__name__)

async def rewrite_query(original_query: str, fast_llm, context: str = "") -> str:
    """Uses the fast LLM (GPT-4o mini) to rewrite a query for better retrieval."""
    prompt = (
        f"You are an expert scientific researcher. Rewrite the following scientific question or topic "
        f"to retrieve the most relevant literature or data from an academic database or web search.\n"
        f"Context: {context}\n"
        f"Original Query: '{original_query}'\n\n"
        f"Return ONLY the rewritten search query text, without quotes or explanation."
    )
    response = await safe_ainvoke(fast_llm, prompt)
    rewritten = response.content.strip().strip("'\"")
    return rewritten

async def evaluate_retrieval(query: str, results_text: str, fast_llm) -> Tuple[bool, str]:
    """Evaluates if the retrieved results sufficiently address the query."""
    prompt = (
        f"You are evaluating search results for the query: '{query}'.\n"
        f"Search Results:\n{results_text}\n\n"
        f"Do these results provide sufficient scientific evidence to answer the query or ground the hypothesis? "
        f"Respond with exactly 'YES' or 'NO' on the first line, followed by a brief reason."
    )
    response = await safe_ainvoke(fast_llm, prompt)
    content = response.content.strip().upper()
    is_sufficient = content.startswith("YES")
    return is_sufficient, content

async def corrective_rag_search(query: str, max_iterations: int = 2, context: str = "", max_results: int = 3) -> str:
    """
    Implements the Corrective RAG (CRAG) pipeline.
    1. Rewrites query.
    2. Searches.
    3. Evaluates if results are good enough.
    4. If not, rewrites again (up to max_iterations).
    5. Returns synthesized output using the strong LLM (Gemini 3.5 Flash).
    """
    if not tavily_client:
        return "Search is unavailable due to missing API key."

    fast_llm = gateway.get_fast_llm()
    strong_llm = gateway.get_strong_llm()
    
    current_query = query
    best_results_text = ""
    
    for iteration in range(max_iterations):
        if iteration > 0:
            current_query = await rewrite_query(current_query, fast_llm, context)
            
        try:
            tavily_query = current_query[:400]
            loop = asyncio.get_event_loop()
            
            tavily_task = asyncio.sleep(0)
            if tavily_client:
                tavily_task = loop.run_in_executor(
                    None, 
                    lambda: tavily_client.search(query=tavily_query, search_depth="advanced", max_results=max_results)
                )
                
            arxiv_task = loop.run_in_executor(None, lambda: search_arxiv_sync(current_query, max_results))
            pubmed_task = loop.run_in_executor(None, lambda: search_pubmed_sync(current_query, max_results))
            
            results = await asyncio.gather(
                tavily_task if tavily_client else asyncio.sleep(0),
                arxiv_task,
                pubmed_task,
                return_exceptions=True
            )
            
            tavily_res = results[0] if tavily_client and not isinstance(results[0], Exception) and results[0] else {}
            arxiv_res = results[1] if not isinstance(results[1], Exception) else []
            pubmed_res = results[2] if not isinstance(results[2], Exception) else []
            
            all_results = tavily_res.get("results", []) + arxiv_res + pubmed_res
            
            if not all_results:
                continue
                
            formatted_results = "\n\n".join([
                f"Source: [{r.get('source', 'Tavily')}] {r.get('url', 'Unknown')}\nTitle: {r.get('title', 'Unknown')}\nContent: {r.get('content', '')}"
                for r in all_results
            ])
            
            best_results_text = formatted_results
            
            # Evaluate
            is_sufficient, _ = await evaluate_retrieval(query, formatted_results, fast_llm)
            if is_sufficient:
                break
                
        except Exception as e:
            logger.error(f"CRAG search iteration failed: {e}")
            
    if not best_results_text:
        return "No relevant information found after search iterations."

    # Final RAG generation using the Strong LLM (Gemini)
    synthesis_prompt = (
        f"Synthesize the following scientific search results to answer the query: '{query}'\n"
        f"Context: {context}\n\n"
        f"Search Results:\n{best_results_text}\n\n"
        "Provide a comprehensive, factual summary of the key findings. Cite sources by URL where appropriate."
    )
    
    response = await safe_ainvoke(strong_llm, synthesis_prompt)
    return response.content
