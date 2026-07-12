import os
import sys
import asyncio
import argparse
import logging
from typing import Dict, Any

from coscientist.evaluation.benchmark import get_benchmark
from coscientist.evaluation.evaluate import Evaluator
from coscientist.graphs.framework import CoscientistFramework, CoscientistConfig
from coscientist.graphs.global_state import CoscientistStateManager
from coscientist.services.model_gateway import metrics_tracker
from coscientist.configs.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_benchmark_task(task: Dict[str, Any], evaluator: Evaluator):
    logger.info(f"Starting benchmark task: {task['id']}")
    
    # Initialize state and config
    config = CoscientistConfig()
    goal = task['goal']
    
    from coscientist.graphs.global_state import CoscientistState
    try:
        CoscientistState.clear_goal_directory(goal)
    except Exception:
        pass
        
    state = CoscientistState(goal)
    state_manager = CoscientistStateManager(state)
    
    framework = CoscientistFramework(config, state_manager)
    
    # Reset metrics tracker before each run
    metrics_tracker.reset()
    
    # Execute the framework
    try:
        await framework.run()
    except Exception as e:
        logger.error(f"Error running benchmark {task['id']}: {e}")
        return
        
    # Evaluate the results
    if state_manager.tournament:
        metrics = evaluator.evaluate_tournament(state_manager.tournament, goal_name=task['id'])
        logger.info(f"Completed benchmark {task['id']}. Top-1 Elo: {metrics.get('final_max_elo')}")
    else:
        logger.warning(f"No tournament completed for {task['id']}")

async def main():
    parser = argparse.ArgumentParser(description="AI Co-Scientist Benchmark Runner")
    parser.add_argument("--run-benchmarks", action="store_true", help="Run the full benchmark suite")
    parser.add_argument("--task-id", type=str, help="Run a specific benchmark task by ID")
    args = parser.parse_args()
    
    if not args.run_benchmarks and not args.task_id:
        parser.print_help()
        return

    benchmark_dataset = get_benchmark("CoScientistBenchmarks")
    benchmark_dataset.load()
    tasks = benchmark_dataset.get_tasks()
    
    if not tasks:
        logger.error("No benchmark tasks found. Please ensure data/benchmarks/ contains JSON files.")
        return
        
    if args.task_id:
        tasks = [t for t in tasks if t['id'] == args.task_id]
        if not tasks:
            logger.error(f"Task ID {args.task_id} not found.")
            return

    evaluator = Evaluator()
    
    for task in tasks:
        await run_benchmark_task(task, evaluator)
        
    summary_table = evaluator.generate_summary_table()
    print("\n\n" + "="*80)
    print("BENCHMARK RESULTS")
    print("="*80)
    print(summary_table)
    
    # Optionally save to file
    with open("benchmark_results.md", "w") as f:
        f.write("# Benchmark Results\n\n")
        f.write(summary_table)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Enable LangSmith tracing if API key is present
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        logger.info("LangSmith observability enabled.")
    
    asyncio.run(main())
