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


class UbuntuProvider(BaseProvider):
    """
    Resolve official Ubuntu release artifacts with support for:
    - exact point releases (24.04.2)
    - release series aliases (24.04)
    - codenames (noble, jammy, focal)

    Resolution rules:
    - Exact point release input must resolve to an ISO matching that exact version.
    - Series or codename input resolves to the latest matching point release found
      in the upstream SHA256SUMS manifest.
    """

    name = "ubuntu"

    SUPPORTED_ARCHITECTURES = {"amd64"}
    SUPPORTED_IMAGE_TYPES = {"live-server", "desktop"}

    CODENAME_MAP = {
        "noble": "24.04",
        "jammy": "22.04",
        "focal": "20.04",
        "bionic": "18.04",
        "xenial": "16.04",
        "trusty": "14.04",
    }

    POINT_RELEASE_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
    SERIES_PATTERN = re.compile(r"^\d+\.\d+$")

    def __init__(
        self,
        cache_root: Path,
        downloads_root: Path,
    ) -> None:
        self.cache_root = cache_root
        self.downloads_root = downloads_root

    def build_release_artifacts(
        self,
        request: UbuntuReleaseRequest,
    ) -> UbuntuReleaseArtifacts:
        self._validate_request(request)

        release_path = self._resolve_release_path(request.release)
        base_url = f"https://releases.ubuntu.com/{release_path}"

        iso_name = self._discover_iso_filename(
            requested_release=request.release,
            release_path=release_path,
            base_url=base_url,
            architecture=request.architecture,
            image_type=request.image_type,
        )

        return self._build_artifacts_bundle(
            release_path=release_path,
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
        Build artifacts for an explicitly selected Ubuntu ISO filename.
        """
        self._validate_request(request)

        release_path = self._resolve_release_path(request.release)
        base_url = f"https://releases.ubuntu.com/{release_path}"

        available_images = self.list_available_images(request)
        if selected_filename not in available_images:
            raise ArtifactNotFoundError(
                f"Selected Ubuntu image is not available for release {request.release}: "
                f"{selected_filename}"
            )

        return self._build_artifacts_bundle(
            release_path=release_path,
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
        List available Ubuntu ISO images for a given release and architecture.

        Only directly downloadable ISO files are returned.
        """
        self._validate_request(request)

        release_path = self._resolve_release_path(request.release)
        base_url = f"https://releases.ubuntu.com/{release_path}"
        manifest_url = f"{base_url}/SHA256SUMS"

        try:
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ArtifactNotFoundError(
                f"Failed to retrieve Ubuntu checksum manifest: {manifest_url}: {exc}"
            ) from exc

        pattern = re.compile(
            rf"^(ubuntu-\d+\.\d+(?:\.\d+)?-[a-z0-9-]+-{re.escape(request.architecture)}\.iso)$"
        )

        manifest_images: list[str] = []

        for raw_line in response.text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            filename = parts[-1].lstrip("*").strip()
            if pattern.match(filename):
                manifest_images.append(filename)

        downloadable_images = [
            filename
            for filename in sorted(manifest_images)
            if self._is_direct_download_available(base_url, filename)
        ]

        return downloadable_images

    def _build_artifacts_bundle(
        self,
        release_path: str,
        base_url: str,
        architecture: str,
        image_type: str,
        iso_name: str,
    ) -> UbuntuReleaseArtifacts:
        """
        Build a complete Ubuntu artifact bundle from a resolved ISO filename.
        """
        checksums_name = "SHA256SUMS"
        signature_name = "SHA256SUMS.gpg"

        release_cache_dir = self.cache_root / release_path
        release_download_dir = self.downloads_root / release_path

        iso_artifact = RemoteArtifact(
            name="ubuntu_iso",
            url=f"{base_url}/{iso_name}",
            local_path=release_download_dir / iso_name,
        )

        checksums_artifact = RemoteArtifact(
            name="ubuntu_checksums",
            url=f"{base_url}/SHA256SUMS",
            local_path=release_cache_dir / "SHA256SUMS",
        )

        signature_artifact = RemoteArtifact(
            name="ubuntu_checksum_signature",
            url=f"{base_url}/SHA256SUMS.gpg",
            local_path=release_cache_dir / "SHA256SUMS.gpg",
        )

        return UbuntuReleaseArtifacts(
            distribution=self.name,
            release=release_path,
            architecture=architecture,
            image_type=image_type,
            base_url=base_url,
            iso=iso_artifact,
            checksums=checksums_artifact,
            signature=signature_artifact,
        )

    def _resolve_release_path(self, release: str) -> str:
        """
        Resolve the upstream Ubuntu release directory path.
        """
        normalized = release.strip().lower()

        if normalized in self.CODENAME_MAP:
            resolved = self.CODENAME_MAP[normalized]
            LOGGER.info("Resolved codename '%s' -> '%s'", normalized, resolved)
            normalized = resolved

        url = f"https://releases.ubuntu.com/{normalized}/"

        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return normalized
        except requests.RequestException as exc:
            LOGGER.debug("Ubuntu HEAD request failed for %s: %s", url, exc)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return normalized
        except requests.RequestException as exc:
            LOGGER.debug("Ubuntu GET request failed for %s: %s", url, exc)

        raise UnsupportedReleaseError(f"Ubuntu release not found: {release}")

    def _discover_iso_filename(
        self,
        requested_release: str,
        release_path: str,
        base_url: str,
        architecture: str,
        image_type: str,
    ) -> str:
        """
        Discover the correct ISO filename from the upstream SHA256SUMS manifest.
        """
        manifest_url = f"{base_url}/SHA256SUMS"

        try:
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ArtifactNotFoundError(
                f"Failed to retrieve Ubuntu checksum manifest: {manifest_url}: {exc}"
            ) from exc

        candidates = self._extract_iso_candidates(
            manifest_text=response.text,
            architecture=architecture,
            image_type=image_type,
        )

        if not candidates:
            raise ArtifactNotFoundError(
                f"Could not discover any Ubuntu ISO filename from {manifest_url}"
            )

        normalized_requested = requested_release.strip().lower()
        if normalized_requested in self.CODENAME_MAP:
            normalized_requested = self.CODENAME_MAP[normalized_requested]

        if self.POINT_RELEASE_PATTERN.fullmatch(normalized_requested):
            for candidate in candidates:
                if candidate["version"] == normalized_requested:
                    LOGGER.info(
                        "Discovered exact Ubuntu ISO filename: %s",
                        candidate["filename"],
                    )
                    return candidate["filename"]

            raise ArtifactNotFoundError(
                f"No ISO matching exact Ubuntu release {normalized_requested} "
                f"was found in {manifest_url}"
            )

        if self.SERIES_PATTERN.fullmatch(release_path):
            matching_candidates = [
                candidate
                for candidate in candidates
                if candidate["version"].startswith(f"{release_path}.")
                or candidate["version"] == release_path
            ]

            if not matching_candidates:
                raise ArtifactNotFoundError(
                    f"No ISO matching Ubuntu series {release_path} "
                    f"was found in {manifest_url}"
                )

            selected = max(
                matching_candidates,
                key=lambda item: self._version_key(item["version"]),
            )
            LOGGER.info(
                "Discovered latest Ubuntu ISO filename for series %s: %s",
                release_path,
                selected["filename"],
            )
            return selected["filename"]

        raise ArtifactNotFoundError(
            f"Unsupported Ubuntu release resolution state for {requested_release}"
        )

    def _extract_iso_candidates(
        self,
        manifest_text: str,
        architecture: str,
        image_type: str,
    ) -> list[dict[str, str]]:
        """
        Extract matching ISO filenames and versions from a SHA256SUMS manifest.
        """
        pattern = re.compile(
            rf"^(ubuntu-(?P<version>\d+\.\d+(?:\.\d+)?)-"
            rf"{re.escape(image_type)}-{re.escape(architecture)}\.iso)$"
        )

        candidates: list[dict[str, str]] = []

        for raw_line in manifest_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            candidate_filename = parts[-1].lstrip("*").strip()
            match = pattern.match(candidate_filename)
            if match:
                candidates.append(
                    {
                        "filename": candidate_filename,
                        "version": match.group("version"),
                    }
                )

        return candidates

    def _is_direct_download_available(self, base_url: str, filename: str) -> bool:
        """
        Check whether the direct ISO download URL is actually available.
        """
        url = f"{base_url}/{filename}"

        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                return True
        except requests.RequestException as exc:
            LOGGER.debug("Ubuntu ISO HEAD request failed for %s: %s", url, exc)

        try:
            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            LOGGER.debug("Ubuntu ISO GET request failed for %s: %s", url, exc)

        return False

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        """
        Convert a dotted version string to a sortable numeric tuple.
        """
        return tuple(int(part) for part in version.split("."))

    def _validate_request(self, request: UbuntuReleaseRequest) -> None:
        if request.architecture not in self.SUPPORTED_ARCHITECTURES:
            raise UnsupportedArchitectureError(
                f"Unsupported Ubuntu architecture: {request.architecture}"
            )

        if request.image_type not in self.SUPPORTED_IMAGE_TYPES:
            raise UnsupportedReleaseError(
                f"Unsupported Ubuntu image type: {request.image_type}"
            )

        if not request.release.strip():
            raise UnsupportedReleaseError("Ubuntu release must not be empty")
