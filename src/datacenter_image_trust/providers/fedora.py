from __future__ import annotations

import logging
import re
from pathlib import Path

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


class FedoraProvider(BaseProvider):
    """
    Fedora provider using browsable Fedora mirrors for deterministic artifact discovery.

    Current scope:
    - releases: 42, 43
    - architecture: x86_64
    - image types:
        - server-dvd
        - server-netinst
    """

    name = "fedora"

    SUPPORTED_RELEASES = {"42", "43"}
    SUPPORTED_ARCHITECTURES = {"x86_64"}
    SUPPORTED_IMAGE_TYPES = {"server-dvd", "server-netinst"}

    MIRRORS = [
        "https://ftp.usf.edu/pub/fedora/linux/releases",
        "https://free.nchc.org.tw/fedora/linux/releases",
        "https://ftp.riken.jp/Linux/fedora/releases",
    ]

    def __init__(self, cache_root: Path, downloads_root: Path) -> None:
        self.cache_root = cache_root
        self.downloads_root = downloads_root

    def build_release_artifacts(
        self,
        request: UbuntuReleaseRequest,
    ) -> UbuntuReleaseArtifacts:
        self._validate_request(request)

        base_url = self._build_base_url(
            release=request.release,
            architecture=request.architecture,
        )

        checksum_name = self._discover_checksum_filename(
            base_url=base_url,
            release=request.release,
            architecture=request.architecture,
        )

        iso_name = self._discover_iso_filename(
            base_url=base_url,
            checksum_name=checksum_name,
            release=request.release,
            architecture=request.architecture,
            image_type=request.image_type,
        )

        return self._build_artifacts_bundle(
            request=request,
            base_url=base_url,
            iso_name=iso_name,
            checksum_name=checksum_name,
        )

    def list_available_images(
        self,
        request: UbuntuReleaseRequest,
    ) -> list[str]:
        self._validate_request(request)

        base_url = self._build_base_url(
            release=request.release,
            architecture=request.architecture,
        )

        checksum_name = self._discover_checksum_filename(
            base_url=base_url,
            release=request.release,
            architecture=request.architecture,
        )

        checksum_text = self._fetch_text(f"{base_url}/{checksum_name}")
        images = self._extract_iso_filenames_from_checksum(
            checksum_text=checksum_text,
            release=request.release,
            architecture=request.architecture,
        )

        return sorted(images)

    def build_selected_release_artifacts(
        self,
        request: UbuntuReleaseRequest,
        selected_filename: str,
    ) -> UbuntuReleaseArtifacts:
        self._validate_request(request)

        available_images = self.list_available_images(request)
        if selected_filename not in available_images:
            raise ArtifactNotFoundError(
                f"Selected Fedora image is not available for release {request.release}: "
                f"{selected_filename}"
            )

        base_url = self._build_base_url(
            release=request.release,
            architecture=request.architecture,
        )

        checksum_name = self._discover_checksum_filename(
            base_url=base_url,
            release=request.release,
            architecture=request.architecture,
        )

        return self._build_artifacts_bundle(
            request=request,
            base_url=base_url,
            iso_name=selected_filename,
            checksum_name=checksum_name,
        )

    def _build_artifacts_bundle(
        self,
        request: UbuntuReleaseRequest,
        base_url: str,
        iso_name: str,
        checksum_name: str,
    ) -> UbuntuReleaseArtifacts:
        release_cache_dir = self.cache_root / request.release
        release_download_dir = self.downloads_root / request.release

        checksum_local_path = release_cache_dir / checksum_name

        return UbuntuReleaseArtifacts(
            distribution=self.name,
            release=request.release,
            architecture=request.architecture,
            image_type=request.image_type,
            base_url=base_url,
            iso=RemoteArtifact(
                name="fedora_iso",
                url=f"{base_url}/{iso_name}",
                local_path=release_download_dir / iso_name,
            ),
            checksums=RemoteArtifact(
                name="fedora_checksums",
                url=f"{base_url}/{checksum_name}",
                local_path=checksum_local_path,
            ),
            signature=RemoteArtifact(
                name="fedora_inline_checksum_signature",
                url=f"{base_url}/{checksum_name}",
                local_path=checksum_local_path,
            ),
        )

    def _build_base_url(self, release: str, architecture: str) -> str:
        for mirror in self.MIRRORS:
            url = f"{mirror}/{release}/Server/{architecture}/iso"

            try:
                response = requests.get(f"{url}/", timeout=5)
                if response.status_code == 200:
                    LOGGER.info("Using Fedora mirror: %s", mirror)
                    return url
            except requests.RequestException as exc:
                LOGGER.debug("Fedora mirror probe failed for %s: %s", url, exc)

        raise ArtifactNotFoundError(
            f"No working Fedora mirror found for release {release}"
        )

    def _discover_checksum_filename(
        self,
        base_url: str,
        release: str,
        architecture: str,
    ) -> str:
        index_text = self._fetch_text(f"{base_url}/")

        pattern = re.compile(
            rf"(Fedora-Server-{re.escape(release)}-[0-9.]+-{re.escape(architecture)}-CHECKSUM)"
        )

        matches = pattern.findall(index_text)
        if not matches:
            raise ArtifactNotFoundError(
                f"Could not discover Fedora CHECKSUM filename in {base_url}/"
            )

        return sorted(set(matches))[-1]

    def _discover_iso_filename(
        self,
        base_url: str,
        checksum_name: str,
        release: str,
        architecture: str,
        image_type: str,
    ) -> str:
        checksum_text = self._fetch_text(f"{base_url}/{checksum_name}")
        images = self._extract_iso_filenames_from_checksum(
            checksum_text=checksum_text,
            release=release,
            architecture=architecture,
        )

        if image_type == "server-dvd":
            expected_prefix = f"Fedora-Server-dvd-{architecture}-{release}-"
        elif image_type == "server-netinst":
            expected_prefix = f"Fedora-Server-netinst-{architecture}-{release}-"
        else:
            raise UnsupportedReleaseError(
                f"Unsupported Fedora image type: {image_type}"
            )

        candidates = [
            image for image in images
            if image.startswith(expected_prefix)
        ]

        if not candidates:
            raise ArtifactNotFoundError(
                f"Could not discover Fedora ISO filename in {base_url}/{checksum_name}"
            )

        return sorted(candidates)[-1]

    def _extract_iso_filenames_from_checksum(
        self,
        checksum_text: str,
        release: str,
        architecture: str,
    ) -> list[str]:
        images: list[str] = []

        pattern = re.compile(
            rf"(Fedora-Server-(dvd|netinst)-{re.escape(architecture)}-"
            rf"{re.escape(release)}-[0-9.]+\.iso)"
        )

        for raw_line in checksum_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            for match in pattern.finditer(line):
                images.append(match.group(1))

        return sorted(set(images))

    def _fetch_text(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            raise ArtifactNotFoundError(
                f"Failed to retrieve Fedora resource: {url}: {exc}"
            ) from exc

    def _validate_request(self, request: UbuntuReleaseRequest) -> None:
        if request.release not in self.SUPPORTED_RELEASES:
            raise UnsupportedReleaseError(
                f"Unsupported Fedora release: {request.release}. "
                f"Supported values currently include: {sorted(self.SUPPORTED_RELEASES)}"
            )

        if request.architecture not in self.SUPPORTED_ARCHITECTURES:
            raise UnsupportedArchitectureError(
                f"Unsupported Fedora architecture: {request.architecture}"
            )

        if request.image_type not in self.SUPPORTED_IMAGE_TYPES:
            raise UnsupportedReleaseError(
                f"Unsupported Fedora image type: {request.image_type}"
            )
