import asyncio
import multiprocessing
import os

import streamlit as st
from background import _get_done_file_path, check_coscientist_status
from common import get_available_states

from coscientist.framework import CoscientistConfig, CoscientistFramework
from coscientist.global_state import CoscientistState, CoscientistStateManager


def coscientist_resume_target(goal: str):
    """The target function for resuming a Coscientist process."""
    try:
        # Load the existing state instead of creating a new one
        initial_state = CoscientistState.load_latest(goal=goal)
        if initial_state is None:
            raise Exception(f"No existing state found for goal: {goal}")

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


def display_resume_page():
    """Display the resume from checkpoint page."""
    st.header("🔄 Resume from Checkpoint")

    st.markdown("""
    Resume a Coscientist research process from where it left off. This page allows you to:
    
    - Select an existing research goal that has been started
    - Check if the research is already completed
    - Resume the research process from the latest checkpoint
    """)

    # Initialize session state for process tracking
    if "resume_process" not in st.session_state:
        st.session_state.resume_process = None
    if "resume_goal" not in st.session_state:
        st.session_state.resume_goal = None

    # Get available goals
    available_goals = get_available_states()

    if not available_goals:
        st.warning(
            "No existing research goals found. Please start a new research goal first."
        )
        return

    # Goal selection
    st.subheader("📋 Select Research Goal")
    selected_goal = st.selectbox(
        "Choose a research goal to resume:",
        options=available_goals,
        format_func=lambda x: x[:100] + "..." if len(x) > 100 else x,
        help="Select an existing research goal to resume from its latest checkpoint",
    )

    # Check status and display information
    if selected_goal:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📊 Goal Status")

            try:
                # Load the latest state to check if finished
                state = CoscientistState.load_latest(goal=selected_goal)
                if state is None:
                    st.error("❌ No state found for this goal. Cannot resume.")
                    return

                # Create state manager to check if finished
                state_manager = CoscientistStateManager(state)
                is_finished = state_manager.is_finished

                # Check running status
                status = check_coscientist_status(selected_goal)

                if is_finished:
                    st.success("✅ This research goal has already been completed!")
                    st.info(
                        "The research process for this goal has finished. You can view the results in the Tournament Rankings or Proximity Graph pages."
                    )
                elif status == "running":
                    st.warning("⏳ This goal is currently running in another process.")
                    st.info(
                        "Please wait for the current process to finish before resuming."
                    )
                elif status.startswith("error"):
                    st.error(f"❌ Previous run ended with error: {status[7:]}")
                    st.info(
                        "You can try resuming to continue from the last successful checkpoint."
                    )
                else:
                    st.info("🔄 This goal can be resumed.")
                    st.success("Ready to resume from the latest checkpoint.")

                # Display some basic state information
                with st.expander("📈 Current State Information"):
                    st.write(f"**Goal:** {selected_goal}")
                    st.write(f"**Finished:** {'Yes ✅' if is_finished else 'No ❌'}")
                    if hasattr(state, "hypotheses") and state.hypotheses:
                        st.write(f"**Number of Hypotheses:** {len(state.hypotheses)}")
                    if (
                        hasattr(state, "tournament_results")
                        and state.tournament_results
                    ):
                        st.write(
                            f"**Tournament Matches:** {len(state.tournament_results)}"
                        )

            except Exception as e:
                st.error(f"❌ Error checking goal status: {str(e)}")
                return

        with col2:
            st.subheader("🚀 Resume Action")

            # Resume button
            can_resume = (
                state is not None
                and not is_finished
                and status != "running"
                and (
                    st.session_state.resume_process is None
                    or not st.session_state.resume_process.is_alive()
                )
            )

            if st.button(
                "🔄 Resume Research",
                disabled=not can_resume,
                help="Resume the research process from the latest checkpoint"
                if can_resume
                else "Cannot resume: check the status information",
            ):
                try:
                    # Start the resume process
                    st.session_state.resume_process = multiprocessing.Process(
                        target=coscientist_resume_target, args=(selected_goal,)
                    )
                    st.session_state.resume_process.start()
                    st.session_state.resume_goal = selected_goal
                    st.success(f"🚀 Resumed research for: {selected_goal[:50]}...")
                    st.info(
                        "The research process is now running in the background. You can check the status below or refresh the page to see updates."
                    )

                except Exception as e:
                    st.error(f"❌ Failed to resume research: {str(e)}")

    # Display running process status
    if st.session_state.resume_process is not None and st.session_state.resume_goal:
        st.subheader("🔄 Resume Process Status")

        # Check if process is still running
        if st.session_state.resume_process.is_alive():
            st.info(
                f"⏳ Research is currently running for: {st.session_state.resume_goal[:50]}..."
            )

            # Add a refresh button
            if st.button("🔄 Refresh Status"):
                st.rerun()

        else:
            # Process has finished
            status = check_coscientist_status(st.session_state.resume_goal)
            if status == "done":
                st.success(
                    f"✅ Research completed successfully for: {st.session_state.resume_goal[:50]}..."
                )
            elif status.startswith("error"):
                st.error(f"❌ Research ended with error: {status[7:]}")

            # Clear the process from session state
            st.session_state.resume_process = None
            st.session_state.resume_goal = None

    # Tips section
    with st.expander("💡 Tips for Resuming Research"):
        st.markdown("""
        **Before resuming:**
        - Make sure the research goal is not already completed
        - Check that no other process is currently running for this goal
        - Review the current state information to understand progress
        
        **During resume:**
        - The process runs in the background - you can navigate to other pages
        - Use the refresh button to check status updates
        - Check the Tournament Rankings page to see new results as they appear
        
        **After completion:**
        - View results in the Tournament Rankings page
        - Explore hypothesis relationships in the Proximity Graph page
        - Results are automatically saved and can be viewed later
        """)
