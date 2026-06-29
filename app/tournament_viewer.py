import os

import streamlit as st

# Import from modular pages
from common import (
    get_available_states,
    load_coscientist_state,
    load_coscientist_state_by_goal,
)
from configuration_page import display_configuration_page
from final_report_page import display_final_report_page
from literature_review_page import display_literature_review_page
from meta_reviews_page import display_meta_reviews_page
from proximity_page import display_proximity_graph_page
from resume_page import display_resume_page
from supervisor_page import display_supervisor_page
from tournament_page import display_tournament_page
from evaluation_page import display_evaluation_page

st.set_page_config(page_title="Coscientist Viewer", page_icon="🧪", layout="wide")

# Sidebar navigation
st.sidebar.title("🧪 Coscientist Viewer")
page = st.sidebar.selectbox(
    "Select Page",
    [
        "Configuration Agent",
        "Literature Review",
        "Tournament Rankings",
        "Proximity Graph",
        "Meta-Reviews",
        "Supervisor Decisions",
        "Final Report",
        "Evaluation Benchmark",
        "Resume from Checkpoint",
    ],
)


def main():
    st.title("🧪 Coscientist Viewer")

    # Initialize session state for file selection
    if "current_file" not in st.session_state:
        st.session_state.current_file = None
    if "file_list_updated" not in st.session_state:
        st.session_state.file_list_updated = False

    # Variables for file handling
    selected_file = None
    temp_path = None
    state = None

    # Sidebar for file selection (only for pages that need state files)
    if page in [
        "Literature Review",
        "Tournament Rankings",
        "Proximity Graph",
        "Meta-Reviews",
        "Supervisor Decisions",
        "Final Report",
        "Evaluation Benchmark",
    ]:
        with st.sidebar:
            st.header("📁 Select Research Goal")

            # Update button
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown("**Available Goals:**")
            with col2:
                if st.button("Update", help="Refresh file list and load latest"):
                    st.session_state.file_list_updated = True
                    st.rerun()

            # Get available state files
            available_states = get_available_states()

            # Auto-select most recent file if update was clicked or no file is selected
            if (
                st.session_state.file_list_updated
                or st.session_state.current_file is None
            ):
                if available_states:
                    st.session_state.current_file = available_states[
                        0
                    ]  # Most recent file
                    if st.session_state.file_list_updated:
                        st.success(
                            f"📁 Updated! Latest goal: {available_states[0][:50]}{'...' if len(available_states[0]) > 50 else ''}"
                        )
                st.session_state.file_list_updated = False

            if available_states:
                # Find index of current file in the list (in case files changed)
                current_index = 0
                if st.session_state.current_file in available_states:
                    current_index = available_states.index(
                        st.session_state.current_file
                    )

                selected_file = st.selectbox(
                    "Choose a research goal:",
                    options=available_states,
                    format_func=lambda x: x,  # Display the goal text directly
                    index=current_index,
                    key="file_selector",
                )

                # Update session state when selection changes
                if selected_file != st.session_state.current_file:
                    st.session_state.current_file = selected_file
            else:
                st.warning("No Coscientist research goals found.")
                selected_file = None
                st.session_state.current_file = None

            # File upload option
            st.markdown("**Or upload a file:**")
            uploaded_file = st.file_uploader("Upload .pkl file", type="pkl")

            if uploaded_file is not None:
                # Save uploaded file temporarily
                temp_path = f"temp_{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                selected_file = temp_path

        # Load state if goal is selected
        if selected_file:
            # If it's a temp file (uploaded), use the original function
            if selected_file.startswith("temp_"):
                state = load_coscientist_state(selected_file)
            else:
                # It's a goal text, use the new function
                state = load_coscientist_state_by_goal(selected_file)

    # Display appropriate page based on navigation
    if page == "Configuration Agent":
        display_configuration_page()
    elif page == "Literature Review":
        if state is None:
            st.info(
                "👈 Please select a research goal or upload a Coscientist state file from the sidebar to get started."
            )
            st.markdown("""
            ## Literature Review Page
            
            View the comprehensive literature review that forms the foundation of the research:
            
            1. **Research Subtopics** - see how the main research goal was systematically decomposed
            2. **Subtopic Reports** - select any subtopic to view its detailed literature analysis
            3. **Knowledge Foundation** - understand the scientific background informing hypothesis generation
            
            **What you'll see:**
            - **Dropdown Navigation**: Select from numbered subtopics to explore different research areas
            - **Detailed Reports**: Comprehensive literature analysis for each subtopic
            - **Research Context**: Scientific foundation that guides hypothesis generation
            - **Summary Statistics**: Overview of subtopics covered and reports available
            
            The literature review is one of the first steps in the research process, providing
            the scientific foundation for generating well-informed, evidence-based research hypotheses.
            """)
        else:
            display_literature_review_page(state)
    elif page == "Tournament Rankings":
        if state is None:
            st.info(
                "👈 Please select a research goal or upload a Coscientist state file from the sidebar to get started."
            )
            st.markdown("""
            ## Tournament Rankings Page
            
            View and explore hypotheses ranked by ELO rating:
            
            1. **Browse tournament rankings** - see all hypotheses ranked by ELO rating
            2. **Select a hypothesis** for detailed view to see:
               - Full hypothesis text and predictions
               - Causal reasoning and verification results
               - Assumptions and supporting research
               - Complete match history with debate transcripts
            
            **What you'll see:**
            - **ELO Ratings**: Higher scores indicate stronger performance in head-to-head comparisons
            - **Win-Loss Records**: Track record against other hypotheses
            - **Match History**: Full debate transcripts showing why one hypothesis beat another
            - **Hypothesis Lineage**: See which hypotheses evolved from others
            """)
        else:
            display_tournament_page(state)
    elif page == "Proximity Graph":
        if state is None:
            st.info(
                "👈 Please select a research goal or upload a Coscientist state file from the sidebar to get started."
            )
            st.markdown("""
            ## Proximity Graph Page
            
            Explore the semantic relationships between hypotheses using advanced network visualization:
            
            1. **Interactive Cytoscape.js graph** with hypotheses as nodes and similarities as edges
            2. **Community detection** to find groups of semantically similar hypotheses
            3. **Click nodes** to select them and see full hypothesis text
            4. **Drag and rearrange** nodes to explore relationships
            5. **Adjust parameters** to control community detection sensitivity
            
            **What you'll see:**
            - **Node colors**: Different colors represent different semantic communities
            - **Interactive layout**: Force-directed positioning based on similarity
            - **Edges**: Connections show cosine similarity between hypothesis embeddings
            - **Statistics**: Number of hypotheses, connections, and average similarity
            - **Selection feedback**: Click nodes to see their full hypothesis text below the graph
            
            **Advanced Features:**
            - Multi-node selection with Ctrl/Cmd + click
            - Smooth animations and transitions
            - Professional network graph layout algorithms
            - Real-time interaction feedback
            """)
        else:
            display_proximity_graph_page(state)
    elif page == "Meta-Reviews":
        if state is None:
            st.info(
                "👈 Please select a research goal or upload a Coscientist state file from the sidebar to get started."
            )
            st.markdown("""
            ## Meta-Reviews Page
            
            View the strategic analysis and review process of the research:
            
            1. **Reviews Timeline** - see all meta-reviews generated during the research process
            2. **Strategic Analysis** - click on any meta-review to see the full analysis
            3. **Research Guidance** - understand how each review guided future research directions
            
            **What you'll see:**
            - **Numbered Reviews**: Latest meta-reviews appear first with sequential numbering
            - **Strategic Analysis**: Full text of the meta-review analysis and insights
            - **Research Context**: Tournament state and hypothesis counts at review time
            - **Quality Assessment**: Evaluation of hypothesis performance and research progress
            
            Meta-reviews are generated periodically to analyze the current state of research,
            identify patterns and gaps, and guide the supervisor agent's strategic decisions.
            """)
        else:
            display_meta_reviews_page(state)
    elif page == "Supervisor Decisions":
        if state is None:
            st.info(
                "👈 Please select a research goal or upload a Coscientist state file from the sidebar to get started."
            )
            st.markdown("""
            ## Supervisor Decisions Page
            
            View the decision-making process of the supervisor agent:
            
            1. **Actions Timeline** - see all actions taken by the supervisor in chronological order
            2. **Decision Reasoning** - click on any action to see the detailed reasoning behind it
            3. **System Context** - understand the research state that influenced each decision
            
            **What you'll see:**
            - **Numbered Actions**: Latest actions appear first with sequential numbering
            - **Decision Reasoning**: Full text of the supervisor's strategic thinking
            - **System Metrics**: Research state, hypothesis counts, tournament progress at decision time
            - **Recent Context**: What other actions were taken recently that influenced the decision
            
            The supervisor agent analyzes the research progress and decides what actions to take next,
            such as generating new hypotheses, evolving existing ones, running tournaments, or finishing the research.
            """)
        else:
            display_supervisor_page(state)
    elif page == "Final Report":
        if state is None:
            st.info(
                "👈 Please select a research goal or upload a Coscientist state file from the sidebar to get started."
            )
            st.markdown("""
            ## Final Report Page
            
            View the comprehensive final research report generated upon completion:
            
            1. **Complete Analysis** - comprehensive summary of all research findings
            2. **Top Hypotheses** - detailed review of the highest-ranked hypotheses  
            3. **Research Conclusions** - final insights and recommendations
            4. **Process Summary** - overview of the research methodology and evaluation
            
            **What you'll see:**
            - **Final Report**: Complete research summary and conclusions
            - **Research Statistics**: Overview of hypotheses generated, tournaments run, and key metrics
            - **Process Completion**: Confirmation that the research process finished successfully
            
            The final report is generated only when the supervisor agent determines that the research
            has achieved sufficient depth and quality, and further investigation would yield diminishing returns.
            """)
        else:
            display_final_report_page(state)
    elif page == "Evaluation Benchmark":
        if state is None:
            st.info("👈 Please select a research goal or upload a Coscientist state file from the sidebar to evaluate.")
        else:
            display_evaluation_page(state)
    elif page == "Resume from Checkpoint":
        display_resume_page()

    # Clean up temp file if it was uploaded
    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)


if __name__ == "__main__":
    main()
