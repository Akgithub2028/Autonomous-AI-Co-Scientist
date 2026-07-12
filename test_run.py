import asyncio
from coscientist.graphs.framework import CoscientistFramework
from coscientist.configs.config import settings

def main():
    print("Testing framework initialization...")
    # Reduce settings for faster test
    settings.LITERATURE_MAX_QUERIES = 1
    settings.MAX_DEBATE_TURNS = 1
    settings.MAX_SUBTOPICS = 1
    
    goal = "Are there any promising non-stimulant treatments for ADHD that target the NMDA receptor?"
    
    print(f"Goal: {goal}")
    framework = CoscientistFramework(goal)
    print("Running framework single step...")
    framework.step()
    print("Framework step complete.")
    
if __name__ == "__main__":
    main()
