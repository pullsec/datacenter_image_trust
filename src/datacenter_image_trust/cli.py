from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from datacenter_image_trust.checksum import verify_sha256, verify_sha256_from_text
from datacenter_image_trust.downloader import download_artifacts
from datacenter_image_trust.exceptions import DatacenterImageTrustError
from datacenter_image_trust.logging_config import configure_logging
from datacenter_image_trust.models import UbuntuReleaseRequest, VerificationReport
from datacenter_image_trust.providers.debian import DebianProvider
from datacenter_image_trust.providers.fedora import FedoraProvider
from datacenter_image_trust.providers.ubuntu import UbuntuProvider
from datacenter_image_trust.settings import (
    DistributionConfig,
    RuntimeSettings,
    ensure_runtime_directories,
    load_runtime_settings,
)
from datacenter_image_trust.signature import (
    verify_detached_signature,
    verify_inline_clearsigned_file,
)
from datacenter_image_trust.trust import validate_trust_policy


LOGGER = logging.getLogger(__name__)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datacenter-image-trust",
        description="Securely download and verify Linux distribution images",
    )

    parser.add_argument(
        "--distribution",
        default="ubuntu",
        choices=["ubuntu", "debian", "fedora"],
        help="Target Linux distribution (default: ubuntu)",
    )

    parser.add_argument(
        "--release",
        required=True,
        help="Release version, series, or codename depending on the provider",
    )

    parser.add_argument(
        "--arch",
        default=None,
        help="Target architecture (default: from YAML configuration)",
    )

    parser.add_argument(
        "--image-type",
        default=None,
        help="Distribution image type (default: from YAML configuration)",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available ISO images without downloading",
    )

    parser.add_argument(
        "--select",
        default=None,
        help="Select an exact ISO filename returned by --list",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose operational logging",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final verification report as JSON",
    )

    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify already-downloaded local artifacts without downloading",
    )

    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Do not download remote artifacts; use existing local files only",
    )

    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download of artifacts even if already present locally",
    )

    return parser


def run() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    settings = load_runtime_settings()
    configure_logging(verbose=args.verbose)

    ensure_runtime_directories(settings.paths)

    offline_mode = args.no_download or args.verify_only

    try:
        distribution_config = settings.distributions[args.distribution]

        LOGGER.info("Building release request")
        request = UbuntuReleaseRequest(
            release=args.release,
            architecture=_resolve_architecture(
                cli_arch=args.arch,
                distribution_config=distribution_config,
                settings=settings,
            ),
            image_type=_resolve_image_type(
                cli_image_type=args.image_type,
                distribution_config=distribution_config,
            ),
        )

        LOGGER.info("Resolving %s artifacts", args.distribution)
        provider = _build_provider(
            distribution=args.distribution,
            settings=settings,
        )

        if args.list:
            LOGGER.info("Listing available images")
            images = provider.list_available_images(request)

            if args.json:
                print(json.dumps({"images": images}, indent=2))
            else:
                print("\nAvailable images:\n")
                for image in images:
                    print(f" - {image}")
                print()

            return 0

        if args.select:
            LOGGER.info("Using explicitly selected image: %s", args.select)
            artifacts = provider.build_selected_release_artifacts(
                request=request,
                selected_filename=args.select,
            )
        else:
            artifacts = provider.build_release_artifacts(request)

        if offline_mode:
            LOGGER.info("Offline verification mode enabled")
            _ensure_local_artifacts_exist(
                artifacts.iso.local_path,
                artifacts.checksums.local_path,
                artifacts.signature.local_path,
            )
        else:
            if args.force_download:
                LOGGER.info("Force download enabled")

            LOGGER.info("Downloading remote artifacts")
            download_artifacts(
                [
                    artifacts.iso,
                    artifacts.checksums,
                    artifacts.signature,
                ],
                timeout=settings.application.network_timeout,
                chunk_size=settings.application.network_chunk_size,
                force=args.force_download,
            )

        if args.distribution == "fedora":
            LOGGER.info("Verifying inline clearsigned Fedora CHECKSUM")
            signature_result, verified_checksum_text = verify_inline_clearsigned_file(
                signed_file_path=artifacts.checksums.local_path,
                keyring_path=distribution_config.keyring_path,
            )

            LOGGER.info("Verifying ISO SHA256 checksum against verified Fedora CHECKSUM")
            checksum_result = verify_sha256_from_text(
                iso_path=artifacts.iso.local_path,
                manifest_text=verified_checksum_text,
            )
        else:
            LOGGER.info("Verifying detached checksum signature")
            signature_result = verify_detached_signature(
                signed_file_path=artifacts.checksums.local_path,
                signature_file_path=artifacts.signature.local_path,
                keyring_path=distribution_config.keyring_path,
            )

            LOGGER.info("Verifying ISO SHA256 checksum")
            checksum_result = verify_sha256(
                iso_path=artifacts.iso.local_path,
                manifest_path=artifacts.checksums.local_path,
            )

        LOGGER.info("Validating local trust policy")
        trust_result = validate_trust_policy(
            artifact_url=artifacts.iso.url,
            allowed_hosts=distribution_config.allowed_hosts,
            signer_fingerprint=signature_result.signer_fingerprint,
            fingerprints_file_path=distribution_config.allowed_signers_path,
        )

        success = (
            signature_result.is_valid
            and checksum_result.is_valid
            and trust_result.is_trusted
        )

        report = VerificationReport(
            distribution=artifacts.distribution,
            release=artifacts.release,
            architecture=artifacts.architecture,
            image_type=artifacts.image_type,
            iso_path=artifacts.iso.local_path,
            signature_result=signature_result,
            checksum_result=checksum_result,
            trust_result=trust_result,
            success=success,
            details={
                "offline_mode": str(offline_mode).lower(),
                "verify_only": str(args.verify_only).lower(),
                "no_download": str(args.no_download).lower(),
                "force_download": str(args.force_download).lower(),
                "selected_image": args.select or "",
            },
        )

        if args.json:
            _print_json_report(report)
        else:
            _print_report(report)

        return 0 if success else 1

    except DatacenterImageTrustError as exc:
        if args.json:
            print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    except RuntimeError as exc:
        if args.json:
            print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        else:
            print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _build_provider(distribution: str, settings: RuntimeSettings):
    if distribution == "ubuntu":
        return UbuntuProvider(
            cache_root=settings.paths.ubuntu_cache_root,
            downloads_root=settings.paths.ubuntu_downloads_root,
        )

    if distribution == "debian":
        return DebianProvider(
            cache_root=settings.paths.debian_cache_root,
            downloads_root=settings.paths.debian_downloads_root,
        )

    if distribution == "fedora":
        return FedoraProvider(
            cache_root=settings.paths.fedora_cache_root,
            downloads_root=settings.paths.fedora_downloads_root,
        )

    raise DatacenterImageTrustError(
        f"Unsupported distribution requested by CLI: {distribution}"
    )


