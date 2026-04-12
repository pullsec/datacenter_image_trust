from __future__ import annotations

from abc import ABC, abstractmethod

from datacenter_image_trust.models import UbuntuReleaseArtifacts, UbuntuReleaseRequest


class BaseProvider(ABC):
    """
    Define the common interface for all distribution providers.

    A provider is responsible for translating a high-level user request
    into a fully-resolved set of remote artifacts that can later be
    downloaded and verified.

    Each provider must:
    - validate the requested release and architecture,
    - build the official upstream URLs,
    - define the local storage paths for all required artifacts.
    """

    name: str

    @abstractmethod
    def build_release_artifacts(
        self,
        request: UbuntuReleaseRequest,
    ) -> UbuntuReleaseArtifacts:
        """
        Resolve all artifacts required for a distribution release.

        Args:
            request: User request describing the target release.

        Returns:
            A fully-populated artifact bundle for the requested release.

        Raises:
            ProviderError: If the provider cannot resolve the requested release.
        """
        raise NotImplementedError
