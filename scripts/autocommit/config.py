
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

# Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:latest"
OLLAMA_TIMEOUT = 120

# Watcher
DEBOUNCE_SECONDS = 10

# Git
PROTECTED_BRANCHES = {"main", "master"}

# Ignored directories
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "node_modules",
    "media",
    "staticfiles",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

# Ignored files
IGNORED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    "db.sqlite3",
}

# Ignored extensions
IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".log",
    ".sqlite3",
    ".db",
    ".dump",
    ".backup",
    ".pem",
    ".key",
}

MAX_DIFF_LENGTH = 20000