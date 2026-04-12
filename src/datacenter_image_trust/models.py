from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class RemoteArtifact:
    """
    Represent a remote file that must be downloaded and stored locally.

    Attributes:
        name: Logical artifact name used internally by the application.
        url: Remote HTTPS URL of the artifact.
        local_path: Local destination path for the downloaded file.
    """

    name: str
    url: str
    local_path: Path


@dataclass(slots=True)
class UbuntuReleaseRequest:
    """
    Describe the Ubuntu image requested by the user.

    Attributes:
        release: Ubuntu release version, such as '24.04.2'.
        architecture: Target CPU architecture, such as 'amd64'.
        image_type: Ubuntu image type, such as 'live-server' or 'desktop'.
    """

    release: str
    architecture: str = "amd64"
    image_type: str = "live-server"


@dataclass(slots=True)
class UbuntuReleaseArtifacts:
    """
    Group all remote artifacts required to validate an Ubuntu image.

    Attributes:
        distribution: Distribution name.
        release: Ubuntu release version.
        architecture: Target CPU architecture.
        image_type: Requested image type.
        base_url: Official base URL used for the release.
        iso: ISO artifact.
        checksums: Checksum manifest artifact.
        signature: Detached signature artifact for the checksum manifest.
    """

    distribution: str
    release: str
    architecture: str
    image_type: str
    base_url: str
    iso: RemoteArtifact
    checksums: RemoteArtifact
    signature: RemoteArtifact


@dataclass(slots=True)
class SignatureVerificationResult:
    """
    Store the result of a detached signature verification operation.

    Attributes:
        is_valid: Whether the signature is cryptographically valid.
        signer_fingerprint: Fingerprint of the signing key if available.
        signer_uid: Human-readable signer identity if available.
        status_message: Verification status message for logs and reporting.
    """

    is_valid: bool
    signer_fingerprint: Optional[str] = None
    signer_uid: Optional[str] = None
    status_message: str = ""


@dataclass(slots=True)
class ChecksumVerificationResult:
    """
    Store the result of a checksum verification operation.

    Attributes:
        is_valid: Whether the computed checksum matches the expected checksum.
        algorithm: Hash algorithm used for verification.
        expected: Expected checksum value from the checksum manifest.
        actual: Computed checksum value from the downloaded ISO.
        status_message: Verification status message for logs and reporting.
    """

    is_valid: bool
    algorithm: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    status_message: str = ""


@dataclass(slots=True)
class TrustValidationResult:
    """
    Store the result of trust policy validation.

    Attributes:
        is_trusted: Whether the signer and source satisfy local trust policy.
        validated_hostname: Hostname checked against the local allowlist.
        signer_fingerprint: Signer fingerprint checked against the local allowlist.
        status_message: Validation status message for logs and reporting.
    """

    is_trusted: bool
    validated_hostname: Optional[str] = None
    signer_fingerprint: Optional[str] = None
    status_message: str = ""


@dataclass(slots=True)
class VerificationReport:
    """
    Aggregate the full verification status for a downloaded Ubuntu ISO.

    Attributes:
        distribution: Distribution name.
        release: Ubuntu release version.
        architecture: Target CPU architecture.
        image_type: Requested image type.
        iso_path: Local path of the downloaded ISO.
        signature_result: Detached signature verification result.
        checksum_result: Checksum verification result.
        trust_result: Trust policy validation result.
        success: Final global status.
        details: Additional operational details for reporting or debugging.
    """

    distribution: str
    release: str
    architecture: str
    image_type: str
    iso_path: Path
    signature_result: SignatureVerificationResult
    checksum_result: ChecksumVerificationResult
    trust_result: TrustValidationResult
    success: bool
    details: dict[str, str] = field(default_factory=dict)
