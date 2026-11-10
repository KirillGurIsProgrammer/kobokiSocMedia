
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import (
    BASE_DIR,
    DEBOUNCE_SECONDS,
    IGNORED_DIRS,
    IGNORED_FILES,
    IGNORED_EXTENSIONS,
)

from .git_manager import GitManager
from .ai_generator import AICommitGenerator


class AutoCommitHandler(FileSystemEventHandler):
    def __init__(self):
        self.git = GitManager()
        self.ai = AICommitGenerator()
        self.last_change = None

    def is_ignored(self, path):
        try:
            relative = str(
                path.relative_to(BASE_DIR)
            )
        except ValueError:
            return True

        parts = path.relative_to(BASE_DIR).parts

        if any(part in IGNORED_DIRS for part in parts):
            return True

        if path.name in IGNORED_FILES:
            return True

        if path.suffix in IGNORED_EXTENSIONS:
            return True

        return False

    def on_any_event(self, event):
        if event.is_directory:
            return

        path = getattr(event, "src_path", None)

        if not path:
            return

        path = __import__("pathlib").Path(path)

        if self.is_ignored(path):
            return

        self.last_change = time.monotonic()

    def process_changes(self):
        if not self.git.is_allowed_branch():
            return

        if self.git.has_staged_changes():
            print("[!] Staged changes detected. Skipping.")
            return

        files = self.git.get_changed_files()

        if not files:
            return

        diff = self.git.get_diff(files)

        if not diff.strip():
            return

        print("[*] Generating commit message...")

        message = self.ai.generate(diff)

        if not message:
            print("[!] AI did not generate a valid message.")
            return

        print(f"[*] Commit message: {message}")

        self.git.commit(files, message)

        print("[+] Commit created successfully.")

    def run(self):
        observer = Observer()

        observer.schedule(
            self,
            str(BASE_DIR),
            recursive=True,
        )

        observer.start()

        print("[+] AutoCommit started.")
        print(f"[*] Watching: {BASE_DIR}")
        print("[*] Press CTRL+C to stop.")

        try:
            while True:
                time.sleep(1)

                if self.last_change is None:
                    continue

                elapsed = (
                    time.monotonic() - self.last_change
                )

                if elapsed < DEBOUNCE_SECONDS:
                    continue

                
                self.last_change = None

                try:
                    self.process_changes()
                except Exception as error:
                    print(f"[!] AutoCommit error: {error}")


        except KeyboardInterrupt:
            print("\n[*] Stopping AutoCommit...")

        finally:
            observer.stop()
            observer.join()


if __name__ == "__main__":
    AutoCommitHandler().run()