"""Opt-in demo rows. Never imported by production migrations."""

from scripts.db.migrate import seed


def load_demo() -> None:
    seed()
