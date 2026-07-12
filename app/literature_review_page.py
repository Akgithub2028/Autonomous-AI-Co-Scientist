import streamlit as st


def display_literature_review_page(state):
    """
    Display the literature review page.

    Parameters
    ----------
    state : CoscientistState
        The loaded Coscientist state containing literature review data
    """
    st.header("📚 Literature Review")

    # Check if we have literature review data
    if not hasattr(state, "literature_review") or not state.literature_review:
        st.warning("No literature review found in this research state.")
        st.markdown("""
        ## Literature Review Page
        
        This page displays the comprehensive literature review conducted for the research:
        
        - **Research Subtopics**: Systematic decomposition of the main research goal
        - **Subtopic Reports**: Detailed literature analysis for each research area
        - **Knowledge Foundation**: Scientific background that informs hypothesis generation
        - **Research Context**: Current state of knowledge in relevant fields
        
        The literature review is one of the first steps in the research process, providing
        the scientific foundation for generating well-informed research hypotheses.
        """)
        return

    # Get literature review data
    literature_review = state.literature_review
    subtopics = literature_review.get("subtopics", [])
    subtopic_reports = literature_review.get("subtopic_reports", [])

    # Verify data consistency
    if len(subtopics) != len(subtopic_reports):
        st.error(
            f"Data inconsistency: {len(subtopics)} subtopics but {len(subtopic_reports)} reports"
        )
        return

    if not subtopics:
        st.warning("Literature review exists but contains no subtopics.")
        return

    # Create main layout
    st.markdown(f"**Research Goal:** {state.goal}")
    st.markdown(f"**Total Subtopics:** {len(subtopics)}")

    # Subtopic selection dropdown
    st.subheader("🔍 Select Subtopic")

    # Initialize session state for selected subtopic
    if "selected_subtopic_index" not in st.session_state:
        st.session_state.selected_subtopic_index = 0

    # Create dropdown with subtopics
    selected_index = st.selectbox(
        "Choose a research subtopic:",
        range(len(subtopics)),
        format_func=lambda x: f"{x+1}. {subtopics[x]}",
        index=st.session_state.selected_subtopic_index,
        key="subtopic_selector",
    )

    # Update session state when selection changes
    if selected_index != st.session_state.selected_subtopic_index:
        st.session_state.selected_subtopic_index = selected_index

    # Display selected subtopic and report
    st.subheader("📖 Subtopic Report")

    selected_subtopic = subtopics[selected_index]
    selected_report = subtopic_reports[selected_index]

    # Show subtopic header
    st.markdown(f"### {selected_index + 1}. {selected_subtopic}")

    # Display the report content
    if selected_report:
        # Create a scrollable container for the markdown content
        with st.container():
            st.markdown(selected_report)
    else:
        st.info("No report content available for this subtopic.")

    # Show navigation help and summary stats
    with st.expander("📊 Literature Review Summary"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Review Statistics:**")
            st.write(f"• Total Subtopics: {len(subtopics)}")
            st.write(f"• Current Selection: #{selected_index + 1}")
            st.write(f"• Reports Available: {len([r for r in subtopic_reports if r])}")

        with col2:
            st.markdown("**Navigation:**")
            st.write("• Use the dropdown above to browse subtopics")
            st.write("• Each subtopic represents a focused research area")
            st.write("• Reports provide scientific context for hypothesis generation")

        # Show all subtopics as a quick reference
        st.markdown("**All Research Subtopics:**")
        for i, subtopic in enumerate(subtopics):
            marker = "🔹" if i == selected_index else "◦"
            st.write(f"{marker} {i+1}. {subtopic}")
