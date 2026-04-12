from __future__ import annotations

import hashlib
from pathlib import Path

from datacenter_image_trust.exceptions import ChecksumVerificationError
from datacenter_image_trust.models import ChecksumVerificationResult


DEFAULT_BUFFER_SIZE = 1024 * 1024


def verify_sha256(
    iso_path: Path,
    manifest_path: Path,
) -> ChecksumVerificationResult:
    """
    Verify an ISO against a SHA256 manifest file stored on disk.
    """
    if not iso_path.is_file():
        raise ChecksumVerificationError(f"ISO file not found: {iso_path}")

    if not manifest_path.is_file():
        raise ChecksumVerificationError(f"Checksum manifest not found: {manifest_path}")

    manifest_text = manifest_path.read_text(encoding="utf-8")
    return verify_sha256_from_text(
        iso_path=iso_path,
        manifest_text=manifest_text,
    )


def verify_sha256_from_text(
    iso_path: Path,
    manifest_text: str,
) -> ChecksumVerificationResult:
    """
    Verify an ISO against a SHA256 manifest provided as text.
    """
    if not iso_path.is_file():
        raise ChecksumVerificationError(f"ISO file not found: {iso_path}")

    expected_checksum = _extract_expected_sha256(
        manifest_text=manifest_text,
        target_filename=iso_path.name,
    )

    if not expected_checksum:
        raise ChecksumVerificationError(
            f"No SHA256 entry found for ISO in checksum manifest: {iso_path.name}"
        )

    actual_checksum = _compute_sha256(iso_path)

    is_valid = expected_checksum.lower() == actual_checksum.lower()

    return ChecksumVerificationResult(
        is_valid=is_valid,
        algorithm="sha256",
        expected=expected_checksum,
        actual=actual_checksum,
        status_message=(
            "SHA256 checksum verification succeeded"
            if is_valid
            else "SHA256 checksum verification failed"
        ),
    )


def _extract_expected_sha256(
    manifest_text: str,
    target_filename: str,
) -> str:
    """
    Extract the expected SHA256 checksum for a specific file.

    Supports formats such as:
    - "<hash>  filename"
    - "SHA256 (filename) = <hash>"
    """
    for raw_line in manifest_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Format: SHA256 (filename) = <hash>
        prefix = f"SHA256 ({target_filename}) = "
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()

        parts = line.split()
        if len(parts) >= 2:
            candidate_filename = parts[-1].lstrip("*").strip()
            if candidate_filename == target_filename:
                return parts[0].strip()

    return ""


def _compute_sha256(file_path: Path) -> str:
    """
    Compute the SHA256 checksum of a file.
    """
    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        while chunk := handle.read(DEFAULT_BUFFER_SIZE):
            digest.update(chunk)

    return digest.hexdigest()
