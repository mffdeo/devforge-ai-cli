from pathlib import Path

import yaml
from pydantic import BaseModel


class DevForgeConfig(BaseModel):
    project_name: str
    edition: str = "community"
    audit_enabled: bool = True
    output_format: str = "markdown+json"
    cloud_login: bool = False


def write_config(path: Path, config: DevForgeConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)


def read_config(path: Path) -> DevForgeConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return DevForgeConfig(**data)
