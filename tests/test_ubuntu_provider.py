from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from datacenter_image_trust.exceptions import (
    ArtifactNotFoundError,
    UnsupportedArchitectureError,
)
from datacenter_image_trust.models import UbuntuReleaseRequest
from datacenter_image_trust.providers.ubuntu import UbuntuProvider


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_provider_builds_expected_artifacts_for_exact_point_release(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure the Ubuntu provider resolves an exact point release to the exact ISO.
    """
    mock_head.return_value = Mock(status_code=200)

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-24.04-live-server-amd64.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "ubuntu-24.04.2-live-server-amd64.iso\n"
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc  "
        "ubuntu-24.04.4-live-server-amd64.iso\n"
    )
    mock_get.return_value = manifest_response

    cache_root = tmp_path / "cache" / "ubuntu"
    downloads_root = tmp_path / "downloads" / "ubuntu"

    provider = UbuntuProvider(
        cache_root=cache_root,
        downloads_root=downloads_root,
    )

    request = UbuntuReleaseRequest(
        release="24.04.2",
        architecture="amd64",
        image_type="live-server",
    )

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.distribution == "ubuntu"
    assert artifacts.release == "24.04.2"
    assert artifacts.architecture == "amd64"
    assert artifacts.image_type == "live-server"
    assert artifacts.base_url == "https://releases.ubuntu.com/24.04.2"
    assert (
        artifacts.iso.url
        == "https://releases.ubuntu.com/24.04.2/ubuntu-24.04.2-live-server-amd64.iso"
    )
    assert (
        artifacts.iso.local_path
        == downloads_root / "24.04.2" / "ubuntu-24.04.2-live-server-amd64.iso"
    )
    assert artifacts.checksums.url == "https://releases.ubuntu.com/24.04.2/SHA256SUMS"
    assert artifacts.signature.url == "https://releases.ubuntu.com/24.04.2/SHA256SUMS.gpg"


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_provider_builds_latest_artifacts_for_series_release(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure the Ubuntu provider selects the latest point release for a series alias.
    """
    mock_head.return_value = Mock(status_code=200)

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-22.04-live-server-amd64.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "ubuntu-22.04.3-live-server-amd64.iso\n"
        "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc  "
        "ubuntu-22.04.5-live-server-amd64.iso\n"
    )
    mock_get.return_value = manifest_response

    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="22.04",
        architecture="amd64",
        image_type="live-server",
    )

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.release == "22.04"
    assert artifacts.iso.url.endswith("/ubuntu-22.04.5-live-server-amd64.iso")
    assert artifacts.iso.local_path.name == "ubuntu-22.04.5-live-server-amd64.iso"


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_provider_resolves_codename_to_series(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure the Ubuntu provider resolves a codename to its series and picks the latest ISO.
    """
    mock_head.return_value = Mock(status_code=200)

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-22.04.4-live-server-amd64.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "ubuntu-22.04.5-live-server-amd64.iso\n"
    )
    mock_get.return_value = manifest_response

    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="jammy",
        architecture="amd64",
        image_type="live-server",
    )

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.release == "22.04"
    assert artifacts.base_url == "https://releases.ubuntu.com/22.04"
    assert artifacts.iso.local_path.name == "ubuntu-22.04.5-live-server-amd64.iso"


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_provider_supports_desktop_image(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure the Ubuntu provider resolves desktop images correctly.
    """
    mock_head.return_value = Mock(status_code=200)

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-24.04.4-live-server-amd64.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "ubuntu-24.04.4-desktop-amd64.iso\n"
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

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.distribution == "ubuntu"
    assert artifacts.release == "24.04"
    assert artifacts.image_type == "desktop"
    assert artifacts.base_url == "https://releases.ubuntu.com/24.04"
    assert (
        artifacts.iso.url
        == "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-desktop-amd64.iso"
    )
    assert artifacts.iso.local_path.name == "ubuntu-24.04.4-desktop-amd64.iso"


def test_ubuntu_provider_rejects_unsupported_architecture(tmp_path) -> None:
    """
    Ensure the Ubuntu provider rejects unsupported architectures.
    """
    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="24.04.2",
        architecture="arm64",
        image_type="live-server",
    )

    with pytest.raises(UnsupportedArchitectureError):
        provider.build_release_artifacts(request)


@patch("datacenter_image_trust.providers.ubuntu.requests.get")
@patch("datacenter_image_trust.providers.ubuntu.requests.head")
def test_ubuntu_provider_fails_when_exact_point_release_is_missing(
    mock_head,
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure the Ubuntu provider fails instead of silently selecting another point release.
    """
    mock_head.return_value = Mock(status_code=200)

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "ubuntu-24.04.4-live-server-amd64.iso\n"
    )
    mock_get.return_value = manifest_response

    provider = UbuntuProvider(
        cache_root=tmp_path / "cache" / "ubuntu",
        downloads_root=tmp_path / "downloads" / "ubuntu",
    )

    request = UbuntuReleaseRequest(
        release="24.04.2",
        architecture="amd64",
        image_type="live-server",
    )

    with pytest.raises(ArtifactNotFoundError):
        provider.build_release_artifacts(request)
