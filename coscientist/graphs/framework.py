"""
The overall framework that takes a CoscientistStateManager from global_state.py,
setups the agents, and organizes the multi-agent system. The framework will be controlled
by a supervisor agent.
"""

import logging
import math
import random
import asyncio

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from coscientist.agents.evolution_agent import build_evolution_agent
from coscientist.agents.final_report_agent import build_final_report_agent
from coscientist.agents.generation_agent import (
    CollaborativeConfig,
    IndependentConfig,
    build_generation_agent,
)
from coscientist.graphs.global_state import CoscientistStateManager
from coscientist.agents.literature_review_agent import build_literature_review_agent
from coscientist.agents.meta_review_agent import build_meta_review_agent
from coscientist.models.reasoning_types import ReasoningType
from coscientist.agents.reflection_agent import build_deep_verification_agent
from coscientist.agents.supervisor_agent import build_supervisor_agent
from coscientist.services.model_gateway import gateway, metrics_tracker
from coscientist.configs.config import settings
from coscientist.configs.research_plan import parse_goal

class CoscientistConfig:
    """
    Configuration for the Coscientist system using ModelGateway.
    """

    def __init__(
        self,
        literature_review_agent_llm: BaseChatModel | None = None,
        generation_agent_llms: dict[str, BaseChatModel] | None = None,
        reflection_agent_llms: dict[str, BaseChatModel] | None = None,
        evolution_agent_llms: dict[str, BaseChatModel] | None = None,
        meta_review_agent_llm: BaseChatModel | None = None,
        supervisor_agent_llm: BaseChatModel | None = None,
        final_report_agent_llm: BaseChatModel | None = None,
        specialist_fields: list[str] | None = None,
    ):
        gemini_llm = gateway.get_gemini_llm()
        groq_llm = gateway.get_groq_llm()
        
        self.literature_review_agent_llm = literature_review_agent_llm or groq_llm
        self.generation_agent_llms = generation_agent_llms or {"default": gemini_llm}
        self.reflection_agent_llms = reflection_agent_llms or {"default": groq_llm}
        self.evolution_agent_llms = evolution_agent_llms or {"default": groq_llm}
        self.meta_review_agent_llm = meta_review_agent_llm or groq_llm
        self.supervisor_agent_llm = supervisor_agent_llm or groq_llm
        self.final_report_agent_llm = final_report_agent_llm or gemini_llm
        
        if specialist_fields is None:
            self.specialist_fields = ["biology"]
        else:
            self.specialist_fields = specialist_fields


