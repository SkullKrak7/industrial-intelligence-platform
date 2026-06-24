"""Watches predictions.csv for new rows and logs ALERT when anomaly=True.

Runs in a background thread alongside the asyncio telemetry loop.
Uses Observer (inotify) not PollingObserver — bind-mounted Docker volumes
emit inotify events on Linux. Fall back to PollingObserver on macOS.
"""
import os
import threading
import time

import pandas as pd

_BASE            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREDICTIONS_PATH = os.path.join(_BASE, "data", "predictions.csv")


def _read_last_row(path: str) -> dict | None:
    try:
        df = pd.read_csv(path)
        if df.empty:
            return None
        return df.iloc[-1].to_dict()
    except Exception:
        return None


class PredictionsHandler:
    """Called by the watcher thread whenever predictions.csv changes."""

    def __init__(self) -> None:
        self._last_seen: str | None = None

    def on_change(self) -> None:
        row = _read_last_row(PREDICTIONS_PATH)
        if row is None:
            return
        row_key = str(row)
        if row_key == self._last_seen:
            return
        self._last_seen = row_key

        machine_id = row.get("machine_id", "?")
        confidence = row.get("confidence", 0.0)
        anomaly    = str(row.get("anomaly", "False")).lower() in ("true", "1")

        if anomaly:
            print(
                f"[ALERT] machine={machine_id}  confidence={confidence:.4f}  "
                f"→ FAILURE PREDICTED",
                flush=True,
            )
        else:
            print(
                f"[OK]    machine={machine_id}  confidence={confidence:.4f}",
                flush=True,
            )


def _poll_loop(handler: PredictionsHandler, interval_s: float = 2.0) -> None:
    """Fallback polling loop used when watchdog is unavailable."""
    while True:
        if os.path.exists(PREDICTIONS_PATH):
            handler.on_change()
        time.sleep(interval_s)


def start_watcher() -> threading.Thread:
    """Start predictions.csv watcher in a daemon thread.

    Tries inotify-based watchdog first; falls back to polling if unavailable.
    Returns the thread so the caller can join it if needed.
    """
    handler = PredictionsHandler()

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class _WatchdogHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if os.path.abspath(event.src_path) == os.path.abspath(PREDICTIONS_PATH):
                    handler.on_change()

        watch_dir = os.path.dirname(PREDICTIONS_PATH)
        os.makedirs(watch_dir, exist_ok=True)

        observer = Observer()
        observer.schedule(_WatchdogHandler(), path=watch_dir, recursive=False)
        observer.daemon = True
        observer.start()
        print(f"Watchdog (inotify) watching {PREDICTIONS_PATH}", flush=True)
        return observer

    except Exception as e:
        print(f"Watchdog unavailable ({e}), falling back to polling", flush=True)
        t = threading.Thread(
            target=_poll_loop, args=(handler,), daemon=True, name="predictions-poller"
        )
        t.start()
        return t


if __name__ == "__main__":
    # Standalone smoke-test: watch and print changes until Ctrl-C
    thread = start_watcher()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
