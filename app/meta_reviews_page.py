import streamlit as st


def display_meta_reviews_page(state):
    """
    Display the meta-reviews page.

    Parameters
    ----------
    state : CoscientistState
        The loaded Coscientist state containing meta-reviews
    """
    st.header("🔍 Meta-Reviews")

    # Check if we have meta-reviews
    if not hasattr(state, "meta_reviews") or not state.meta_reviews:
        st.warning("No meta-reviews found in this research state.")
        st.markdown("""
        ## Meta-Reviews Page
        
        This page displays the meta-review analyses generated throughout the research process:
        
        - **Strategic Analysis**: Comprehensive review of hypothesis quality and research progress
        - **Pattern Recognition**: Identification of strengths, weaknesses, and knowledge gaps
        - **Research Direction**: Guidance for future hypothesis generation and evolution
        - **Quality Assessment**: Evaluation of tournament results and hypothesis performance
        
        Meta-reviews are generated periodically to analyze the current state of research and guide
        the supervisor agent's strategic decisions about what actions to take next.
        """)
        return

    # Get meta-reviews
    meta_reviews = state.meta_reviews

    # Create two columns: meta-reviews list and content display
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📚 Reviews History")
        st.markdown(f"**Total Meta-Reviews:** {len(meta_reviews)}")

        # Create a container for the scrollable meta-reviews list
        reviews_container = st.container()

        # Initialize session state for selected meta-review
        if "selected_meta_review_index" not in st.session_state:
            st.session_state.selected_meta_review_index = (
                0  # Default to latest meta-review
            )

        with reviews_container:
            # Display meta-reviews in reverse order (latest first) with numbering
            for i, _meta_review in enumerate(reversed(meta_reviews)):
                review_number = len(meta_reviews) - i  # Number from latest to oldest

                # Create a clickable button for each meta-review
                button_key = f"meta_review_{i}"
                button_label = f"Meta-Review #{review_number}"

                # Highlight the selected meta-review
                if i == st.session_state.selected_meta_review_index:
                    st.markdown(f"**🔹 {button_label}**")
                else:
                    if st.button(button_label, key=button_key):
                        st.session_state.selected_meta_review_index = i
                        st.rerun()

    with col2:
        st.subheader("📖 Meta-Review Content")

        if meta_reviews:
            # Get the selected meta-review (remember we're working with reversed list)
            selected_meta_review = list(reversed(meta_reviews))[
                st.session_state.selected_meta_review_index
            ]
            review_number = (
                len(meta_reviews) - st.session_state.selected_meta_review_index
            )

            # Display the meta-review header
            st.markdown(f"### Meta-Review #{review_number}")

            # Show the meta-review content
            meta_review_content = selected_meta_review.get("result", "")
            if meta_review_content:
                st.markdown(meta_review_content)
            else:
                st.info("No content available for this meta-review.")

            # Show additional context in an expander
            with st.expander("📊 Meta-Review Context"):
                context_cols = st.columns(2)

                with context_cols[0]:
                    st.markdown("**Review Information:**")
                    st.write(f"• Review Number: {review_number} of {len(meta_reviews)}")

                    # Show other available fields from the meta-review state
                    if "goal" in selected_meta_review:
                        st.write("• Research Goal Available: ✅")
                    if "top_k" in selected_meta_review:
                        st.write(
                            f"• Top K Analyzed: {selected_meta_review.get('top_k', 'N/A')}"
                        )

                with context_cols[1]:
                    st.markdown("**System State:**")
                    # Show tournament info if available
                    if (
                        "tournament" in selected_meta_review
                        and selected_meta_review["tournament"]
                    ):
                        tournament = selected_meta_review["tournament"]
                        if hasattr(tournament, "hypotheses"):
                            st.write(
                                f"• Hypotheses in Tournament: {len(tournament.hypotheses)}"
                            )
                        try:
                            win_loss_records = tournament.get_win_loss_records()
                            st.write(f"• Ranked Hypotheses: {len(win_loss_records)}")
                        except:  # noqa: E722
                            st.write("• Tournament statistics unavailable")
                    else:
                        st.write("• Tournament data not available")
        else:
            st.info("No meta-reviews available to display.")
