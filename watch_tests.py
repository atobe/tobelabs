# watch_tests.py
import subprocess
import os
import sys
import time
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler


class TestRunnerHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(patterns=["*.py"])

    def on_modified(self, event):
        print(f"Detected change in {event.src_path}. Running tests...")
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{os.getcwd()}:{env.get('PYTHONPATH', '')}"
        subprocess.run(["pytest", "-v"], env=env)
        subprocess.run(["coverage", "run", "-m", "pytest"], env=env)
        subprocess.run(["coverage", "report", "-m"])
        print("Running type checks... (mypy)")
        subprocess.run(["mypy"])


if __name__ == "__main__":
    # Add the current working directory to Python path
    sys.path.insert(0, os.getcwd())

    path = "."
    event_handler = TestRunnerHandler()
    observer = PollingObserver()
    observer.schedule(event_handler, path, recursive=True)
    print("Starting to watch for changes. Press Ctrl+C to stop.")
    observer.start()
    time.sleep(0.5)
    try:
        os.system("touch setup.py")
        while True:
            observer.join(1)
    except KeyboardInterrupt:
        print("Stopping watcher.")
        observer.stop()
    observer.join()
