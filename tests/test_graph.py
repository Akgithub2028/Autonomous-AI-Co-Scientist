import pytest
from coscientist.graphs.framework import CoscientistFramework
from coscientist.configs.config import settings

def test_config_loaded():
    assert settings.RETRY_MAX_ATTEMPTS > 0
    # Ensuring the correct Puter key format or existence isn't strictly required in CI without env vars,
    # but we can verify the defaults are loaded.
    assert settings.STRONG_MODEL == "gemini-3.5-flash"
    assert settings.FAST_MODEL == "gpt-4o-mini"

def test_framework_initialization():
    framework = CoscientistFramework(goal="Test goal", research_plan_config=None)
    assert framework.state["goal"] == "Test goal"
    assert framework.state["iteration"] == 0
    assert framework.graph is not None
