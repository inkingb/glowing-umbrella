#!/usr/bin/env python3
"""config_loader 单元测试（不访问网络）。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from config_loader import deep_merge, load_config


class ConfigLoaderTest(unittest.TestCase):
    def test_deep_merge(self) -> None:
        base = {"yunxiao": {"token": "a", "org_id": "1"}, "query": {"page": 1}}
        override = {"yunxiao": {"token": "b"}, "query": {"per_page": 50}}
        merged = deep_merge(base, override)
        self.assertEqual(merged["yunxiao"]["token"], "b")
        self.assertEqual(merged["yunxiao"]["org_id"], "1")
        self.assertEqual(merged["query"]["page"], 1)
        self.assertEqual(merged["query"]["per_page"], 50)

    def test_layers_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "default.json").write_text(
                json.dumps({"yunxiao": {"org_id": "from-default", "token": "d"}}),
                encoding="utf-8",
            )
            (root / "local.json").write_text(
                json.dumps({"yunxiao": {"token": "from-local"}}),
                encoding="utf-8",
            )
            extra = root / "extra.json"
            extra.write_text(
                json.dumps({"yunxiao": {"project_name": "P"}}),
                encoding="utf-8",
            )

            old = {k: os.environ.get(k) for k in ("YUNXIAO_ORG_ID", "YUNXIAO_TOKEN")}
            os.environ["YUNXIAO_ORG_ID"] = "from-env"
            os.environ.pop("YUNXIAO_TOKEN", None)
            try:
                cfg = load_config(
                    config_dir=root,
                    extra_config=extra,
                    cli_overrides={"yunxiao": {"project_id": "cli-id"}},
                )
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

            self.assertEqual(cfg["yunxiao"]["token"], "from-local")
            self.assertEqual(cfg["yunxiao"]["org_id"], "from-env")
            self.assertEqual(cfg["yunxiao"]["project_name"], "P")
            self.assertEqual(cfg["yunxiao"]["project_id"], "cli-id")


if __name__ == "__main__":
    unittest.main()
