from __future__ import annotations

from unittest.mock import Mock, patch

from datacenter_image_trust.models import UbuntuReleaseRequest
from datacenter_image_trust.providers.debian import DebianProvider
from datacenter_image_trust.providers.ubuntu import UbuntuProvider


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_provider_lists_available_images_for_series(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Ubuntu listing returns all matching ISO images for the requested series.
    """
    mock_head.return_value = Mock(status_code=200)

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-24.04.3-desktop-amd64.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "ubuntu-24.04.3-live-server-amd64.iso\n"
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc  "
        "ubuntu-24.04.4-desktop-amd64.iso\n"
        "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd  "
        "ubuntu-24.04.4-live-server-amd64.iso\n"
    )
    mock_get.return_value = manifest_response

    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="24.04",
        architecture="amd64",
        image_type="desktop",
    )

    images = provider.list_available_images(request)

    assert images == [
        "ubuntu-24.04.3-desktop-amd64.iso",
        "ubuntu-24.04.3-live-server-amd64.iso",
        "ubuntu-24.04.4-desktop-amd64.iso",
        "ubuntu-24.04.4-live-server-amd64.iso",
    ]


@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_provider_lists_only_standard_netinst_images(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian listing returns only the standard Debian netinst image by default.
    """
    archive_response = Mock()
    archive_response.raise_for_status.return_value = None
    archive_response.text = """
<a href="11.10.0/">11.10.0/</a>
<a href="11.11.0/">11.11.0/</a>
"""

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "debian-11.11.0-amd64-netinst.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "debian-edu-11.11.0-amd64-netinst.iso\n"
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc  "
        "debian-mac-11.11.0-amd64-netinst.iso\n"
    )

    mock_get.side_effect = [archive_response, manifest_response]

    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="bullseye",
        architecture="amd64",
        image_type="netinst",
    )

    images = provider.list_available_images(request)

    assert images == [
        "debian-11.11.0-amd64-netinst.iso",
    ]
