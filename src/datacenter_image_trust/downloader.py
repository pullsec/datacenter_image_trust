from __future__ import annotations

import logging
import sys
from pathlib import Path

import requests

from datacenter_image_trust.exceptions import DownloadError
from datacenter_image_trust.models import RemoteArtifact


LOGGER = logging.getLogger(__name__)


def download_artifacts(
    artifacts: list[RemoteArtifact],
    timeout: int = 30,
    chunk_size: int = 1024 * 1024,
    force: bool = False,
) -> None:
    """
    Download multiple remote artifacts with progress display.
    """
    for artifact in artifacts:
        _download_single(
            artifact=artifact,
            timeout=timeout,
            chunk_size=chunk_size,
            force=force,
        )


def _download_single(
    artifact: RemoteArtifact,
    timeout: int,
    chunk_size: int,
    force: bool,
) -> None:
    """
    Download a single artifact with progress reporting.
    """
    target_path = artifact.local_path

    if target_path.exists() and not force:
        LOGGER.info("Skipping download (already exists): %s", target_path)
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Downloading: %s", artifact.url)

    try:
        with requests.get(artifact.url, stream=True, timeout=timeout) as response:
            response.raise_for_status()

            total_size = int(response.headers.get("Content-Length", 0))

            with open(target_path, "wb") as handle:
                downloaded = 0

                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue

                    handle.write(chunk)
                    downloaded += len(chunk)

                    _print_progress(
                        filename=target_path.name,
                        downloaded=downloaded,
                        total=total_size,
                    )

        # newline after progress
        sys.stdout.write("\n")
        sys.stdout.flush()

    except requests.RequestException as exc:
        raise DownloadError(
            f"Download failed for {artifact.url}: {exc}"
        ) from exc


def _print_progress(filename: str, downloaded: int, total: int) -> None:
    """
    Print progress to stdout (inline updating).
    """
    if total > 0:
        percent = downloaded / total * 100
        progress_line = (
            f"\rDownloading {filename} "
            f"{_format_size(downloaded)} / {_format_size(total)} "
            f"({percent:5.1f}%)"
        )
    else:
        progress_line = (
            f"\rDownloading {filename} {_format_size(downloaded)}"
        )

    sys.stdout.write(progress_line)
    sys.stdout.flush()


def _format_size(size: int) -> str:
    """
    Human readable size formatting.
    """
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PiB"
