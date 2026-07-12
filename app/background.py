import asyncio
import os

from coscientist.graphs.framework import CoscientistConfig, CoscientistFramework
from coscientist.graphs.global_state import CoscientistState, CoscientistStateManager


def _get_done_file_path(goal: str) -> str:
    """Gets the path for the 'done' file for a given goal."""
    goal_hash = CoscientistState._hash_goal(goal)
    # This assumes _OUTPUT_DIR is consistent.
    output_dir = os.path.join(
        os.environ.get("COSCIENTIST_DIR", os.path.expanduser("~/.coscientist")),
        goal_hash,
    )
    return os.path.join(output_dir, "done.txt")


def coscientist_process_target(goal: str):
    """The target function for the multiprocessing.Process."""
    try:
        # This will fail if the directory exists, which is what we want.
        initial_state = CoscientistState(goal=goal)
        config = CoscientistConfig()
        state_manager = CoscientistStateManager(initial_state)
        cosci = CoscientistFramework(config, state_manager)

        # Run the framework
        asyncio.run(cosci.run())

    except Exception as e:
        # Log error to a file in the goal directory
        goal_hash = CoscientistState._hash_goal(goal)
        output_dir = os.path.join(
            os.environ.get("COSCIENTIST_DIR", os.path.expanduser("~/.coscientist")),
            goal_hash,
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(os.path.join(output_dir, "error.log"), "w") as f:
            f.write(str(e))
    finally:
        # Create a "done" file to signal completion
        done_file = _get_done_file_path(goal)
        with open(done_file, "w") as f:
            f.write("done")


def check_coscientist_status(goal: str) -> str:
    """Checks the status of a Coscientist run."""
    goal_hash = CoscientistState._hash_goal(goal)
    output_dir = os.path.join(
        os.environ.get("COSCIENTIST_DIR", os.path.expanduser("~/.coscientist")),
        goal_hash,
    )

    done_file = os.path.join(output_dir, "done.txt")
    error_file = os.path.join(output_dir, "error.log")

    if os.path.exists(done_file):
        if os.path.exists(error_file):
            with open(error_file, "r") as f:
                error_message = f.read()
            return f"error: {error_message}"
        return "done"
    return "running"


def get_coscientist_results(goal: str) -> tuple[str, str]:
    """Gets the results from a completed Coscientist run."""
    state = CoscientistState.load_latest(goal=goal)
    if state and state.final_report and state.meta_reviews:
        # These are TypedDicts, access by key.
        final_report_text = state.final_report.get(
            "result", "Final report not generated."
        )
        meta_review_text = state.meta_reviews[-1].get(
            "result", "Meta review not generated."
        )
        return final_report_text, meta_review_text
    return "Results not found.", "Results not found."


def cleanup_coscientist_run(goal: str):
    """Cleans up files after a run."""
    goal_hash = CoscientistState._hash_goal(goal)
    output_dir = os.path.join(
        os.environ.get("COSCIENTIST_DIR", os.path.expanduser("~/.coscientist")),
        goal_hash,
    )
    done_file = os.path.join(output_dir, "done.txt")
    error_file = os.path.join(output_dir, "error.log")
    if os.path.exists(done_file):
        os.remove(done_file)
    if os.path.exists(error_file):
        os.remove(error_file)
