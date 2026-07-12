import os
import logging
import numpy as np
from typing import Dict, Any, List

import matplotlib.pyplot as plt

from coscientist.agents.ranking_agent import EloTournament
from coscientist.models.custom_types import ReviewedHypothesis
from langchain_huggingface import HuggingFaceEmbeddings
from coscientist.configs.config import settings
from coscientist.services.model_gateway import gateway, safe_invoke, metrics_tracker

logger = logging.getLogger(__name__)

class Evaluator:
    """
    Evaluates the performance of the AI Co-Scientist.
    Tracks diversity of exploration, ELO rating trajectory, and basic accuracy.
    """
    def __init__(self):
        self.metrics = []
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )

    def calculate_diversity(self, hypotheses: List[ReviewedHypothesis]) -> float:
        """
        Calculates diversity using the average pairwise cosine distance of embeddings.
        """
        if len(hypotheses) < 2:
            return 0.0
            
        texts = [h.hypothesis for h in hypotheses]
        vectors = self.embeddings.embed_documents(texts)
        
        # Calculate pairwise cosine similarity
        vectors_np = np.array(vectors)
        # Normalize vectors
        norms = np.linalg.norm(vectors_np, axis=1, keepdims=True)
        normalized = vectors_np / norms
        
        similarities = np.dot(normalized, normalized.T)
        
        # Diversity = 1 - average similarity (off-diagonal)
        n = len(hypotheses)
        sum_sim = np.sum(similarities) - n
        avg_sim = sum_sim / (n * (n - 1))
        
        return 1.0 - avg_sim

    def calculate_human_proxies(self, top_hypothesis: str) -> Dict[str, float]:
        """Uses LLM-as-a-judge to estimate Novelty, Impact, and Preference Rank."""
        prompt = f"""Evaluate the following scientific hypothesis for Novelty, Impact, and Preference.
Hypothesis:
{top_hypothesis}

Provide a score from 1.0 to 5.0 for Novelty (how original and unprecedented is this) and Impact (how useful is this).
Also provide a Preference Rank from 1.0 (best) to 5.0 (worst) comparing it to typical baselines.
Format your response exactly as:
Novelty: [score]
Impact: [score]
Preference Rank: [score]
"""
        try:
            llm = gateway.get_fast_llm()
            response = safe_invoke(llm, prompt).content
            
            novelty = 3.0
            impact = 3.0
            preference_rank = 2.0
            for line in response.split('\n'):
                if "Novelty:" in line:
                    novelty = float(line.split(":")[1].strip())
                elif "Impact:" in line:
                    impact = float(line.split(":")[1].strip())
                elif "Preference Rank:" in line:
                    preference_rank = float(line.split(":")[1].strip())
            return {"novelty": novelty, "impact": impact, "preference_rank": preference_rank}
        except Exception as e:
            logger.error(f"Error calculating human proxies: {e}")
            return {"novelty": 3.0, "impact": 3.0, "preference_rank": 2.0}

    def plot_elo_progression(self, trajectory: Dict[str, list], goal_name: str) -> None:
        """Plots the Elo progression over tournament rounds."""
        try:
            max_elos = trajectory.get("max_elo_rating", [])
            median_elos = trajectory.get("median_elo_rating", [])
            if not max_elos:
                return
                
            rounds = range(1, len(max_elos) + 1)
            plt.figure(figsize=(10, 6))
            plt.plot(rounds, max_elos, label='Max Elo (Top Hypothesis)', marker='o', color='blue')
            if median_elos:
                plt.plot(rounds, median_elos, label='Median Elo', marker='s', color='orange', linestyle='--')
            
            plt.title(f"Elo Progression: {goal_name}")
            plt.xlabel("Tournament Round")
            plt.ylabel("Elo Rating")
            plt.legend()
            plt.grid(True)
            
            os.makedirs("output", exist_ok=True)
            filename = f"output/elo_progression_{goal_name}.png".replace(" ", "_").lower()
            plt.savefig(filename)
            plt.close()
            logger.info(f"Saved Elo progression plot to {filename}")
        except Exception as e:
            logger.error(f"Failed to plot Elo progression: {e}")

    def evaluate_tournament(self, tournament: EloTournament, goal_name: str = "Goal") -> Dict[str, Any]:
        """
        Extracts key metrics from an Elo tournament.
        """
        trajectory = tournament.summarize_tournament_trajectory()
        self.plot_elo_progression(trajectory, goal_name)
        
        hypotheses = list(tournament.hypotheses.values())
        diversity_score = self.calculate_diversity(hypotheses)
        
        sorted_hypos = tournament.get_sorted_hypotheses()
        
        final_max_elo = trajectory.get("max_elo_rating", [1200])[-1] if trajectory.get("max_elo_rating") else 1200
        initial_max_elo = trajectory.get("max_elo_rating", [1200])[0] if trajectory.get("max_elo_rating") else 1200
        elo_improvement = final_max_elo - initial_max_elo
        
        top10_elos = [rating for _, rating in sorted_hypos[:10]]
        final_top10_elo = np.mean(top10_elos) if top10_elos else 1200
        
        top_hypo_text = hypotheses[0].hypothesis if hypotheses else ""
        if sorted_hypos:
            top_id = sorted_hypos[0][0]
            top_hypo_text = tournament.hypotheses[top_id].hypothesis
            
        proxies = self.calculate_human_proxies(top_hypo_text)
        
        # Calculate Cost
        # Pricing assumption: 
        # Gemini 1.5 Flash: $0.075/1M input, $0.30/1M output (average to ~$0.18/1M)
        # GPT-4o mini: $0.150/1M input, $0.600/1M output (average to ~$0.37/1M)
        gemini_tokens = metrics_tracker.total_tokens["gemini"]
        fast_tokens = metrics_tracker.total_tokens["fast"]
        cost = (gemini_tokens / 1_000_000 * 0.18) + (fast_tokens / 1_000_000 * 0.37)
        
        metrics = {
            "goal_name": goal_name,
            "final_max_elo": final_max_elo,
            "final_top10_elo": final_top10_elo,
            "elo_improvement": elo_improvement,
            "novelty": proxies["novelty"],
            "impact": proxies["impact"],
            "preference_rank": proxies["preference_rank"],
            "gpqa_correlation": "N/A (Optional)",
            "diversity_score": diversity_score,
            "latency": metrics_tracker.total_latency,
            "gemini_tokens": gemini_tokens,
            "fast_tokens": fast_tokens,
            "cost": cost,
            "gemini_calls": metrics_tracker.api_calls["gemini"],
            "fast_calls": metrics_tracker.api_calls["fast"],
            "rate_limit_events": metrics_tracker.rate_limit_events,
        }
        
        self.metrics.append(metrics)
        return metrics

    def generate_summary_table(self) -> str:
        if not self.metrics:
            return "No metrics collected."
            
        markdown = "| Metric | Definition |"
        for res in self.metrics:
            markdown += f" {res['goal_name']} |"
        markdown += "\n|---|---|"
        for _ in self.metrics:
            markdown += "---|"
        markdown += "\n"
        
        metrics_to_plot = [
            ("Top-1 Elo (end)", "Elo of best hypothesis after final round", "final_max_elo"),
            ("Top-10 Elo avg (end)", "Avg Elo of top 10 hypotheses", "final_top10_elo"),
            ("Elo Improvement", "Δ Elo of top hypothesis (start→end)", "elo_improvement"),
            ("Novelty (avg expert 1-5)", "(Simulated) average novelty rating by judge", "novelty"),
            ("Impact (avg expert 1-5)", "(Simulated) average impact rating by judge", "impact"),
            ("Preference Rank", "(Simulated) co-scientist rank among baselines", "preference_rank"),
            ("GPQA Correlation", "Alignment with GPQA QA accuracy", "gpqa_correlation"),
            ("Diversity (embedding dist)", "Mean pairwise cosine distance among top hypotheses", "diversity_score"),
            ("Latency (total, sec)", "Total time to complete goal (end-to-end)", "latency"),
            ("Tokens (Gemini)", "Tokens used on strong model", "gemini_tokens"),
            ("Tokens (GPT-4o mini)", "Tokens used on fast model", "fast_tokens"),
            ("Total Estimated Cost ($)", "Approximate API cost based on token usage", "cost"),
            ("LLM Calls (Gemini)", "Number of strong model calls", "gemini_calls"),
            ("LLM Calls (GPT-4o mini)", "Number of fast model calls", "fast_calls"),
            ("Rate-limit Events", "Number of API retries due to limits", "rate_limit_events"),
        ]
        
        for name, definition, key in metrics_to_plot:
            markdown += f"| *{name}* | {definition} |"
            for res in self.metrics:
                val = res.get(key, "N/A")
                if isinstance(val, float):
                    markdown += f" {val:.2f} |"
                else:
                    markdown += f" {val} |"
            markdown += "\n"
            
        return markdown
