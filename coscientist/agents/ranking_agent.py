"""
Ranking agent
-------------
- Runs tournaments and assigns ELO ratings to hypotheses

More details:
- Newly added hypotheses are added to the tournament with
an ELO rating of 1200.
- Top and bottom ranked hypotheses are evaluated differently.
Two top-ranked hypotheses are paired against each other and
there is a multi-turn scientific debate. Lower ranked hypotheses
are evaluated with a single turn debate. Final output is the number
of the winning hypothesis.
- Based on the Proximity agents graph, similar hypotheses are ranked
against each other. New and top-ranked hypotheses are prioritized.

TODO: Add a queue of hypotheses ordered by rank this will limit the number of hypotheses
that need to be evaluated by dropping the lowest ranked hypotheses that drop outside of the
queue.
"""

import itertools  # Add itertools for combinations
import statistics
import random
import time
from typing import Optional  # Add Optional

from langchain_core.language_models.chat_models import BaseChatModel

from coscientist.services import multiturn
from coscientist.services.common import load_prompt
from coscientist.models.custom_types import RankingMatchResult, ReviewedHypothesis
from coscientist.services.cache import global_cache
from coscientist.services.model_gateway import safe_invoke
from coscientist.configs.config import settings

# Constants
DEFAULT_ELO = 1200
K_FACTOR = 32


class DebateState(multiturn.MultiTurnState):
    goal: str
    hypothesis_1: str
    hypothesis_2: str
    review_1: str
    review_2: str


import asyncio

def _build_debate_agent(
    agent_names: list[str],
    llms: dict[str, BaseChatModel],
    max_turns: int = 10,
) -> DebateState:
    """Build collaborative generation agent."""

    # Create agent node functions
    agent_node_fns = {}
    for agent_name in agent_names:
        agent_node_fns[agent_name] = multiturn.create_agent_node_fn(
            agent_name=agent_name,
            llm=llms[agent_name],
            prompt_name="simulated_debate",
            prompt_keys_from_state=[
                "goal",
                "hypothesis_1",
                "hypothesis_2",
                "review_1",
                "review_2",
            ],
        )

    # Create moderator and post-processor
    moderator_fn = multiturn.create_moderator_node_fn(
        agent_names, lambda msg: "WINNER:" in msg, max_turns
    )

    return multiturn.build_multi_turn_agent(DebateState, agent_node_fns, moderator_fn)


def calculate_expected_score(rating1: float, rating2: float) -> tuple[float, float]:
    """Calculates the expected scores for two players based on their ELO ratings."""
    expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    expected2 = 1 / (1 + 10 ** ((rating1 - rating2) / 400))
    return expected1, expected2


def update_elo(rating1: float, rating2: float, winner: int) -> tuple[float, float]:
    """
    Updates the ELO ratings of two players based on the match outcome.

    Parameters
    ----------
    rating1 : float
        ELO rating of hypothesis 1.
    rating2 : float
        ELO rating of hypothesis 2.
    winner : int
        1 if hypothesis 1 won, 2 if hypothesis 2 won.

    Returns
    -------
    tuple of float
        A tuple containing the updated ELO ratings (new_rating1, new_rating2).
    """
    expected1, expected2 = calculate_expected_score(rating1, rating2)

    if winner == 1:
        score1, score2 = 1, 0
    elif winner == 2:
        score1, score2 = 0, 1
    else:
        raise ValueError("Winner must be 1 or 2")  # Assuming no draws for now

    new_rating1 = rating1 + K_FACTOR * (score1 - expected1)
    new_rating2 = rating2 + K_FACTOR * (score2 - expected2)

    return new_rating1, new_rating2


