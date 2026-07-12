import streamlit as st
from st_cytoscape import cytoscape


def create_cytoscape_elements(graph, communities):
    """Convert NetworkX graph to Cytoscape elements format."""
    if graph is None or len(graph.nodes()) == 0:
        return [], []

    G = graph

    # Create color mapping for communities
    colors = [
        "#FF6B6B",
        "#4ECDC4",
        "#45B7D1",
        "#96CEB4",
        "#FFEAA7",
        "#DDA0DD",
        "#98D8C8",
        "#FFA07A",
        "#B19CD9",
        "#FFB6C1",
    ]
    community_colors = {}
    for i, community in enumerate(communities):
        color = colors[i % len(colors)]
        for node_id in community:
            community_colors[node_id] = color

    # Create nodes
    elements = []

    for node_id in G.nodes():
        hypothesis_text = G.nodes[node_id].get("hypothesis", f"Hypothesis {node_id}")

        # Truncate for label but keep full text for tooltip
        label = f"H{node_id}"
        if len(hypothesis_text) > 80:
            tooltip = hypothesis_text[:80] + "..."
        else:
            tooltip = hypothesis_text

        elements.append(
            {
                "data": {
                    "id": str(node_id),
                    "label": label,
                    "hypothesis": hypothesis_text,
                    "tooltip": tooltip,
                },
                "classes": f"community-{hash(community_colors.get(node_id, colors[0])) % 10}",
            }
        )

    # Create edges
    for edge in G.edges(data=True):
        weight = edge[2].get("weight", 0)
        elements.append(
            {
                "data": {
                    "id": f"{edge[0]}-{edge[1]}",
                    "source": str(edge[0]),
                    "target": str(edge[1]),
                    "weight": weight,
                }
            }
        )

    # Create stylesheet
    node_styles = []
    for i in range(10):  # Create styles for 10 different community classes
        color = colors[i % len(colors)]
        node_styles.append(
            {
                "selector": f".community-{i}",
                "style": {
                    "background-color": color,
                    "border-width": 2,
                    "border-color": "#ffffff",
                    "color": "#ffffff",
                    "text-valign": "center",
                    "text-halign": "center",
                    "font-size": "12px",
                    "font-weight": "bold",
                    "width": 50,
                    "height": 50,
                },
            }
        )

    stylesheet = [
        {
            "selector": "node",
            "style": {
                "content": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": "12px",
                "font-weight": "bold",
                "width": 50,
                "height": 50,
                "border-width": 2,
                "border-color": "#ffffff",
            },
        },
        {
            "selector": "edge",
            "style": {
                "width": 2,
                "line-color": "#cccccc",
                "opacity": 0.6,
                "curve-style": "bezier",
            },
        },
        {
            "selector": "node:selected",
            "style": {
                "border-width": 4,
                "border-color": "#333333",
                "background-color": "#333333",
            },
        },
        {
            "selector": "edge:selected",
            "style": {"line-color": "#333333", "width": 4, "opacity": 1.0},
        },
    ] + node_styles

    return elements, stylesheet


