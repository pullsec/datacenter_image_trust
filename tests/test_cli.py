from __future__ import annotations

import pytest

from datacenter_image_trust.cli import _ensure_local_artifacts_exist
from datacenter_image_trust.exceptions import DatacenterImageTrustError


def test_ensure_local_artifacts_exist_succeeds_when_all_files_exist(tmp_path) -> None:
    """
    Ensure offline verification pre-check succeeds when all files exist.
    """
    iso_path = tmp_path / "ubuntu.iso"
    sums_path = tmp_path / "SHA256SUMS"
    sig_path = tmp_path / "SHA256SUMS.gpg"

    iso_path.write_text("iso", encoding="utf-8")
    sums_path.write_text("sums", encoding="utf-8")
    sig_path.write_text("sig", encoding="utf-8")

    _ensure_local_artifacts_exist(iso_path, sums_path, sig_path)


def test_ensure_local_artifacts_exist_fails_when_a_file_is_missing(tmp_path) -> None:
    """
    Ensure offline verification pre-check fails when at least one file is missing.
    """
    iso_path = tmp_path / "ubuntu.iso"
    sums_path = tmp_path / "SHA256SUMS"
    sig_path = tmp_path / "SHA256SUMS.gpg"

    iso_path.write_text("iso", encoding="utf-8")
    sums_path.write_text("sums", encoding="utf-8")

    with pytest.raises(DatacenterImageTrustError):
        _ensure_local_artifacts_exist(iso_path, sums_path, sig_path)
