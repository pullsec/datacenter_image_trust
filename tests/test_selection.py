from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from datacenter_image_trust.exceptions import ArtifactNotFoundError
from datacenter_image_trust.models import UbuntuReleaseRequest
from datacenter_image_trust.providers.debian import DebianProvider
from datacenter_image_trust.providers.ubuntu import UbuntuProvider


# ============================================================
# Ubuntu tests
# ============================================================

@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_select_valid_image(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Ubuntu provider accepts a valid explicitly selected image.
    """
    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-24.04.4-desktop-amd64.iso\n"
    )
    mock_get.return_value = manifest_response
    mock_head.return_value.status_code = 200

    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="24.04",
        architecture="amd64",
        image_type="desktop",
    )

    artifacts = provider.build_selected_release_artifacts(
        request,
        selected_filename="ubuntu-24.04.4-desktop-amd64.iso",
    )

    assert artifacts.iso.url.endswith("ubuntu-24.04.4-desktop-amd64.iso")


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_select_invalid_image(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Ubuntu provider rejects invalid selected image.
    """
    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-24.04.4-live-server-amd64.iso\n"
    )
    mock_get.return_value = manifest_response
    mock_head.return_value.status_code = 200

    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="24.04",
        architecture="amd64",
        image_type="desktop",
    )

    with pytest.raises(ArtifactNotFoundError):
        provider.build_selected_release_artifacts(
            request,
            selected_filename="ubuntu-24.04.999-desktop-amd64.iso",
        )


# ============================================================
# Debian tests
# ============================================================

@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_select_valid_image(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian provider accepts a valid explicitly selected image.
    """
    archive_response = Mock()
    archive_response.raise_for_status.return_value = None
    archive_response.text = """
<a href="12.12.0/">12.12.0/</a>
<a href="12.13.0/">12.13.0/</a>
"""

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "debian-12.13.0-amd64-netinst.iso\n"
    )

    mock_get.side_effect = [
        archive_response,  # _resolve_base_url() in build_selected_release_artifacts()
        archive_response,  # _resolve_base_url() in list_available_images()
        manifest_response,  # SHA256SUMS in list_available_images()
    ]

    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="12",
        architecture="amd64",
        image_type="netinst",
    )

    artifacts = provider.build_selected_release_artifacts(
        request,
        selected_filename="debian-12.13.0-amd64-netinst.iso",
    )

    assert artifacts.iso.url.endswith("debian-12.13.0-amd64-netinst.iso")


@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_select_invalid_image(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian provider rejects invalid selected image.
    """
    archive_response = Mock()
    archive_response.raise_for_status.return_value = None
    archive_response.text = """
<a href="12.12.0/">12.12.0/</a>
<a href="12.13.0/">12.13.0/</a>
"""

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "debian-12.13.0-amd64-netinst.iso\n"
    )

    mock_get.side_effect = [
        archive_response,  # _resolve_base_url() in build_selected_release_artifacts()
        archive_response,  # _resolve_base_url() in list_available_images()
        manifest_response,  # SHA256SUMS in list_available_images()
    ]

    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="12",
        architecture="amd64",
        image_type="netinst",
    )

    with pytest.raises(ArtifactNotFoundError):
        provider.build_selected_release_artifacts(
            request,
            selected_filename="debian-99.99.0-amd64-netinst.iso",
        )
