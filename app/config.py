"""
VisionClick Agent - Configuration module.
Loads from config.yaml, environment variables, and CLI args.
"""
import os
import yaml
from typing import Optional
from pydantic import BaseModel, Field


class BrowserConfig(BaseModel):
    headless: bool = False
    slow_mo: int = 0


class AgentConfig(BaseModel):
    dry_run: bool = True
    auto_submit: bool = False
    max_tasks: int = 10
    max_runtime_minutes: int = 60
    poll_interval: int = 2


class VisionConfig(BaseModel):
    provider: str = "mock"
    sample_fps: int = 4
    high_confidence: float = 0.90
    review_threshold: float = 0.75


class PerformanceConfig(BaseModel):
    workers: int = 4
    enable_cache: bool = True
    adaptive_sampling: bool = True


class DashboardConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class DemoConfig(BaseModel):
    url: str = "http://127.0.0.1:3000"


class AppConfig(BaseModel):
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    demo: DemoConfig = Field(default_factory=DemoConfig)
    db_path: str = "./data/visionclick.db"


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file, with env var overrides."""
    data = {}

    # Load YAML
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

    config = AppConfig(**data)

    # Environment variable overrides
    env_map = {
        "VISIONCLICK_HEADLESS": ("browser", "headless", lambda v: v.lower() == "true"),
        "VISIONCLICK_SLOW_MO": ("browser", "slow_mo", int),
        "VISIONCLICK_DRY_RUN": ("agent", "dry_run", lambda v: v.lower() == "true"),
        "VISIONCLICK_AUTO_SUBMIT": ("agent", "auto_submit", lambda v: v.lower() == "true"),
        "VISIONCLICK_MAX_TASKS": ("agent", "max_tasks", int),
        "VISIONCLICK_MAX_RUNTIME_MINUTES": ("agent", "max_runtime_minutes", int),
        "VISIONCLICK_VISION_PROVIDER": ("vision", "provider", str),
        "VISIONCLICK_DEMO_URL": ("demo", "url", str),
        "VISIONCLICK_DASHBOARD_HOST": ("dashboard", "host", str),
        "VISIONCLICK_DASHBOARD_PORT": ("dashboard", "port", int),
        "VISIONCLICK_DB_PATH": (None, "db_path", str),
    }

    for env_key, (section, attr, converter) in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            if section:
                sub = getattr(config, section)
                setattr(sub, attr, converter(val))
            else:
                setattr(config, attr, converter(val))

    return config
