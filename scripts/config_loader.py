#!/usr/bin/env python3
"""分层配置加载。

优先级（低 → 高，后者覆盖前者）：
  1. 代码内置默认值
  2. config/default.json
  3. config/local.json（本地私密覆盖，勿提交）
  4. 额外 --config 文件（可选）
  5. 环境变量 YUNXIAO_*
  6. 命令行参数（由调用方合并）
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

BUILTIN_DEFAULTS: dict[str, Any] = {
    "yunxiao": {
        "domain": "https://openapi-rdc.aliyuncs.com",
        "token": "",
        "org_id": "",
        "project_id": "",
        "project_name": "",
    },
    "query": {
        "category": "Bug",
        "space_type": "Project",
        "page": 1,
        "per_page": 20,
        "order_by": "gmtCreate",
        "sort": "desc",
        "keyword": "",
        "fetch_all": False,
    },
    "output": {
        "format": "table",
    },
}

ENV_MAP: dict[str, tuple[str, str]] = {
    # env_name -> (section, key)
    "YUNXIAO_TOKEN": ("yunxiao", "token"),
    "YUNXIAO_ORG_ID": ("yunxiao", "org_id"),
    "YUNXIAO_DOMAIN": ("yunxiao", "domain"),
    "YUNXIAO_PROJECT_ID": ("yunxiao", "project_id"),
    "YUNXIAO_PROJECT_NAME": ("yunxiao", "project_name"),
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"配置文件必须是 JSON 对象: {path}")
    return data


def _env_overrides() -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for env_name, (section, key) in ENV_MAP.items():
        value = os.environ.get(env_name)
        if value is None or value.strip() == "":
            continue
        patch.setdefault(section, {})[key] = value.strip()
    return patch


def load_config(
    *,
    config_dir: str | Path | None = None,
    extra_config: str | Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """加载分层配置并返回合并后的字典。"""
    root = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR

    cfg = deepcopy(BUILTIN_DEFAULTS)
    cfg = deep_merge(cfg, _load_json_file(root / "default.json"))
    cfg = deep_merge(cfg, _load_json_file(root / "local.json"))
    if extra_config:
        cfg = deep_merge(cfg, _load_json_file(Path(extra_config)))
    cfg = deep_merge(cfg, _env_overrides())
    if cli_overrides:
        cfg = deep_merge(cfg, cli_overrides)
    return cfg


def describe_layers(
    *,
    config_dir: str | Path | None = None,
    extra_config: str | Path | None = None,
) -> list[str]:
    """返回已生效的配置层说明（便于排查）。"""
    root = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    layers = [
        "1. builtin defaults",
        f"2. {root / 'default.json'} ({'yes' if (root / 'default.json').exists() else 'missing'})",
        f"3. {root / 'local.json'} ({'yes' if (root / 'local.json').exists() else 'missing'})",
    ]
    if extra_config:
        path = Path(extra_config)
        layers.append(f"4. {path} ({'yes' if path.exists() else 'missing'})")
    else:
        layers.append("4. extra --config (none)")
    env_hit = [name for name in ENV_MAP if os.environ.get(name)]
    layers.append(
        "5. env "
        + (f"[{', '.join(env_hit)}]" if env_hit else "(none)")
    )
    layers.append("6. CLI overrides (applied by caller)")
    return layers
