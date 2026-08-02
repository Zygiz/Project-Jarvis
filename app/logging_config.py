import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure logging once, at app startup.

    Logs go to stdout because Docker captures stdout — that's what
    `docker compose logs api` shows. Never log to files in a container:
    the file would vanish with the container.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,  # override any config a library set up first
    )