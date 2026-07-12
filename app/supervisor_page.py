import streamlit as st


def display_supervisor_page(state):
    """
    Display the supervisor decisions page.

    Parameters
    ----------
    state : CoscientistState
        The loaded Coscientist state containing supervisor decisions and actions
    """
    st.header("🎯 Supervisor Decisions")

    # Check if we have supervisor decisions
    if not hasattr(state, "supervisor_decisions") or not state.supervisor_decisions:
        st.warning("No supervisor decisions found in this research state.")
        st.markdown("""
        ## Supervisor Decisions Page
        
        This page displays the decision-making process of the supervisor agent:
        
        - **Actions Taken**: See all actions decided by the supervisor in chronological order
        - **Decision Reasoning**: View the detailed reasoning behind each decision
        - **Strategic Context**: Understand the system state that influenced each decision
        
        The supervisor agent analyzes the research progress and decides what actions to take next,
        such as generating hypotheses, running tournaments, or finishing the research.
        """)
        return

    # Get supervisor decisions and actions
    supervisor_decisions = state.supervisor_decisions
    actions = state.actions

    # Verify they are correlated
    if len(supervisor_decisions) != len(actions):
        st.error(
            f"Mismatch between supervisor decisions ({len(supervisor_decisions)}) and actions ({len(actions)})"
        )
        return

    # Create two columns: actions list and reasoning display
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📋 Actions History")
        st.markdown(f"**Total Actions:** {len(actions)}")

        # Create a container for the scrollable actions list
        actions_container = st.container()

        # Initialize session state for selected action
        if "selected_action_index" not in st.session_state:
            st.session_state.selected_action_index = 0  # Default to latest action

        with actions_container:
            # Display actions in reverse order (latest first) with numbering
            for i, (action, _decision) in enumerate(
                zip(reversed(actions), reversed(supervisor_decisions))
            ):
                action_number = len(actions) - i  # Number from latest to oldest

                # Create a clickable button for each action
                button_key = f"action_{i}"
                button_label = f"#{action_number}: {action}"

                # Highlight the selected action
                if i == st.session_state.selected_action_index:
                    st.markdown(f"**🔹 {button_label}**")
                else:
                    if st.button(button_label, key=button_key):
                        st.session_state.selected_action_index = i
                        st.rerun()

    with col2:
        st.subheader("💭 Decision Reasoning")

        if supervisor_decisions:
            # Get the selected decision (remember we're working with reversed lists)
            selected_decision = list(reversed(supervisor_decisions))[
                st.session_state.selected_action_index
            ]
            selected_action = list(reversed(actions))[
                st.session_state.selected_action_index
            ]
            action_number = len(actions) - st.session_state.selected_action_index

            # Display the action and reasoning
            st.markdown(f"### Action #{action_number}: `{selected_action}`")

            # Show the reasoning
            if (
                "decision_reasoning" in selected_decision
                and selected_decision["decision_reasoning"]
            ):
                st.markdown("**Reasoning:**")
                st.markdown(selected_decision["decision_reasoning"])
            else:
                st.info("No detailed reasoning available for this action.")

            # Show additional context in an expander
            with st.expander("📊 System Context at Decision Time"):
                context_cols = st.columns(2)

                with context_cols[0]:
                    st.markdown("**Research Metrics:**")
                    st.write(
                        f"• Total Hypotheses: {selected_decision.get('total_hypotheses', 'N/A')}"
                    )
                    st.write(
                        f"• Unranked Hypotheses: {selected_decision.get('num_unranked_hypotheses', 'N/A')}"
                    )
                    st.write(
                        f"• Meta-Reviews: {selected_decision.get('num_meta_reviews', 'N/A')}"
                    )
                    st.write(
                        f"• Literature Subtopics: {selected_decision.get('literature_review_subtopics_completed', 'N/A')}"
                    )

                with context_cols[1]:
                    st.markdown("**Tournament Metrics:**")
                    st.write(
                        f"• Total Matches: {selected_decision.get('total_matches_played', 'N/A')}"
                    )
                    st.write(
                        f"• Tournament Rounds: {selected_decision.get('total_rounds_played', 'N/A')}"
                    )
                    st.write(
                        f"• New Hypotheses Since Meta-Review: {selected_decision.get('new_hypotheses_since_meta_review', 'N/A')}"
                    )

                # Show recent actions context
                if (
                    "latest_actions" in selected_decision
                    and selected_decision["latest_actions"]
                ):
                    st.markdown("**Recent Actions Context:**")
                    st.text(selected_decision["latest_actions"])
        else:
            st.info("No supervisor decisions available to display.")
