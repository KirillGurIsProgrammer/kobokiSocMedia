
import subprocess

from pathlib import Path

from .config import (
    BASE_DIR,
    PROTECTED_BRANCHES,
    IGNORED_DIRS,
    IGNORED_FILES,
    IGNORED_EXTENSIONS,
)


class GitManager:
    def __init__(self):
        self.root = BASE_DIR

    def run(self, *args):
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

        return result.stdout.strip()

    def get_branch(self):
        return self.run("branch", "--show-current")

    def is_allowed_branch(self):
        branch = self.get_branch()

        if not branch:
            return False

        return branch not in PROTECTED_BRANCHES

    def get_status(self):
        return self.run(
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )

    
    def has_staged_changes(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.root,
            capture_output=True,
        )

        if result.returncode not in (0, 1):
            raise RuntimeError("Failed to inspect Git index")

        return result.returncode == 1


    def is_ignored(self, path):
        path = Path(path)

        if any(part in IGNORED_DIRS for part in path.parts):
            return True

        if path.name in IGNORED_FILES:
            return True

        if path.suffix in IGNORED_EXTENSIONS:
            return True

        return False

    def get_changed_files(self):
        status = self.get_status()
        changed_files = []

        for line in status.splitlines():
            if len(line) < 4:
                continue

            state = line[:2]
            filename = line[3:]

            # Пропускаем staged-изменения и конфликты
            if state != "??" and (
                state[0] != " " or state[1] == "U"
            ):
                continue

            if self.is_ignored(filename):
                continue

            changed_files.append(filename)

        return changed_files

    def get_diff(self, files):
        parts = []

        for filename in files:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--no-ext-diff",
                    "--no-color",
                    "--",
                    filename,
                ],
                cwd=self.root,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                continue

            if result.stdout:
                parts.append(result.stdout)
                continue

            # git diff не показывает содержимое новых файлов
            path = self.root / filename

            if path.is_file():
                try:
                    content = path.read_text(
                        encoding="utf-8"
                    )
                    parts.append(
                        f"New file: {filename}\n{content}"
                    )
                except (UnicodeDecodeError, OSError):
                    parts.append(
                        f"New binary or unreadable file: {filename}"
                    )

        return "\n".join(parts)

    def commit(self, files, message):
        if not self.is_allowed_branch():
            raise RuntimeError("Protected branch")

        if self.has_staged_changes():
            raise RuntimeError(
                "There are already staged changes. "
                "Commit cancelled."
            )

        for filename in files:
            self.run("add", "--", filename)

        if self.has_staged_changes():
            self.run("commit", "-m", message)
            return True

        return False