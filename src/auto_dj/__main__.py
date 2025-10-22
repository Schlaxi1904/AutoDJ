"""Entry points for the Auto-DJ services."""
from __future__ import annotations

import argparse
import logging

import uvicorn

from .audio.engine import AudioEngine
from .config import DEFAULT_CONFIG
from .database.session import Database
from .services.dj_brain import DjBrain
from .services.queue import QueueManager
from .utils.logging import configure_logging
from .web.app import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-DJ service launcher")
    parser.add_argument("service", choices=["web", "engine", "brain"], help="Which service to start")
    args = parser.parse_args()

    configure_logging(DEFAULT_CONFIG.paths.runtime_log_root, DEFAULT_CONFIG.paths.persistent_log_root)

    if args.service == "web":
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
    elif args.service == "engine":
        engine = AudioEngine(DEFAULT_CONFIG.audio)
        engine.start()
        try:
            while True:
                pass
        except KeyboardInterrupt:
            engine.stop()
    elif args.service == "brain":
        db = Database(DEFAULT_CONFIG.database)
        queue = QueueManager(db, DEFAULT_CONFIG.queue_policy)
        brain = DjBrain(DEFAULT_CONFIG)
        logging.getLogger(__name__).info("Brain service initialised", extra={"queue_length": queue.status().remaining_slots})


if __name__ == "__main__":
    main()
