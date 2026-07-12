import streamlit as st


def display_final_report_page(state):
    """
    Display the final report page.

    Parameters
    ----------
    state : CoscientistState
        The loaded Coscientist state containing the final report
    """
    st.header("📋 Final Report")

    # Check if we have a final report
    if not hasattr(state, "final_report") or not state.final_report:
        st.warning("No final report found in this research state.")
        st.markdown("""
        ## Final Report Page
        
        This page displays the final research report generated when the Coscientist system completes its research:
        
        - **Comprehensive Summary**: Complete analysis of all hypotheses and findings
        - **Top Hypotheses**: Detailed review of the highest-ranked hypotheses
        - **Research Conclusions**: Final insights and recommendations
        - **Methodology Summary**: Overview of the research process and evaluation methods
        
        The final report is generated only when the supervisor agent decides the research process
        is complete and has achieved sufficient depth and quality in hypothesis exploration.
        """)
        return

    # Display the final report
    final_report_content = state.final_report.get("result", "")

    if final_report_content:
        st.markdown("### 📊 Research Summary")
        st.info("✅ Research process completed successfully!")

        # Display the final report content
        st.markdown(final_report_content)

        # Show some basic statistics if available
        with st.expander("📈 Research Statistics"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Process Overview:**")
                if hasattr(state, "actions"):
                    st.write(f"• Total Actions Taken: {len(state.actions)}")
                if hasattr(state, "supervisor_decisions"):
                    st.write(
                        f"• Supervisor Decisions: {len(state.supervisor_decisions)}"
                    )
                if hasattr(state, "meta_reviews"):
                    st.write(f"• Meta-Reviews Completed: {len(state.meta_reviews)}")

            with col2:
                st.markdown("**Hypothesis Statistics:**")
                if hasattr(state, "tournament") and state.tournament:
                    st.write(
                        f"• Tournament Hypotheses: {len(state.tournament.hypotheses)}"
                    )
                    # Get tournament stats if available
                    try:
                        tournament_stats = (
                            state.tournament.summarize_tournament_trajectory()
                        )
                        st.write(
                            f"• Total Matches Played: {tournament_stats.get('total_matches_played', 'N/A')}"
                        )
                        st.write(
                            f"• Max ELO Rating: {tournament_stats.get('max_elo_rating', ['N/A'])[0] if tournament_stats.get('max_elo_rating') else 'N/A'}"
                        )
                    except:  # noqa: E722
                        st.write("• Tournament statistics unavailable")

    else:
        st.error("Final report exists but contains no content.")
