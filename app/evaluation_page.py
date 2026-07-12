import sys
import os
import asyncio
import streamlit as st

# Add the parent directory to the path so we can import evaluate
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from evaluate import evaluate_single_report
except ImportError:
    evaluate_single_report = None


def run_async_evaluation(goal, report):
    """Helper to run async evaluation function in Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(evaluate_single_report(goal, report))


def display_evaluation_page(state):
    """
    Display the Evaluation Benchmark page.

    Parameters
    ----------
    state : CoscientistState
        The loaded Coscientist state containing the final report
    """
    st.header("🏆 Evaluation Benchmark")
    
    st.markdown("""
    This dashboard evaluates the AI Co-Scientist's final report against Google's official benchmark metrics.
    """)

    # Google's Official Baselines
    st.subheader("Official Baselines (For Comparison)")
    col1, col2, col3 = st.columns(3)
    col1.metric("Target Novelty", "3.64 / 4.0")
    col2.metric("Target Impact", "3.09 / 4.0")
    col3.metric("Target GPQA Score", "> 74%")
    
    st.divider()

    # Check if we have a final report
    if not hasattr(state, "final_report") or not state.final_report:
        st.warning("No final report found in this research state to evaluate.")
        return
        
    final_report_content = state.final_report.get("result", "")
    goal_content = getattr(state, "goal", "Unknown Goal")
    
    if not final_report_content:
        st.error("Final report exists but contains no content.")
        return

    st.markdown("### Run Live Evaluation")
    st.write("Click the button below to use the LLM-as-a-judge (Gemini 3.1 Pro via Google GenAI) to grade this project's final report.")
    
    if st.button("▶ Run Live Evaluation", type="primary"):
        if not evaluate_single_report:
            st.error("Failed to load evaluation logic. Ensure evaluate.py is in the parent directory.")
            return
            
        with st.spinner("Running deep evaluation pipeline... this may take up to 20 seconds."):
            try:
                # Call evaluate_single_report
                result = run_async_evaluation(goal_content, final_report_content)
                
                st.success("Evaluation completed!")
                
                # Display Results
                st.subheader("Results")
                
                # Top row metrics
                r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                
                r_col1.metric("Novelty Rating", f"{result.novelty:.2f} / 4.0", delta=f"{result.novelty - 3.64:.2f} vs Target")
                r_col2.metric("Impact Rating", f"{result.impact:.2f} / 4.0", delta=f"{result.impact - 3.09:.2f} vs Target")
                r_col3.metric("GPQA Equivalent", f"{result.gpqa_score}%", delta=f"{result.gpqa_score - 74}% vs Target")
                r_col4.metric("Groundedness", f"{result.groundedness}%")
                
                # Feedback
                st.markdown("#### Evaluation Feedback")
                st.info(result.feedback)
                
                st.markdown("---")
                with st.expander("View Report Being Evaluated"):
                    st.markdown(f"**Goal**: {goal_content}")
                    st.markdown(final_report_content)
                    
            except Exception as e:
                st.error(f"An error occurred during evaluation: {e}")
                st.info("Check your PUTER_API_KEY and internet connection.")
