import asyncio
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
from typing import List, Dict, Any
from tavily import TavilyClient
from tenacity import retry, stop_after_attempt, wait_exponential

from coscientist.configs.config import settings
from coscientist.services.cache import global_cache
from coscientist.services.model_gateway import gateway, safe_ainvoke

logger = logging.getLogger(__name__)

# Initialize Tavily client
tavily_client = None
if settings.TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Tavily client: {e}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_arxiv_sync(query: str, max_results: int = 3) -> list:
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={max_results}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        results = []
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
            summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
            link = entry.find('atom:id', ns).text.strip()
            results.append({"title": title, "content": summary, "url": link, "source": "arXiv"})
        return results
    except Exception as e:
        logger.error(f"arXiv search failed: {e}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_pubmed_sync(query: str, max_results: int = 3) -> list:
    try:
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded_query}&retmax={max_results}&retmode=json"
        
        req = urllib.request.Request(search_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
            
        ids = ",".join(id_list)
        summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={ids}&retmode=json"
        req = urllib.request.Request(summary_url)
        with urllib.request.urlopen(req, timeout=10) as response:
            summary_data = json.loads(response.read())
            
        results = []
        for uid in id_list:
            doc_sum = summary_data.get("result", {}).get(uid, {})
            title = doc_sum.get("title", "Unknown Title")
            url = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
            content = f"Authors: {', '.join([a.get('name', '') for a in doc_sum.get('authors', [])])}. Source: {doc_sum.get('source', '')}."
            results.append({"title": title, "content": content, "url": url, "source": "PubMed"})
            
        return results
    except Exception as e:
        logger.error(f"PubMed search failed: {e}")
        return []

async def search_and_summarize(query: str, max_results: int = 3, topic_context: str = "") -> str:
    """Search Tavily, arXiv, and PubMed and summarize the results."""
    # Check cache first
    cache_key = f"search_{query}_{max_results}_{topic_context}"
    cached_result = global_cache.get("search", cache_key)
    if cached_result:
        return cached_result

    try:
        tavily_query = query[:400]
        loop = asyncio.get_event_loop()
        
        tavily_task = None
        if tavily_client:
            tavily_task = loop.run_in_executor(
                None, 
                lambda: tavily_client.search(query=tavily_query, search_depth="basic", max_results=max_results)
            )
            
        arxiv_task = loop.run_in_executor(None, lambda: search_arxiv_sync(query, max_results))
        pubmed_task = loop.run_in_executor(None, lambda: search_pubmed_sync(query, max_results))
        
        tasks_to_gather = []
        if tavily_task:
            tasks_to_gather.append(tavily_task)
        tasks_to_gather.extend([arxiv_task, pubmed_task])
        
        results = await asyncio.gather(*tasks_to_gather, return_exceptions=True)
        
        idx = 0
        tavily_res = {}
        if tavily_task:
            tavily_res = results[idx] if not isinstance(results[idx], Exception) and results[idx] else {}
            idx += 1
            
        arxiv_res = results[idx] if not isinstance(results[idx], Exception) else []
        idx += 1
        pubmed_res = results[idx] if not isinstance(results[idx], Exception) else []
        
        all_results = tavily_res.get("results", []) + arxiv_res + pubmed_res
        
        if not all_results:
            return "No relevant information found."
            
        # Format results for LLM
        formatted_results = "\n\n".join([
            f"Source: [{r.get('source', 'Tavily')}] {r.get('url', 'Unknown')}\nTitle: {r.get('title', 'Unknown')}\nContent: {r.get('content', '')}"
            for r in all_results
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
