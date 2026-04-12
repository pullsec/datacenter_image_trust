class DatacenterImageTrustError(Exception):
    """
    Base exception for all application-specific errors.

    This class should be used to catch all project-related failures
    in a generic and controlled way.
    """

    pass


class ConfigurationError(DatacenterImageTrustError):
    """
    Raised when configuration files or runtime settings are invalid.
    """

    pass


class ProviderError(DatacenterImageTrustError):
    """
    Raised when a distribution provider fails to resolve or construct
    the required artifacts.
    """

    pass


class DownloadError(DatacenterImageTrustError):
    """
    Raised when a remote artifact cannot be downloaded or validated.
    """

    def __init__(self, url: str, message: str) -> None:
        super().__init__(f"Download failed for {url}: {message}")
        self.url = url


class ChecksumVerificationError(DatacenterImageTrustError):
    """
    Raised when checksum validation fails or expected values cannot be found.
    """

    pass


class SignatureVerificationError(DatacenterImageTrustError):
    """
    Raised when GPG signature verification fails.
    """

    pass


class TrustValidationError(DatacenterImageTrustError):
    """
    Raised when trust validation fails (e.g. signer not allowed,
    unapproved domain, unknown fingerprint).
    """

    pass


class UnsupportedArchitectureError(ProviderError):
    """
    Raised when the requested architecture is not supported by the provider.
    """

    pass


class UnsupportedReleaseError(ProviderError):
    """
    Raised when the requested release is not available or cannot be resolved.
    """

    pass


class ArtifactNotFoundError(ProviderError):
    """
    Raised when a required artifact (ISO, checksum, signature)
    cannot be located.
    """

    pass
