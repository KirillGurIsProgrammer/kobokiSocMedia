
import json
import re
import requests

from .config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    MAX_DIFF_LENGTH,
)


class AICommitGenerator:
    def __init__(self):
        self.session = requests.Session()

    def generate(self, diff):
        if not diff.strip():
            return None

        diff = diff[:MAX_DIFF_LENGTH]

        prompt = f"""
Generate one Conventional Commit message based on the Git diff.

Allowed types: feat, fix, refactor, docs, style, test, chore, perf, build.

Rules:
- English only.
- Format: type(scope): description OR type: description.
- Imperative mood.
- One line only.
- No explanations.

Return JSON in this exact format:
{{"message": "docs: update documentation"}}

Git diff:
{diff}
"""

        try:
            response = self.session.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=OLLAMA_TIMEOUT,
            )

            response.raise_for_status()
            data = response.json()

            result = data.get("response", "").strip()

            try:
                parsed = json.loads(result)
                message = parsed.get("message", "")
            except json.JSONDecodeError:
                message = result

            message = message.strip().strip('"').strip()

            if not re.fullmatch(
                r"(feat|fix|refactor|docs|style|test|chore|perf|build)"
                r"(\([a-zA-Z0-9._/-]+\))?: .{1,72}",
                message,
            ):
                print(f"[!] Invalid AI message: {message!r}")
                return None

            return message

        except (requests.RequestException, ValueError, TypeError) as error:
            print(f"[!] Ollama error: {error}")
            return None