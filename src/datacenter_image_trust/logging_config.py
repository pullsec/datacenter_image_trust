from __future__ import annotations

import logging
import sys


def configure_logging(verbose: bool = False) -> None:
    """
    Configure application logging.

    Args:
        verbose: Enable INFO-level logs when set to True.
    """
    level = logging.INFO if verbose else logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