def display_proximity_graph_page(state):
    """Display the proximity graph page."""
    st.markdown(
        "Explore the semantic similarity between hypotheses and their communities."
    )

    if state is None:
        st.info(
            "👈 Please select or upload a Coscientist state file from the sidebar to view the proximity graph."
        )
        return

    if state.proximity_graph is None:
        st.warning("No proximity graph data found in this state file.")
        return

    proximity_graph = state.proximity_graph

    if len(proximity_graph.graph.nodes()) == 0:
        st.warning(
            "The proximity graph is empty - no hypotheses have been added to it yet."
        )
        return

    # Community detection controls
    st.subheader("Graph Filtering & Community Detection")
    col1, col2 = st.columns(2)

    with col1:
        resolution = st.slider(
            "Resolution (higher = more communities)",
            min_value=0.1,
            max_value=2.0,
            value=1.0,
            step=0.1,
            help="Controls the size of communities. Higher values create more, smaller communities.",
        )

    with col2:
        min_weight = st.slider(
            "Minimum Edge Weight",
            min_value=0.0,
            max_value=1.0,
            value=0.85,
            step=0.05,
            help="Only edges with similarity above this threshold will be shown in the graph.",
        )

    # Get pruned graph based on minimum edge weight
    pruned_graph = proximity_graph.get_pruned_graph(min_weight)

    # Display updated graph statistics
    num_nodes = len(pruned_graph.nodes())
    num_edges = len(pruned_graph.edges())

    # Show warning if graph is too filtered
    if num_nodes == 0:
        st.warning(
            f"⚠️ No hypotheses remain after filtering with minimum edge weight {min_weight:.2f}. Try lowering the threshold."
        )
        return
    elif num_edges == 0:
        st.warning(
            f"⚠️ No connections remain after filtering with minimum edge weight {min_weight:.2f}. The graph will show isolated nodes."
        )

    # Calculate average similarity for pruned graph
    if num_edges > 0:
        edge_weights = [
            data.get("weight", 0) for _, _, data in pruned_graph.edges(data=True)
        ]
        avg_similarity = sum(edge_weights) / len(edge_weights)
    else:
        avg_similarity = 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Hypotheses (Filtered)", num_nodes)
    with col2:
        st.metric("Connections (Filtered)", num_edges)
    with col3:
        st.metric("Avg Similarity (Filtered)", f"{avg_similarity:.3f}")

    # Get communities from pruned graph
    communities = proximity_graph.get_semantic_communities(
        resolution=resolution, min_weight=min_weight
    )

    st.subheader(f"Semantic Communities ({len(communities)} found)")

    # Display communities
    if communities:
        for i, community in enumerate(communities):
            with st.expander(f"Community {i+1} ({len(community)} hypotheses)"):
                for node_id in community:
                    hypothesis_text = pruned_graph.nodes[node_id].get(
                        "hypothesis", f"Hypothesis {node_id}"
                    )
                    st.markdown(f"**H{node_id}:** {hypothesis_text}")
    else:
        st.info(
            "No communities detected with current settings. Try lowering the minimum edge weight or adjusting the resolution parameter."
        )

    # Create and display the visualization
    st.subheader("Interactive Graph Visualization")

    # Convert to Cytoscape format using the pruned graph
    elements, stylesheet = create_cytoscape_elements(pruned_graph, communities)

    if elements:
        # Layout options
        layout_options = {
            "name": "fcose",
            "animationDuration": 1000,
            "fit": True,
            "padding": 50,
            "nodeSeparation": 100,
            "idealEdgeLength": 100,
            "edgeElasticity": 0.1,
            "nestingFactor": 0.1,
            "numIter": 1000,
            "initialEnergyOnIncremental": 0.3,
            "gravityRangeCompound": 1.5,
            "gravityCompound": 1.0,
            "gravityRange": 3.8,
        }

        # Create the Cytoscape graph (key includes min_weight for reactivity)
        selected = cytoscape(
            elements=elements,
            stylesheet=stylesheet,
            layout=layout_options,
            selection_type="additive",
            width="100%",
            height="600px",
            key=f"proximity_graph_{min_weight}_{resolution}",
        )

        # Display information about selected nodes
        if selected and (selected["nodes"] or selected["edges"]):
            st.subheader("🎯 Selected Elements")

            if selected["nodes"]:
                st.markdown("**Selected Hypotheses:**")
                for node_id in selected["nodes"]:
                    # Find the corresponding element to get the full hypothesis
                    for element in elements:
                        if element["data"]["id"] == node_id:
                            hypothesis_text = element["data"]["hypothesis"]
                            st.markdown(f"**H{node_id}:** {hypothesis_text}")
                            break

            if selected["edges"]:
                st.markdown(
                    f"**Selected Connections:** {len(selected['edges'])} edge(s)"
                )

        # Additional information
        st.info("""
        **How to interact with the graph:**
        - **Click nodes** to select them and see full hypothesis text below
        - **Drag nodes** to rearrange the layout
        - **Zoom and pan** to explore different areas
        - **Different colors** represent different semantic communities
        - **Hold Ctrl/Cmd + click** to select multiple nodes
        - **Double-click empty space** to fit the graph to view
        - **Adjust sliders above** to dynamically filter the graph and update communities
        """)

        st.success(
            f"📊 **Graph Status:** Showing {num_nodes} hypotheses and {num_edges} connections with similarity ≥ {min_weight:.2f}"
        )
    else:
        st.error("Could not create visualization. Please check the data.")
