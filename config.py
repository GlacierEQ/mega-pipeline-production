"""
APEX HIGH-SIGNAL COMPANIES — Production Configuration System
Externalized configuration via dataclass + TOML.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional
import json


@dataclass(frozen=True)
class NASAConfig:
    """NASA telemetry gate configuration."""
    cfar_threshold_db: float = 10.0
    sigma_threshold: float = 3.0
    max_history_per_apid: int = 4096
    known_apids: tuple = (0x100, 0x10A)


@dataclass(frozen=True)
class ConstellationConfig:
    """Constellation mesh configuration."""
    earth_radius_km: float = 6371.0
    min_elevation_deg: float = 5.0
    gamma: float = 0.95
    eta: float = 0.10
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_s: float = 30.0


@dataclass(frozen=True)
class GPUConfig:
    """GPU topology engine configuration."""
    nvlink_bandwidth_gbps: float = 900.0
    pcie_bandwidth_gbps: float = 64.0
    min_nvlink_for_training: int = 2


@dataclass(frozen=True)
class F35Config:
    """F-35 verification pipeline configuration."""
    gamma: float = 0.92
    eta: float = 0.15
    max_retries: int = 3
    pipeline_stages: tuple = (
        "unit_test", "integration", "static_analysis",
        "hil_simulation", "certification", "deployment",
    )


@dataclass(frozen=True)
class EWConfig:
    """EW signal fabric configuration."""
    cfar_threshold_db: float = 10.0
    max_signal_buffer: int = 100_000
    confirmation_samples: int = 3
    classification_threshold: float = 0.5


@dataclass(frozen=True)
class CMMCConfig:
    """CMMC compliance engine configuration."""
    gamma: float = 0.95
    eta: float = 0.10
    cui_patterns_enabled: bool = True


@dataclass(frozen=True)
class SwarmConfig:
    """Swarm forge configuration."""
    earth_radius_m: float = 6_371_000.0
    heartbeat_timeout_s: float = 30.0
    gamma: float = 0.85
    eta: float = 0.15
    min_reliability_for_engagement: float = 0.5


@dataclass(frozen=True)
class ApexConfig:
    """Root configuration for all APEX high-signal modules."""
    nasa: NASAConfig = field(default_factory=NASAConfig)
    constellation: ConstellationConfig = field(default_factory=ConstellationConfig)
    gpu: GPUConfig = field(default_factory=GPUConfig)
    f35: F35Config = field(default_factory=F35Config)
    ew: EWConfig = field(default_factory=EWConfig)
    cmmc: CMMCConfig = field(default_factory=CMMCConfig)
    swarm: SwarmConfig = field(default_factory=SwarmConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nasa": self.nasa.__dict__,
            "constellation": self.constellation.__dict__,
            "gpu": self.gpu.__dict__,
            "f35": self.f35.__dict__,
            "ew": self.ew.__dict__,
            "cmmc": self.cmmc.__dict__,
            "swarm": self.swarm.__dict__,
        }

    def save_toml(self, path: Path) -> None:
        """Save configuration to TOML format."""
        lines = ["# APEX Production Configuration", ""]
        for section_name, section_data in self.to_dict().items():
            lines.append(f"[{section_name}]")
            for key, value in section_data.items():
                if isinstance(value, tuple):
                    lines.append(f'{key} = {list(value)}')
                elif isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                else:
                    lines.append(f"{key} = {value}")
            lines.append("")
        path.write_text("\n".join(lines))

    @classmethod
    def load_toml(cls, path: Path) -> "ApexConfig":
        """Load configuration from TOML file."""
        # Simplified TOML parser for our flat config
        text = path.read_text()
        sections: Dict[str, Dict[str, Any]] = {}
        current_section = ""
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                sections[current_section] = {}
            elif "=" in line and current_section:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    sections[current_section][key] = value[1:-1]
                elif value.startswith("["):
                    sections[current_section][key] = eval(value)
                elif value.lower() == "true":
                    sections[current_section][key] = True
                elif value.lower() == "false":
                    sections[current_section][key] = False
                else:
                    try:
                        sections[current_section][key] = float(value)
                    except ValueError:
                        sections[current_section][key] = value
        return cls(
            nasa=NASAConfig(**sections.get("nasa", {})),
            constellation=ConstellationConfig(**sections.get("constellation", {})),
            gpu=GPUConfig(**sections.get("gpu", {})),
            f35=F35Config(**sections.get("f35", {})),
            ew=EWConfig(**sections.get("ew", {})),
            cmmc=CMMCConfig(**sections.get("cmmc", {})),
            swarm=SwarmConfig(**sections.get("swarm", {})),
        )

    def save_json(self, path: Path) -> None:
        """Save configuration to JSON format."""
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load_json(cls, path: Path) -> "ApexConfig":
        """Load configuration from JSON file."""
        data = json.loads(path.read_text())
        return cls(
            nasa=NASAConfig(**data.get("nasa", {})),
            constellation=ConstellationConfig(**data.get("constellation", {})),
            gpu=GPUConfig(**data.get("gpu", {})),
            f35=F35Config(**data.get("f35", {})),
            ew=EWConfig(**data.get("ew", {})),
            cmmc=CMMCConfig(**data.get("cmmc", {})),
            swarm=SwarmConfig(**data.get("swarm", {})),
        )


# Default configuration instance
DEFAULT_CONFIG = ApexConfig()
