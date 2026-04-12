from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from datacenter_image_trust.exceptions import TrustValidationError
from datacenter_image_trust.models import TrustValidationResult


def validate_artifact_url(url: str, allowed_hosts: set[str]) -> str:
    """
    Validate that a remote artifact URL belongs to an approved hostname.

    Args:
        url: Remote artifact URL.
        allowed_hosts: Set of approved hostnames.

    Returns:
        Validated hostname.

    Raises:
        TrustValidationError: If the URL is invalid or the hostname is not allowed.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise TrustValidationError(
            f"Untrusted URL scheme detected for remote artifact: {url}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise TrustValidationError(
            f"Missing hostname in remote artifact URL: {url}"
        )

    if hostname not in allowed_hosts:
        raise TrustValidationError(
            f"Remote hostname is not part of the approved allowlist: {hostname}"
        )

    return hostname


def load_allowed_fingerprints(fingerprints_file_path: Path) -> set[str]:
    """
    Load allowed signer fingerprints from a local policy file.

    The file may contain empty lines and comment lines prefixed with '#'.

    Args:
        fingerprints_file_path: Path to the local fingerprint allowlist file.

    Returns:
        Set of normalized uppercase fingerprints.

    Raises:
        TrustValidationError: If the fingerprint policy file cannot be read.
    """
    if not fingerprints_file_path.is_file():
        raise TrustValidationError(
            f"Fingerprint allowlist file not found: {fingerprints_file_path}"
        )

    try:
        raw_lines = fingerprints_file_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TrustValidationError(
            f"Failed to read fingerprint allowlist: {fingerprints_file_path}: {exc}"
        ) from exc

    fingerprints: set[str] = set()

    for raw_line in raw_lines:
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        fingerprints.add(line.upper())

    return fingerprints


def validate_signer_fingerprint(
    signer_fingerprint: str | None,
    allowed_fingerprints: set[str],
) -> None:
    """
    Validate that a signer fingerprint is explicitly allowed by local policy.

    Args:
        signer_fingerprint: Fingerprint extracted from signature verification output.
        allowed_fingerprints: Set of approved fingerprints.

    Raises:
        TrustValidationError: If the fingerprint is missing or not approved.
    """
    if not signer_fingerprint:
        raise TrustValidationError(
            "Signer fingerprint is missing from signature verification result"
        )

    normalized_fingerprint = signer_fingerprint.upper()

    if normalized_fingerprint not in allowed_fingerprints:
        raise TrustValidationError(
            f"Signer fingerprint is not approved by local policy: "
            f"{normalized_fingerprint}"
        )


def validate_trust_policy(
    artifact_url: str,
    allowed_hosts: set[str],
    signer_fingerprint: str | None,
    fingerprints_file_path: Path,
) -> TrustValidationResult:
    """
    Validate local trust policy for a downloaded artifact.

    This function enforces:
    - approved HTTPS remote host,
    - approved signer fingerprint.

    Args:
        artifact_url: Remote artifact URL used for download.
        allowed_hosts: Set of approved hostnames.
        signer_fingerprint: Fingerprint reported by signature verification.
        fingerprints_file_path: Path to the local fingerprint allowlist file.

    Returns:
        Structured trust validation result.

    Raises:
        TrustValidationError: If trust policy validation fails.
    """
    validated_hostname = validate_artifact_url(
        url=artifact_url,
        allowed_hosts=allowed_hosts,
    )
    allowed_fingerprints = load_allowed_fingerprints(fingerprints_file_path)
    validate_signer_fingerprint(
        signer_fingerprint=signer_fingerprint,
        allowed_fingerprints=allowed_fingerprints,
    )

    return TrustValidationResult(
        is_trusted=True,
        validated_hostname=validated_hostname,
        signer_fingerprint=signer_fingerprint.upper() if signer_fingerprint else None,
        status_message="Local trust policy validation succeeded",
    )
