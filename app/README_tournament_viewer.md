# Coscientist Viewer App

A comprehensive Streamlit application for visualizing and exploring Coscientist research results, including tournament rankings and semantic proximity graphs.

## Features

### 🏆 Tournament Rankings Page
- **ELO Rating System**: View hypotheses ranked by their tournament performance
- **Detailed Hypothesis View**: Explore individual hypotheses with full context
- **Match History**: See complete debate transcripts between competing hypotheses
- **Hypothesis Lineage**: Track which hypotheses evolved from others
- **Win-Loss Records**: Performance statistics for each hypothesis

### 📊 Proximity Graph Page
- **Interactive Network Visualization**: Explore semantic relationships between hypotheses
- **Community Detection**: Automatically discover groups of similar hypotheses using Louvain clustering
- **Hover Interactions**: View full hypothesis descriptions by hovering over nodes
- **Adjustable Parameters**: Control community detection sensitivity and edge filtering
- **Graph Statistics**: View network metrics including node count, edges, and average similarity

## Installation

```bash
pip install -r viewer_requirements.txt
```

## Usage

### Starting the App

```bash
streamlit run tournament_viewer.py
```

### Loading Data

1. **Recent Files**: Select from automatically discovered Coscientist state files
2. **File Upload**: Upload a `.pkl` state file directly through the interface

### Navigation

Use the sidebar to switch between:
- **Tournament Rankings**: Competitive analysis of hypotheses
- **Proximity Graph**: Semantic similarity visualization

## Proximity Graph Features

### Interactive Visualization
- **Nodes**: Represent individual hypotheses
- **Edges**: Show cosine similarity between hypothesis embeddings
- **Colors**: Different colors indicate semantic communities
- **Layout**: Spring-force layout for optimal node positioning

### Community Detection Controls
- **Resolution**: Higher values create more, smaller communities
- **Minimum Edge Weight**: Filter weak connections for cleaner clustering

### Graph Statistics
- **Number of Hypotheses**: Total nodes in the graph
- **Number of Connections**: Total edges between hypotheses
- **Average Similarity**: Mean cosine similarity across all connections

## Data Requirements

The app expects Coscientist state files (`.pkl`) containing:
- **Tournament data**: For rankings and match analysis
- **Proximity graph**: For semantic similarity visualization
- **Reviewed hypotheses**: With detailed reasoning and predictions

## Technical Details

### Visualization Libraries
- **Plotly**: Interactive graph visualization with zoom, pan, and hover
- **NetworkX**: Graph processing and community detection algorithms
- **Streamlit**: Web application framework

### Graph Layout
- Uses spring-force layout algorithm for optimal node positioning
- Nodes are sized uniformly but could be weighted by ELO rating
- Edge opacity indicates connection strength

### Community Detection
- Louvain method for community detection
- Configurable resolution parameter
- Edge filtering by minimum weight threshold

## File Structure

```
app/
├── tournament_viewer.py      # Main application with both pages
├── viewer_requirements.txt   # Python dependencies
└── README_tournament_viewer.md  # This documentation
```

## Dependencies

- `streamlit>=1.28.0`: Web application framework
- `pandas>=2.0.0`: Data manipulation and analysis
- `plotly>=5.0.0`: Interactive visualizations
- `networkx>=3.0`: Graph processing and algorithms

## Tips for Best Results

### Tournament Page
- Use the detailed view to understand hypothesis evolution
- Check match history to see reasoning behind rankings
- Look for patterns in win-loss records

### Proximity Graph Page
- Adjust resolution to find meaningful community sizes
- Increase minimum edge weight to focus on strongest similarities
- Hover over nodes to quickly compare similar hypotheses
- Use the zoom and pan features to explore dense areas

## Troubleshooting

### Common Issues
- **Empty Graph**: Check that the state file contains proximity graph data
- **No Communities**: Try lowering the minimum edge weight or resolution
- **Performance**: Large graphs (>50 nodes) may be slow to render

### File Format Requirements
- State files must be valid Python pickle files
- Must contain either tournament or proximity_graph data
- Compatible with Coscientist framework output format

## Future Enhancements

Potential improvements could include:
- Node sizing based on ELO ratings or other metrics
- Edge thickness proportional to similarity strength
- Filtering by community or hypothesis attributes
- Export functionality for graphs and rankings
- Additional layout algorithms (circular, hierarchical, etc.) 