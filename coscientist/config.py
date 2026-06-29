import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # API Keys
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Model routing
    STRONG_MODEL: str = os.getenv("STRONG_MODEL", "gemini-3.1-pro-preview")
    FAST_MODEL: str = os.getenv("FAST_MODEL", "gemini-3.1-pro-preview")
    MAX_STRONG_TOKENS: int = int(os.getenv("MAX_STRONG_TOKENS", "4000"))
    MAX_FAST_TOKENS: int = int(os.getenv("MAX_FAST_TOKENS", "2000"))

    # Workflow limits
    INITIAL_HYPOTHESES: int = int(os.getenv("INITIAL_HYPOTHESES", "2"))
    MAX_HYPOTHESES: int = int(os.getenv("MAX_HYPOTHESES", "4"))
    TOURNAMENT_BRACKET_K: int = int(os.getenv("TOURNAMENT_BRACKET_K", "2"))
    MAX_SUBTOPICS: int = int(os.getenv("MAX_SUBTOPICS", "1"))
    MAX_EVOLUTION_CANDIDATES: int = int(os.getenv("MAX_EVOLUTION_CANDIDATES", "1"))
    MAX_DEBATE_TURNS: int = int(os.getenv("MAX_DEBATE_TURNS", "1"))
    
    # Rate limiting
    REQUESTS_PER_MINUTE: int = int(os.getenv("REQUESTS_PER_MINUTE", "10"))
    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "5.0"))

    # Safety and Oversight
    REQUIRE_HUMAN_APPROVAL: bool = os.getenv("REQUIRE_HUMAN_APPROVAL", "True").lower() in ("true", "1", "t")

settings = Settings()