def _resolve_architecture(
    cli_arch: str | None,
    distribution_config: DistributionConfig,
    settings: RuntimeSettings,
) -> str:
    if cli_arch:
        return cli_arch

    if distribution_config.default_architecture:
        return distribution_config.default_architecture

    return settings.application.default_architecture


def _resolve_image_type(
    cli_image_type: str | None,
    distribution_config: DistributionConfig,
) -> str:
    if cli_image_type:
        return cli_image_type

    return distribution_config.default_image_type


def _ensure_local_artifacts_exist(*paths: Path) -> None:
    missing_paths = [path for path in paths if not path.is_file()]

    if missing_paths:
        missing_as_text = ", ".join(str(path) for path in missing_paths)
        raise DatacenterImageTrustError(
            "Offline verification requires local artifacts, but the following "
            f"files are missing: {missing_as_text}"
        )


def _print_report(report: VerificationReport) -> None:
    print("\n=== Verification Report ===")
    print(f"Distribution : {report.distribution}")
    print(f"Release      : {report.release}")
    print(f"Architecture : {report.architecture}")
    print(f"Image type   : {report.image_type}")
    print(f"ISO path     : {report.iso_path}")
    print()

    print("[Signature]")
    print(f"  Valid      : {report.signature_result.is_valid}")
    print(f"  Fingerprint: {report.signature_result.signer_fingerprint}")
    print(f"  UID        : {report.signature_result.signer_uid}")
    print()

    print("[Checksum]")
    print(f"  Valid      : {report.checksum_result.is_valid}")
    print(f"  Expected   : {report.checksum_result.expected}")
    print(f"  Actual     : {report.checksum_result.actual}")
    print()

    print("[Trust]")
    print(f"  Trusted    : {report.trust_result.is_trusted}")
    print(f"  Host       : {report.trust_result.validated_hostname}")
    print()

    print("[Execution]")
    print(f"  Offline       : {report.details.get('offline_mode')}")
    print(f"  Verify only   : {report.details.get('verify_only')}")
    print(f"  No download   : {report.details.get('no_download')}")
    print(f"  Force download: {report.details.get('force_download')}")
    print(f"  Selected image: {report.details.get('selected_image')}")
    print()

    print(f"[FINAL STATUS] {'SUCCESS' if report.success else 'FAILURE'}")


def _print_json_report(report: VerificationReport) -> None:
    payload = {
        "distribution": report.distribution,
        "release": report.release,
        "architecture": report.architecture,
        "image_type": report.image_type,
        "iso_path": str(report.iso_path),
        "signature": {
            "is_valid": report.signature_result.is_valid,
            "fingerprint": report.signature_result.signer_fingerprint,
            "uid": report.signature_result.signer_uid,
            "status_message": report.signature_result.status_message,
        },
        "checksum": {
            "is_valid": report.checksum_result.is_valid,
            "algorithm": report.checksum_result.algorithm,
            "expected": report.checksum_result.expected,
            "actual": report.checksum_result.actual,
            "status_message": report.checksum_result.status_message,
        },
        "trust": {
            "is_trusted": report.trust_result.is_trusted,
            "validated_hostname": report.trust_result.validated_hostname,
            "signer_fingerprint": report.trust_result.signer_fingerprint,
            "status_message": report.trust_result.status_message,
        },
        "details": report.details,
        "success": report.success,
    }

    print(json.dumps(payload, indent=2))
