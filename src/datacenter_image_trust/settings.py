from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class DistributionConfig:
    """
    Store effective distribution-specific configuration loaded from YAML.
    """

    name: str
    default_image_type: str
    default_architecture: str
    allowed_hosts: set[str]
    keyring_path: Path
    allowed_signers_path: Path


@dataclass(slots=True)
class ApplicationConfig:
    """
    Store global application configuration loaded from YAML.
    """

    logging_level: str
    network_timeout: int
    network_chunk_size: int
    default_architecture: str


@dataclass(slots=True)
class ApplicationPaths:
    """
    Store all important filesystem paths used by the application.
    """

    project_root: Path
    config_root: Path
    distributions_config_root: Path
    var_root: Path
    cache_root: Path
    downloads_root: Path
    logs_root: Path
    tmp_root: Path
    trust_root: Path

    ubuntu_cache_root: Path
    ubuntu_downloads_root: Path

    debian_cache_root: Path
    debian_downloads_root: Path

    fedora_cache_root: Path
    fedora_downloads_root: Path

    application_config_path: Path
    ubuntu_config_path: Path
    debian_config_path: Path
    fedora_config_path: Path


@dataclass(slots=True)
class RuntimeSettings:
    """
    Aggregate filesystem paths and parsed YAML settings.
    """

    paths: ApplicationPaths
    application: ApplicationConfig
    distributions: dict[str, DistributionConfig]


def resolve_project_root() -> Path:
    """
    Resolve the project root directory from the current file location.
    """
    return Path(__file__).resolve().parents[2]


def build_application_paths() -> ApplicationPaths:
    """
    Build the full application path configuration.
    """
    project_root = resolve_project_root()

    config_root = project_root / "conf"
    distributions_config_root = config_root / "distributions"

    var_root = project_root / "var"
    cache_root = var_root / "cache"
    downloads_root = var_root / "downloads"
    logs_root = var_root / "logs"
    tmp_root = var_root / "tmp"

    trust_root = project_root / "trust"

    return ApplicationPaths(
        project_root=project_root,
        config_root=config_root,
        distributions_config_root=distributions_config_root,
        var_root=var_root,
        cache_root=cache_root,
        downloads_root=downloads_root,
        logs_root=logs_root,
        tmp_root=tmp_root,
        trust_root=trust_root,
        ubuntu_cache_root=cache_root / "ubuntu",
        ubuntu_downloads_root=downloads_root / "ubuntu",
        debian_cache_root=cache_root / "debian",
        debian_downloads_root=downloads_root / "debian",
        fedora_cache_root=cache_root / "fedora",
        fedora_downloads_root=downloads_root / "fedora",
        application_config_path=config_root / "application.yml",
        ubuntu_config_path=distributions_config_root / "ubuntu.yml",
        debian_config_path=distributions_config_root / "debian.yml",
        fedora_config_path=distributions_config_root / "fedora.yml",
    )


def ensure_runtime_directories(paths: ApplicationPaths) -> None:
    """
    Ensure that required runtime directories exist.
    """
    runtime_directories = (
        paths.var_root,
        paths.cache_root,
        paths.downloads_root,
        paths.logs_root,
        paths.tmp_root,
        paths.ubuntu_cache_root,
        paths.ubuntu_downloads_root,
        paths.debian_cache_root,
        paths.debian_downloads_root,
        paths.fedora_cache_root,
        paths.fedora_downloads_root,
    )

    for directory in runtime_directories:
        directory.mkdir(parents=True, exist_ok=True)


def load_runtime_settings() -> RuntimeSettings:
    """
    Load application and distribution settings from YAML configuration files.
    """
    paths = build_application_paths()

    application_payload = _load_yaml_file(paths.application_config_path)
    ubuntu_payload = _load_yaml_file(paths.ubuntu_config_path)
    debian_payload = _load_yaml_file(paths.debian_config_path)
    fedora_payload = _load_yaml_file(paths.fedora_config_path)

    application = ApplicationConfig(
        logging_level=application_payload["logging"]["default_level"],
        network_timeout=int(application_payload["network"]["timeout"]),
        network_chunk_size=int(application_payload["network"]["chunk_size"]),
        default_architecture=application_payload["execution"]["default_architecture"],
    )

    distributions = {
        "ubuntu": _build_distribution_config(paths.project_root, ubuntu_payload),
        "debian": _build_distribution_config(paths.project_root, debian_payload),
        "fedora": _build_distribution_config(paths.project_root, fedora_payload),
    }

    return RuntimeSettings(
        paths=paths,
        application=application,
        distributions=distributions,
    )


def _build_distribution_config(
    project_root: Path,
    payload: dict[str, Any],
) -> DistributionConfig:
    """
    Build a typed distribution configuration object from raw YAML payload.
    """
    return DistributionConfig(
        name=payload["name"],
        default_image_type=payload["defaults"]["image_type"],
        default_architecture=payload["defaults"]["architecture"],
        allowed_hosts=set(payload["allowed_hosts"]),
        keyring_path=project_root / payload["trust"]["keyring"],
        allowed_signers_path=project_root / payload["trust"]["allowed_signers"],
    )


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """
    Load a YAML file from disk.

    Raises:
        RuntimeError: If the YAML file is missing or invalid.
    """
    if not file_path.is_file():
        raise RuntimeError(f"Configuration file not found: {file_path}")

    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise RuntimeError(f"Failed to read configuration file: {file_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML configuration: {file_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid configuration structure in: {file_path}")

    return data
