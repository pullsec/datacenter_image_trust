from __future__ import annotations

import hashlib

from datacenter_image_trust.checksum import (
    compute_sha256,
    extract_sha256_from_manifest,
    verify_sha256,
)


def test_compute_sha256_returns_expected_digest(tmp_path) -> None:
    """
    Ensure SHA256 computation returns the expected digest for a file.
    """
    file_path = tmp_path / "sample.iso"
    content = b"ubuntu-image-test-payload"
    file_path.write_bytes(content)

    expected_digest = hashlib.sha256(content).hexdigest()

    assert compute_sha256(file_path) == expected_digest


def test_extract_sha256_from_manifest_returns_expected_value(tmp_path) -> None:
    """
    Ensure the checksum manifest parser extracts the checksum for the target file.
    """
    manifest_path = tmp_path / "SHA256SUMS"
    manifest_path.write_text(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  file1.iso\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  file2.iso\n",
        encoding="utf-8",
    )

    checksum = extract_sha256_from_manifest(manifest_path, "file2.iso")

    assert checksum == "b" * 64


def test_verify_sha256_succeeds_for_matching_file_and_manifest(tmp_path) -> None:
    """
    Ensure checksum verification succeeds when the file digest matches the manifest.
    """
    iso_path = tmp_path / "ubuntu.iso"
    content = b"verified-iso-content"
    iso_path.write_bytes(content)

    digest = hashlib.sha256(content).hexdigest()

    manifest_path = tmp_path / "SHA256SUMS"
    manifest_path.write_text(f"{digest}  {iso_path.name}\n", encoding="utf-8")

    result = verify_sha256(iso_path=iso_path, manifest_path=manifest_path)

    assert result.is_valid is True
    assert result.expected == digest
    assert result.actual == digest
    assert result.algorithm == "sha256"


def test_verify_sha256_fails_for_mismatched_file_and_manifest(tmp_path) -> None:
    """
    Ensure checksum verification fails when the file digest does not match the manifest.
    """
    iso_path = tmp_path / "ubuntu.iso"
    iso_path.write_bytes(b"actual-iso-content")

    wrong_digest = hashlib.sha256(b"different-content").hexdigest()

    manifest_path = tmp_path / "SHA256SUMS"
    manifest_path.write_text(f"{wrong_digest}  {iso_path.name}\n", encoding="utf-8")

    result = verify_sha256(iso_path=iso_path, manifest_path=manifest_path)

    assert result.is_valid is False
    assert result.expected == wrong_digest
    assert result.actual != wrong_digest
