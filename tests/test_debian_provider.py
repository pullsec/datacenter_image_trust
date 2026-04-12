from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from datacenter_image_trust.exceptions import (
    UnsupportedArchitectureError,
    UnsupportedReleaseError,
)
from datacenter_image_trust.models import UbuntuReleaseRequest
from datacenter_image_trust.providers.debian import DebianProvider


@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_provider_builds_expected_artifacts_for_release_12(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian release 12 resolves to the latest archived Debian 12 netinst ISO.
    """
    archive_response = Mock()
    archive_response.raise_for_status.return_value = None
    archive_response.text = """
<a href="10.13.0/">10.13.0/</a>
<a href="11.11.0/">11.11.0/</a>
<a href="12.12.0/">12.12.0/</a>
<a href="12.13.0/">12.13.0/</a>
"""

    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "debian-12.12.0-amd64-netinst.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  "
        "debian-12.13.0-amd64-netinst.iso\n"
    )

    mock_get.side_effect = [archive_response, manifest_response]

    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="12",
        architecture="amd64",
        image_type="netinst",
    )

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.distribution == "debian"
    assert artifacts.release == "12"
    assert (
        artifacts.base_url
        == "https://cdimage.debian.org/cdimage/archive/12.13.0/amd64/iso-cd"
    )
    assert (
        artifacts.iso.url
        == "https://cdimage.debian.org/cdimage/archive/12.13.0/amd64/iso-cd/debian-12.13.0-amd64-netinst.iso"
    )
    assert artifacts.iso.local_path.name == "debian-12.13.0-amd64-netinst.iso"
    assert (
        artifacts.checksums.url
        == "https://cdimage.debian.org/cdimage/archive/12.13.0/amd64/iso-cd/SHA256SUMS"
    )
    assert (
        artifacts.signature.url
        == "https://cdimage.debian.org/cdimage/archive/12.13.0/amd64/iso-cd/SHA256SUMS.sign"
    )


@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_provider_builds_expected_artifacts_for_release_13(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian release 13 resolves to the current stable Debian netinst ISO path.
    """
    manifest_response = Mock()
    manifest_response.raise_for_status.return_value = None
    manifest_response.text = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  "
        "debian-13.4.0-amd64-netinst.iso\n"
    )

    mock_get.return_value = manifest_response

    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="13",
        architecture="amd64",
        image_type="netinst",
    )

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.release == "13"
    assert artifacts.base_url == "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd"
    assert artifacts.iso.local_path.name == "debian-13.4.0-amd64-netinst.iso"


@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_provider_resolves_codename_bookworm(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian codename 'bookworm' resolves to release 12.
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

    mock_get.side_effect = [archive_response, manifest_response]

    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="bookworm",
        architecture="amd64",
        image_type="netinst",
    )

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.release == "12"
    assert (
        artifacts.base_url
        == "https://cdimage.debian.org/cdimage/archive/12.13.0/amd64/iso-cd"
    )
    assert artifacts.iso.local_path.name == "debian-12.13.0-amd64-netinst.iso"


@patch("datacenter_image_trust.providers.debian.requests.get")
def test_debian_provider_resolves_codename_bullseye(
    mock_get,
    tmp_path,
) -> None:
    """
    Ensure Debian codename 'bullseye' resolves to release 11.
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

    artifacts = provider.build_release_artifacts(request)

    assert artifacts.release == "11"
    assert (
        artifacts.base_url
        == "https://cdimage.debian.org/cdimage/archive/11.11.0/amd64/iso-cd"
    )
    assert artifacts.iso.local_path.name == "debian-11.11.0-amd64-netinst.iso"


def test_debian_provider_rejects_unsupported_architecture(tmp_path) -> None:
    """
    Ensure Debian provider rejects unsupported architectures.
    """
    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="12",
        architecture="arm64",
        image_type="netinst",
    )

    with pytest.raises(UnsupportedArchitectureError):
        provider.build_release_artifacts(request)


def test_debian_provider_rejects_unknown_release(tmp_path) -> None:
    """
    Ensure Debian provider rejects unsupported releases.
    """
    provider = DebianProvider(
        cache_root=tmp_path / "cache" / "debian",
        downloads_root=tmp_path / "downloads" / "debian",
    )

    request = UbuntuReleaseRequest(
        release="9",
        architecture="amd64",
        image_type="netinst",
    )

    with pytest.raises(UnsupportedReleaseError):
        provider.build_release_artifacts(request)
