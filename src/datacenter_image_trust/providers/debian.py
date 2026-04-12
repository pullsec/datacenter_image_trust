from __future__ import annotations

import logging
from pathlib import Path
import re

import requests

from datacenter_image_trust.exceptions import (
    ArtifactNotFoundError,
    UnsupportedArchitectureError,
    UnsupportedReleaseError,
)
from datacenter_image_trust.models import (
    RemoteArtifact,
    UbuntuReleaseArtifacts,
    UbuntuReleaseRequest,
)
from datacenter_image_trust.providers.base import BaseProvider


LOGGER = logging.getLogger(__name__)


class DebianProvider(BaseProvider):
    """
    Dynamic Debian ISO provider supporting multiple archived releases.
    """

    name = "debian"

    SUPPORTED_ARCHITECTURES = {"amd64"}
    SUPPORTED_IMAGE_TYPES = {"netinst"}

    SUPPORTED_MAJOR = {"10", "11", "12", "13"}

    CODENAME_MAP = {
        "buster": "10",
        "bullseye": "11",
        "bookworm": "12",
        "trixie": "13",
    }

    BASE_URL = "https://cdimage.debian.org"

    def __init__(self, cache_root: Path, downloads_root: Path) -> None:
        self.cache_root = cache_root
        self.downloads_root = downloads_root

    def build_release_artifacts(
        self,
        request: UbuntuReleaseRequest,
    ) -> UbuntuReleaseArtifacts:
        self._validate_request(request)

        release_major = self._resolve_release_major(request.release)

        base_url = self._resolve_base_url(
            release_major=release_major,
            architecture=request.architecture,
        )

        iso_name = self._discover_iso_filename(
            base_url=base_url,
            architecture=request.architecture,
        )

        return self._build_artifacts_bundle(
            release_major=release_major,
            base_url=base_url,
            architecture=request.architecture,
            image_type=request.image_type,
            iso_name=iso_name,
        )

    def build_selected_release_artifacts(
        self,
        request: UbuntuReleaseRequest,
        selected_filename: str,
    ) -> UbuntuReleaseArtifacts:
        """
        Build artifacts for an explicitly selected Debian ISO filename.
        """
        self._validate_request(request)

        release_major = self._resolve_release_major(request.release)
        base_url = self._resolve_base_url(
            release_major=release_major,
            architecture=request.architecture,
        )

        available_images = self.list_available_images(request)
        if selected_filename not in available_images:
            raise ArtifactNotFoundError(
                f"Selected Debian image is not available for release {request.release}: "
                f"{selected_filename}"
            )

        return self._build_artifacts_bundle(
            release_major=release_major,
            base_url=base_url,
            architecture=request.architecture,
            image_type=request.image_type,
            iso_name=selected_filename,
        )

    def list_available_images(
        self,
        request: UbuntuReleaseRequest,
    ) -> list[str]:
        """
        List available Debian standard ISO images for a given release and architecture.
        """
        self._validate_request(request)

        release_major = self._resolve_release_major(request.release)
        base_url = self._resolve_base_url(
            release_major=release_major,
            architecture=request.architecture,
        )

        manifest_url = f"{base_url}/SHA256SUMS"

        try:
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ArtifactNotFoundError(
                f"Failed to retrieve Debian checksum manifest: {manifest_url}: {exc}"
            ) from exc

        pattern = re.compile(
            rf"^debian-\d+\.\d+\.\d+-{re.escape(request.architecture)}-netinst\.iso$"
        )

        images: list[str] = []

        for raw_line in response.text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            filename = parts[-1].lstrip("*").strip()
            if pattern.match(filename):
                images.append(filename)

        return sorted(images)

    def _build_artifacts_bundle(
        self,
        release_major: str,
        base_url: str,
        architecture: str,
        image_type: str,
        iso_name: str,
    ) -> UbuntuReleaseArtifacts:
        """
        Build a complete Debian artifact bundle from a resolved ISO filename.
        """
        release_cache_dir = self.cache_root / release_major
        release_download_dir = self.downloads_root / release_major

        return UbuntuReleaseArtifacts(
            distribution=self.name,
            release=release_major,
            architecture=architecture,
            image_type=image_type,
            base_url=base_url,
            iso=RemoteArtifact(
                name="debian_iso",
                url=f"{base_url}/{iso_name}",
                local_path=release_download_dir / iso_name,
            ),
            checksums=RemoteArtifact(
                name="debian_checksums",
                url=f"{base_url}/SHA256SUMS",
                local_path=release_cache_dir / "SHA256SUMS",
            ),
            signature=RemoteArtifact(
                name="debian_signature",
                url=f"{base_url}/SHA256SUMS.sign",
                local_path=release_cache_dir / "SHA256SUMS.sign",
            ),
        )

    def _resolve_release_major(self, release: str) -> str:
        normalized = release.strip().lower()

        if normalized in self.CODENAME_MAP:
            resolved = self.CODENAME_MAP[normalized]
            LOGGER.info("Resolved codename '%s' -> '%s'", normalized, resolved)
            return resolved

        if normalized in self.SUPPORTED_MAJOR:
            return normalized

        raise UnsupportedReleaseError(
            f"Unsupported Debian release: {release}. "
            f"Supported: {sorted(self.SUPPORTED_MAJOR)} + codenames"
        )

    def _resolve_base_url(self, release_major: str, architecture: str) -> str:
        """
        Resolve correct Debian path:
        - 13 -> current
        - others -> archive auto-discovery
        """
        if release_major == "13":
            return f"{self.BASE_URL}/debian-cd/current/{architecture}/iso-cd"

        archive_index = f"{self.BASE_URL}/cdimage/archive/"

        try:
            response = requests.get(archive_index, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ArtifactNotFoundError(
                f"Failed to retrieve Debian archive index: {exc}"
            ) from exc

        pattern = re.compile(rf"{release_major}\.\d+\.\d+/")
        candidates = pattern.findall(response.text)

        if not candidates:
            raise ArtifactNotFoundError(
                f"No archive releases found for Debian {release_major}"
            )

        latest = max(candidates, key=self._version_key_from_dir).strip("/")
        LOGGER.info("Resolved Debian %s -> %s", release_major, latest)

        return f"{self.BASE_URL}/cdimage/archive/{latest}/{architecture}/iso-cd"

    def _discover_iso_filename(self, base_url: str, architecture: str) -> str:
        manifest_url = f"{base_url}/SHA256SUMS"

        try:
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ArtifactNotFoundError(
                f"Failed to retrieve Debian checksum manifest: {manifest_url}: {exc}"
            ) from exc

        pattern = re.compile(
            rf"^debian-(\d+\.\d+\.\d+)-{re.escape(architecture)}-netinst\.iso$"
        )

        candidates = []

        for line in response.text.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue

            filename = parts[-1].lstrip("*").strip()

            if pattern.match(filename):
                candidates.append(filename)

        if not candidates:
            raise ArtifactNotFoundError("No Debian ISO found in SHA256SUMS")

        selected = max(candidates, key=self._version_key)
        LOGGER.info("Discovered Debian ISO: %s", selected)
        return selected

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        return tuple(map(int, re.findall(r"\d+", version)))

    @staticmethod
    def _version_key_from_dir(directory: str) -> tuple[int, ...]:
        return tuple(map(int, re.findall(r"\d+", directory)))

    def _validate_request(self, request: UbuntuReleaseRequest) -> None:
        if request.architecture not in self.SUPPORTED_ARCHITECTURES:
            raise UnsupportedArchitectureError(
                f"Unsupported Debian architecture: {request.architecture}"
            )

        if request.image_type not in self.SUPPORTED_IMAGE_TYPES:
            raise UnsupportedReleaseError(
                f"Unsupported Debian image type: {request.image_type}"
            )