class EloTournament:
    """Manages a two-stage ELO ranking tournament for hypotheses."""

    def __init__(self, goal: str):
        self.goal = goal
        self.hypotheses: dict[str, ReviewedHypothesis] = {}  # id -> Hypothesis object
        self.ratings: dict[str, float] = {}  # id -> ELO rating
        self.match_history: dict[tuple[int, int, int], RankingMatchResult] = {}

        self._past_tournament_ratings: list[list[float]] = []

    def add_hypothesis(
        self, hypothesis: ReviewedHypothesis, initial_rating: float = DEFAULT_ELO
    ):
        """Adds a new hypothesis to the tournament."""
        if hypothesis.uid not in self.hypotheses:
            self.hypotheses[hypothesis.uid] = hypothesis
            self.ratings[hypothesis.uid] = initial_rating
        else:
            raise ValueError(f"Hypothesis {hypothesis.uid} already exists.")

    def get_sorted_hypotheses(self) -> list[tuple[str, float]]:
        """Returns hypotheses sorted by ELO rating (descending)."""
        return sorted(self.ratings.items(), key=lambda item: item[1], reverse=True)

    def _parse_winner(self, response_text: str) -> int:
        winner_str = response_text.split("WINNER:")[-1].strip()
        if "1" in winner_str and "2" not in winner_str:
            return 1
        elif "2" in winner_str and "1" not in winner_str:
            return 2
        else:
            return 1

    def _determine_winner(
        self,
        hypo1: ReviewedHypothesis,
        hypo2: ReviewedHypothesis,
        prompt_name: str,
        llm: BaseChatModel,
    ) -> tuple[int, str]:
        """Synchronous version"""
        cache_key = f"{hypo1.uid}_{hypo2.uid}_{prompt_name}"
        cached_result = global_cache.get("match", cache_key)
        if cached_result:
            return cached_result["winner"], cached_result["debate"]

        prompt_input = {
            "goal": self.goal,
            "hypothesis_1": hypo1.hypothesis,
            "hypothesis_2": hypo2.hypothesis,
            "review_1": hypo1.verification_result,
            "review_2": hypo2.verification_result,
        }

        formatted_prompt = load_prompt("tournament", **prompt_input)
        response_text = safe_invoke(llm, formatted_prompt).content
        winner = self._parse_winner(response_text)

        global_cache.set("match", cache_key, {"winner": winner, "debate": response_text})
        return winner, response_text

    async def _determine_winner_async(
        self,
        hypo1: ReviewedHypothesis,
        hypo2: ReviewedHypothesis,
        prompt_name: str,
        llm: BaseChatModel,
    ) -> tuple[int, str]:
        """Asynchronous version"""
        cache_key = f"{hypo1.uid}_{hypo2.uid}_{prompt_name}"
        cached_result = global_cache.get("match", cache_key)
        if cached_result:
            return cached_result["winner"], cached_result["debate"]

        prompt_input = {
            "goal": self.goal,
            "hypothesis_1": hypo1.hypothesis,
            "hypothesis_2": hypo2.hypothesis,
            "review_1": hypo1.verification_result,
            "review_2": hypo2.verification_result,
        }

        formatted_prompt = load_prompt("tournament", **prompt_input)
        from coscientist.services.model_gateway import safe_ainvoke
        response = await safe_ainvoke(llm, formatted_prompt)
        response_text = response.content
        winner = self._parse_winner(response_text)

        global_cache.set("match", cache_key, {"winner": winner, "debate": response_text})
        return winner, response_text

    def run_round_robin_stage(self, llm: BaseChatModel):
        """Synchronous version"""
        hypo_ids = list(self.hypotheses.keys())
        stage = 1
        if len(hypo_ids) < 2:
            return

        all_pairs = list(itertools.combinations(hypo_ids, 2))
        valid_pairs = []
        for id1, id2 in all_pairs:
            pair_key = tuple(sorted((id1, id2))) + (stage,)
            if pair_key not in self.match_history:
                valid_pairs.append((id1, id2))
                
        random.shuffle(valid_pairs)
        matches_to_play = valid_pairs[:8]

        for id1, id2 in matches_to_play:
            hypo1 = self.hypotheses[id1]
            hypo2 = self.hypotheses[id2]
            rating1 = self.ratings[id1]
            rating2 = self.ratings[id2]
            winner, debate = self._determine_winner(hypo1, hypo2, "tournament", llm)
            self._record_match_result(id1, id2, stage, winner, debate, rating1, rating2)
            time.sleep(60 / settings.REQUESTS_PER_MINUTE)

    async def run_round_robin_stage_async(self, llm: BaseChatModel):
        """Asynchronous version using gather"""
        hypo_ids = list(self.hypotheses.keys())
        stage = 1
        if len(hypo_ids) < 2:
            return

        all_pairs = list(itertools.combinations(hypo_ids, 2))
        valid_pairs = []
        for id1, id2 in all_pairs:
            pair_key = tuple(sorted((id1, id2))) + (stage,)
            if pair_key not in self.match_history:
                valid_pairs.append((id1, id2))
                
        random.shuffle(valid_pairs)
        matches_to_play = valid_pairs[:8]

        async def play_match(id1, id2):
            hypo1 = self.hypotheses[id1]
            hypo2 = self.hypotheses[id2]
            winner, debate = await self._determine_winner_async(hypo1, hypo2, "tournament", llm)
            return id1, id2, winner, debate

        if not matches_to_play:
            return

        results = await asyncio.gather(*(play_match(id1, id2) for id1, id2 in matches_to_play))

        for id1, id2, winner, debate in results:
            # Re-read current rating because they might have been updated by other concurrent matches
            # Technically, in Elo, simultaneous games should use ratings from start of round, 
            # but updating sequentially with latest ratings is also fine.
            rating1 = self.ratings[id1]
            rating2 = self.ratings[id2]
            self._record_match_result(id1, id2, stage, winner, debate, rating1, rating2)

    def _record_match_result(self, id1, id2, stage, winner, debate, rating1, rating2):
        winner_id = id1 if winner == 1 else id2
        pair = tuple(sorted((id1, id2))) + (stage,)
        self.match_history[pair] = RankingMatchResult(
            hypoA_id=id1, hypoB_id=id2, winner_id=winner_id, rationale=debate
        )
        new_rating1, new_rating2 = update_elo(rating1, rating2, winner)
        self.ratings[id1] = new_rating1
        self.ratings[id2] = new_rating2
        
        # Also update the Elo property on the Hypothesis itself if it exists
        self.hypotheses[id1].elo = new_rating1
        self.hypotheses[id2].elo = new_rating2

        # Save to SQLite
        try:
            from coscientist.services.db_session import SessionLocal
            from coscientist.models.db_models import Match, Hypothesis
            with SessionLocal() as db:
                db_match = Match(
                    winner_uid=winner_id,
                    loser_uid=id1 if winner == 2 else id2,
                    justification=debate
                )
                db.add(db_match)
                
                # Update Elos
                hypo_1 = db.query(Hypothesis).filter(Hypothesis.uid == id1).first()
                if hypo_1:
                    hypo_1.elo = new_rating1
                hypo_2 = db.query(Hypothesis).filter(Hypothesis.uid == id2).first()
                if hypo_2:
                    hypo_2.elo = new_rating2
                db.commit()
        except ImportError:
            pass

    def run_bracket_stage(self, llm: BaseChatModel, k: int = 16) -> Optional[str]:
        """Synchronous version"""
        stage = 2
        if k <= 0 or (k & (k - 1) != 0):
            raise ValueError(f"K must be power of 2. Got {k}.")

        sorted_hypotheses = self.get_sorted_hypotheses()
        if len(sorted_hypotheses) < k:
            return None

        current_round_ids = [h_id for h_id, _ in sorted_hypotheses[:k]]
        while len(current_round_ids) > 1:
            next_round_ids = []
            num_contenders = len(current_round_ids)
            for i in range(num_contenders // 2):
                id1 = current_round_ids[i]
                id2 = current_round_ids[num_contenders - 1 - i]
                pair = tuple(sorted((id1, id2))) + (stage,)
                previous_outcome = self.match_history.get(pair, None)
                if previous_outcome is None:
                    winner, debate = self._determine_winner(self.hypotheses[id1], self.hypotheses[id2], "tournament", llm)
                    self._record_match_result(id1, id2, stage, winner, debate, self.ratings[id1], self.ratings[id2])
                    winner_id = id1 if winner == 1 else id2
                    time.sleep(60 / settings.REQUESTS_PER_MINUTE)
                else:
                    winner_id = previous_outcome.winner_id

                next_round_ids.append(winner_id)

            next_round_ids.sort(key=lambda h_id: self.ratings[h_id], reverse=True)
            current_round_ids = next_round_ids

        return current_round_ids[0] if current_round_ids else None

    async def run_bracket_stage_async(self, llm: BaseChatModel, k: int = 16) -> Optional[str]:
        """Asynchronous version"""
        stage = 2
        if k <= 0 or (k & (k - 1) != 0):
            raise ValueError(f"K must be power of 2. Got {k}.")

        sorted_hypotheses = self.get_sorted_hypotheses()
        if len(sorted_hypotheses) < k:
            return None

        current_round_ids = [h_id for h_id, _ in sorted_hypotheses[:k]]
        
        while len(current_round_ids) > 1:
            next_round_ids = []
            num_contenders = len(current_round_ids)
            
            # Prepare match tasks for the round
            match_tasks = []
            for i in range(num_contenders // 2):
                id1 = current_round_ids[i]
                id2 = current_round_ids[num_contenders - 1 - i]
                pair = tuple(sorted((id1, id2))) + (stage,)
                previous_outcome = self.match_history.get(pair, None)
                if previous_outcome is None:
                    # Async task
                    async def play_bracket_match(id1, id2):
                        winner, debate = await self._determine_winner_async(self.hypotheses[id1], self.hypotheses[id2], "tournament", llm)
                        return id1, id2, winner, debate
                    match_tasks.append(play_bracket_match(id1, id2))
                else:
                    next_round_ids.append(previous_outcome.winner_id)

            if match_tasks:
                results = await asyncio.gather(*match_tasks)
                for id1, id2, winner, debate in results:
                    self._record_match_result(id1, id2, stage, winner, debate, self.ratings[id1], self.ratings[id2])
                    winner_id = id1 if winner == 1 else id2
                    next_round_ids.append(winner_id)

            next_round_ids.sort(key=lambda h_id: self.ratings[h_id], reverse=True)
            current_round_ids = next_round_ids

        return current_round_ids[0] if current_round_ids else None

    def run_tournament(self, llm: BaseChatModel, k_bracket: int = 16) -> Optional[str]:
        self.run_round_robin_stage(llm)
        self.run_bracket_stage(llm, k=k_bracket)
        self._past_tournament_ratings.append(list(self.ratings.values()))

    async def run_tournament_async(self, llm: BaseChatModel, k_bracket: int = 16) -> Optional[str]:
        await self.run_round_robin_stage_async(llm)
        await self.run_bracket_stage_async(llm, k=k_bracket)
        self._past_tournament_ratings.append(list(self.ratings.values()))

    def get_win_loss_records(self) -> dict[str, dict[str, int]]:
        records = {h_id: {"wins": 0, "losses": 0} for h_id in self.hypotheses.keys()}

        for match_result in self.match_history.values():
            winner_id = match_result.winner_id
            loser_id = match_result.hypoB_id if match_result.winner_id == match_result.hypoA_id else match_result.hypoA_id

            records[winner_id]["wins"] += 1
            records[loser_id]["losses"] += 1

        return records

    def summarize_tournament_trajectory(self) -> str:
        summary_stats_dict = {
            "max_elo_rating": [],
            "num_elo_ratings_over_1400": [],
            "median_elo_rating": [],
        }
        for round_ratings in self._past_tournament_ratings[::-1]:
            summary_stats_dict["max_elo_rating"].append(max(round_ratings))
            summary_stats_dict["num_elo_ratings_over_1400"].append(
                sum(1 for rating in round_ratings if rating >= 1400)
            )
            summary_stats_dict["median_elo_rating"].append(
                statistics.median(round_ratings)
            )

        summary_stats_dict["top_3_elo_ratings"] = [
            rating for _, rating in self.get_sorted_hypotheses()[:3]
        ]
        summary_stats_dict["total_matches_played"] = len(self.match_history)
        summary_stats_dict["total_rounds_played"] = len(self._past_tournament_ratings)

        return summary_stats_dict