class CoscientistFramework:
    """
    The framework that takes a CoscientistStateManager from global_state.py,
    setups the agents, and organizes the multi-agent system. The framework will be controlled
    by a supervisor agent.
    """

    def __init__(
        self, config: CoscientistConfig, state_manager: CoscientistStateManager
    ):
        self.config = config
        self.state_manager = state_manager
        
        # Parse goal to get plan and budgets
        self.research_plan = parse_goal(self.state_manager.goal)
        logging.info(f"Loaded Research Plan with budgets: Generation={self.research_plan.generation_budget}, Evolution={self.research_plan.evolution_budget}, Reflection={self.research_plan.reflection_budget}")

    def list_generation_llm_names(self) -> list[str]:
        """
        List the names of the generation agents.
        """
        return list(self.config.generation_agent_llms.keys())

    def list_generation_modes(self) -> list[str]:
        """
        List the names of the generation modes.
        """
        return ["independent", "collaborative"]

    def list_reflection_llm_names(self) -> list[str]:
        """
        List the names of the reflection agents.
        """
        return list(self.config.reflection_agent_llms.keys())

    def list_evolution_llm_names(self) -> list[str]:
        """
        List the names of the evolution agents.
        """
        return list(self.config.evolution_agent_llms.keys())

    def list_evolution_modes(self) -> list[str]:
        """
        List the names of the evolution modes.
        """
        return ["evolve_from_feedback", "out_of_the_box"]

    def list_specialist_fields(self) -> list[str]:
        """
        List the names of the specialist fields.
        """
        return self.config.specialist_fields

    def list_reasoning_types(self) -> list[str]:
        """
        List the names of the reasoning types.
        """
        return list(ReasoningType.__members__.keys())

    def get_semantic_communities(
        self, resolution: float = 1.0, min_weight: float = 0.85
    ) -> list[set[str]]:
        """
        Get the semantic communities of the hypotheses.
        """
        self.state_manager.proximity_graph.update_edges()
        return self.state_manager.proximity_graph.get_semantic_communities(
            resolution=resolution, min_weight=min_weight
        )

    async def _verify_hypothesis(self, initial_reflection_state):
        metrics_tracker.current_agent_role = "reflection"
        llm_name = random.choice(self.list_reflection_llm_names())
        reflection_agent = build_deep_verification_agent(
            llm=self.config.reflection_agent_llms[llm_name],
            review_llm=self.config.meta_review_agent_llm,
            parallel=False,
            checkpointer=None,
        )
        final_reflection_state = await reflection_agent.ainvoke(initial_reflection_state)
        if final_reflection_state["passed_initial_filter"]:
            self.state_manager.add_reviewed_hypothesis(
                final_reflection_state["reviewed_hypothesis"]
            )
            self.state_manager.advance_reviewed_hypothesis()

    async def process_reflection_queue(self) -> None:
        """
        Enqueue all hypotheses in the reflection queue for verification.
        """
        if metrics_tracker.agent_tokens["reflection"] >= self.research_plan.reflection_budget:
            logging.warning("Reflection budget exceeded. Skipping reflection.")
            return
            
        while not self.state_manager.reflection_queue_is_empty:
            state = self.state_manager.next_reflection_state()
            await self.task_queue.put({"action": "_verify_hypothesis", "state": state})

    async def _generate_new_hypothesis(self) -> None:
        """
        Run the hypothesis generation for a given mode and config.
        """
        if metrics_tracker.agent_tokens["generation"] >= self.research_plan.generation_budget:
            logging.warning("Generation budget exceeded. Skipping generation.")
            return
            
        metrics_tracker.current_agent_role = "generation"
        mode = random.choice(self.list_generation_modes())
        if mode == "independent":
            llm_name = random.choice(self.list_generation_llm_names())
            reasoning_type = random.choice(self.list_reasoning_types())
            specialist_field = random.choice(self.list_specialist_fields())
            config = IndependentConfig(
                llm=self.config.generation_agent_llms[llm_name],
                reasoning_type=getattr(ReasoningType, reasoning_type),
                field=specialist_field,
            )
            first_agent_name = None
        elif mode == "collaborative":
            llm_names = np.random.choice(self.list_generation_llm_names(), 2).tolist()
            specialist_fields = np.random.choice(self.list_specialist_fields(), 2).tolist()
            reasoning_types = np.random.choice(self.list_reasoning_types(), 2).tolist()

            agent_names = [f"{llm_name}_{field}" for llm_name, field in zip(llm_names, specialist_fields)]
            config = CollaborativeConfig(
                agent_names=agent_names,
                agent_fields=dict(zip(agent_names, specialist_fields)),
                agent_reasoning_types={
                    name: getattr(ReasoningType, reasoning_type)
                    for name, reasoning_type in zip(agent_names, reasoning_types)
                },
                llms={
                    name: self.config.generation_agent_llms[llm_name]
                    for name, llm_name in zip(agent_names, llm_names)
                },
                max_turns=10,
            )
            first_agent_name = agent_names[0]

        # Rate limit delay (add jitter to prevent thundering herd)
        await asyncio.sleep(random.uniform(0.5, 2.0) + (60 / settings.REQUESTS_PER_MINUTE))
        
        generation_agent = build_generation_agent(mode, config)
        initial_generation_state = self.state_manager.next_generation_state(mode, first_agent_name)
        final_generation_state = await generation_agent.ainvoke(initial_generation_state)
        self.state_manager.add_generated_hypothesis(final_generation_state["hypothesis"])
        # Advance immediately so it gets queued for reflection
        self.state_manager.advance_hypothesis(kind="generated")

    async def start(self, n_hypotheses: int = None) -> None:
        if n_hypotheses is None:
            n_hypotheses = settings.INITIAL_HYPOTHESES
        assert n_hypotheses >= 2, "Must generate at least two hypotheses to start"
        if self.state_manager.is_started:
            raise ValueError(f"Coscientist system has already been started.")

        if not self.state_manager.has_literature_review:
            await self.task_queue.put({"action": "expand_literature_review"})

        await self.generate_new_hypotheses(
            n_hypotheses=max(0, n_hypotheses - self.state_manager.total_hypotheses)
        )

        await self.task_queue.put({"action": "run_tournament"})
        await self.task_queue.put({"action": "run_meta_review"})

    async def generate_new_hypotheses(self, n_hypotheses: int = None) -> None:
        if n_hypotheses is None:
            n_hypotheses = 2
        
        for _ in range(n_hypotheses):
            await self.task_queue.put({"action": "_generate_new_hypothesis"})
            
        await self.process_reflection_queue()

    async def _evolve_uid(self, uid):
        initial_evolution_state = self.state_manager.next_evolution_state(mode="evolve_from_feedback", uid_to_evolve=uid)
        llm_name = random.choice(self.list_evolution_llm_names())
        evolution_agent = build_evolution_agent(mode="evolve_from_feedback", llm=self.config.evolution_agent_llms[llm_name])
        final_evolution_state = await evolution_agent.ainvoke(initial_evolution_state)
        self.state_manager.add_evolved_hypothesis(final_evolution_state["evolved_hypothesis"])
        self.state_manager.advance_hypothesis(kind="evolved")

    async def _evolve_out_of_box(self, top_k):
        out_of_box_initial_state = self.state_manager.next_evolution_state(mode="out_of_the_box", top_k=top_k)
        llm_name = random.choice(self.list_evolution_llm_names())
        evolution_agent = build_evolution_agent(mode="out_of_the_box", llm=self.config.evolution_agent_llms[llm_name])
        out_of_box_state = await evolution_agent.ainvoke(out_of_box_initial_state)
        self.state_manager.add_evolved_hypothesis(out_of_box_state["evolved_hypothesis"])
        self.state_manager.advance_hypothesis(kind="evolved")

    async def evolve_hypotheses(self, n_hypotheses: int = 4) -> None:
        if metrics_tracker.agent_tokens["evolution"] >= self.research_plan.evolution_budget:
            logging.warning("Evolution budget exceeded. Skipping evolution.")
            return
            
        assert n_hypotheses >= 2, "Must evolve at least two hypotheses"
        assert self.state_manager.is_started, "Coscientist system must be started first"
        evolution_candidate_uids = self.state_manager.get_tournament_hypotheses_for_evolution()
        
        if len(evolution_candidate_uids) < n_hypotheses:
            n_hypotheses = len(evolution_candidate_uids)
            if n_hypotheses < 2:
                return

        top_ranked_uids = evolution_candidate_uids[: (n_hypotheses // 2)]
        random_uids = np.random.choice(
            evolution_candidate_uids[(n_hypotheses // 2) :],
            size=n_hypotheses // 2,
            replace=False,
        ).tolist()

        for uid in (top_ranked_uids + random_uids):
            await self.task_queue.put({"action": "_evolve_uid", "uid": uid})

        await self.task_queue.put({"action": "_evolve_out_of_box", "top_k": n_hypotheses // 2})
        await self.process_reflection_queue()

    async def expand_literature_review(self) -> None:
        initial_lit_review_state = self.state_manager.next_literature_review_state(max_subtopics=5)
        literature_review_agent = build_literature_review_agent(self.config.literature_review_agent_llm)
        final_lit_review_state = await literature_review_agent.ainvoke(initial_lit_review_state)
        self.state_manager.update_literature_review(final_lit_review_state)

    async def run_tournament(self, k_bracket: int = 8) -> None:
        metrics_tracker.current_agent_role = "ranking"
        num_hypo = self.state_manager.num_tournament_hypotheses
        if num_hypo < 2:
            return
        k_bracket = min(k_bracket, 2 ** math.floor(math.log2(num_hypo)))
        # Wait for the async tournament
        await self.state_manager.run_tournament_async(llm=self.config.meta_review_agent_llm, k_bracket=k_bracket)

    async def run_meta_review(self, k_bracket: int = 8) -> None:
        metrics_tracker.current_agent_role = "meta_review"
        initial_meta_review_state = self.state_manager.next_meta_review_state(top_k=k_bracket)
        meta_review_agent = build_meta_review_agent(self.config.meta_review_agent_llm)
        final_meta_review_state = await meta_review_agent.ainvoke(initial_meta_review_state)
        self.state_manager.update_meta_review(final_meta_review_state)

    async def finish(self) -> None:
        initial_final_report_state = self.state_manager.next_final_report_state(top_k=3)
        final_report_agent = build_final_report_agent(self.config.final_report_agent_llm)
        final_report_state = await final_report_agent.ainvoke(initial_final_report_state)
        self.state_manager.update_final_report(final_report_state)

    @classmethod
    def available_actions(self) -> list[str]:
        return [
            "generate_new_hypotheses",
            "evolve_hypotheses",
            "expand_literature_review",
            "run_tournament",
            "run_meta_review",
            "finish",
        ]

    async def worker_loop(self):
        """Worker loop for pulling atomic tasks from the queue and executing them."""
        while True:
            task = await self.task_queue.get()
            action = task["action"]
            if action == "SHUTDOWN":
                self.task_queue.task_done()
                break
            try:
                if action == "_generate_new_hypothesis":
                    await self._generate_new_hypothesis()
                elif action == "_verify_hypothesis":
                    await self._verify_hypothesis(task["state"])
                elif action == "_evolve_uid":
                    await self._evolve_uid(task["uid"])
                elif action == "_evolve_out_of_box":
                    await self._evolve_out_of_box(task["top_k"])
                elif hasattr(self, action):
                    await getattr(self, action)()
                else:
                    logging.error(f"Unknown task action: {action}")
            except Exception as e:
                logging.error(f"Error executing task {action}: {e}")
            finally:
                self.task_queue.task_done()

    async def run(self) -> tuple[str, str]:
        self.task_queue = asyncio.Queue()
        num_workers = 3
        workers = [asyncio.create_task(self.worker_loop()) for _ in range(num_workers)]

        if not self.state_manager.is_started:
            await self.start(n_hypotheses=settings.INITIAL_HYPOTHESES)

        supervisor_agent = build_supervisor_agent(self.config.supervisor_agent_llm)
        
        current_action = None
        while not self.state_manager.is_finished:
            # Continuously check for new reflection queue items
            if not self.state_manager.reflection_queue_is_empty:
                await self.process_reflection_queue()
                
            # Poll state and push macro actions when the queue runs dry
            if self.task_queue.empty():
                metrics_tracker.current_agent_role = "supervisor"
                initial_supervisor_state = self.state_manager.next_supervisor_state()
                final_supervisor_state = await supervisor_agent.ainvoke(initial_supervisor_state)
                current_action = final_supervisor_state["action"]
                
                if current_action not in self.available_actions():
                    current_action = "run_tournament"

                if current_action == "finish" and settings.REQUIRE_HUMAN_APPROVAL:
                    print("\n" + "="*50)
                    print("🛑 [HITL] SUPERVISOR DECISION: FINISH RESEARCH")
                    print("="*50)
                    user_input = input("The supervisor has decided to generate the final report. Approve? (y/n): ")
                    if user_input.strip().lower() != 'y':
                        current_action = "run_tournament"

                self.state_manager.update_supervisor_decision(final_supervisor_state)
                self.state_manager.add_action(current_action)

                if current_action == "generate_new_hypotheses":
                    await self.generate_new_hypotheses()
                elif current_action == "evolve_hypotheses":
                    await self.evolve_hypotheses()
                elif current_action == "finish":
                    await self.task_queue.put({"action": "finish"})
                    await self.task_queue.join()
                    break
                else:
                    await self.task_queue.put({"action": current_action})
            
            # Wait for tasks to progress before deciding next macro action
            await asyncio.sleep(3)
            self.state_manager.update_proximity_graph_edges()

        # Wait for all tasks to complete
        await self.task_queue.join()

        # Shutdown workers
        for _ in range(num_workers):
            await self.task_queue.put({"action": "SHUTDOWN"})
        await asyncio.gather(*workers)

        return self.state_manager.final_report, self.state_manager.meta_reviews[-1]
