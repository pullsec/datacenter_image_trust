from __future__ import annotations

import re
import subprocess
from pathlib import Path

from datacenter_image_trust.exceptions import SignatureVerificationError
from datacenter_image_trust.models import SignatureVerificationResult


def verify_detached_signature(
    signed_file_path: Path,
    signature_file_path: Path,
    keyring_path: Path,
) -> SignatureVerificationResult:
    """
    Verify a detached GPG signature using gpgv.
    """
    _ensure_file_exists(signed_file_path, "Signed file")
    _ensure_file_exists(signature_file_path, "Signature file")
    _ensure_file_exists(keyring_path, "Keyring file")

    command = [
        "gpgv",
        "--keyring",
        str(keyring_path),
        str(signature_file_path),
        str(signed_file_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise SignatureVerificationError(f"Failed to execute gpgv: {exc}") from exc

    combined_output = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    )

    if result.returncode != 0:
        raise SignatureVerificationError(
            f"GPG signature verification failed: {combined_output}"
        )

    fingerprint = _extract_fingerprint(combined_output)
    uid = _extract_uid(combined_output)

    return SignatureVerificationResult(
        is_valid=True,
        signer_fingerprint=fingerprint,
        signer_uid=uid,
        status_message="Detached GPG signature verification succeeded",
    )


def verify_inline_clearsigned_file(
    signed_file_path: Path,
    keyring_path: Path,
) -> tuple[SignatureVerificationResult, str]:
    """
    Verify an inline clearsigned file using gpgv and return the verified cleartext.
    """
    _ensure_file_exists(signed_file_path, "Signed file")
    _ensure_file_exists(keyring_path, "Keyring file")

    command = [
        "gpgv",
        "--keyring",
        str(keyring_path),
        "--output",
        "-",
        str(signed_file_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise SignatureVerificationError(f"Failed to execute gpgv: {exc}") from exc

    stderr_text = result.stderr.strip()
    stdout_text = result.stdout

    if result.returncode != 0:
        raise SignatureVerificationError(
            f"Inline GPG signature verification failed: {stderr_text}"
        )

    fingerprint = _extract_fingerprint(stderr_text)
    uid = _extract_uid(stderr_text)

    verification_result = SignatureVerificationResult(
        is_valid=True,
        signer_fingerprint=fingerprint,
        signer_uid=uid,
        status_message="Inline GPG signature verification succeeded",
    )

    return verification_result, stdout_text


def _extract_fingerprint(gpg_output: str) -> str:
    """
    Extract the signing key fingerprint or key ID from gpg/gpgv output.
    """
    fingerprint_pattern = re.compile(r"using [A-Z0-9]+ key ([A-F0-9]{16,40})")
    match = fingerprint_pattern.search(gpg_output)
    if match:
        return match.group(1)

    fallback_pattern = re.compile(r"\b([A-F0-9]{40})\b")
    fallback_match = fallback_pattern.search(gpg_output)
    if fallback_match:
        return fallback_match.group(1)

    return ""


def _extract_uid(gpg_output: str) -> str:
    """
    Extract the signer UID from gpg/gpgv output.
    """
    uid_pattern = re.compile(r'Good signature from "([^"]+)"')
    match = uid_pattern.search(gpg_output)
    if match:
        return match.group(1)

    return ""


def _ensure_file_exists(file_path: Path, label: str) -> None:
    if not file_path.is_file():
        raise SignatureVerificationError(f"{label} not found: {file_path}")
