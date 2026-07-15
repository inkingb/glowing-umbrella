#!/usr/bin/env python3
"""连接云效项目并查询缺陷（Bug）列表。

配置分层（低 → 高）：
  builtin → config/default.json → config/local.json → --config → 环境变量 → CLI
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import describe_layers, load_config  # noqa: E402
from yunxiao_api import YunxiaoClient, YunxiaoError  # noqa: E402


def _fmt_ts(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        ts = int(value)
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return str(value)


def _user_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "-")
    return str(value or "-")


def _status_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("displayName") or value.get("name") or "-")
    return str(value or "-")


def _bug_row(item: dict[str, Any]) -> dict[str, str]:
    return {
        "serial": str(item.get("serialNumber") or "-"),
        "subject": str(item.get("subject") or "-"),
        "status": _status_name(item.get("status")),
        "assignedTo": _user_name(item.get("assignedTo")),
        "creator": _user_name(item.get("creator")),
        "gmtCreate": _fmt_ts(item.get("gmtCreate")),
        "id": str(item.get("id") or "-"),
    }


def _print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("未找到缺陷。")
        return
    headers = ["serial", "subject", "status", "assignedTo", "creator", "gmtCreate", "id"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            # 标题过长时截断显示，避免表格爆炸
            cell = row.get(h, "")
            if h == "subject" and len(cell) > 48:
                cell = cell[:45] + "..."
                row[h] = cell
            widths[h] = max(widths[h], len(cell))

    def line(vals: dict[str, str]) -> str:
        return "  ".join(vals[h].ljust(widths[h]) for h in headers)

    print(line({h: h for h in headers}))
    print(line({h: "-" * widths[h] for h in headers}))
    for row in rows:
        print(line(row))


def _cli_overrides(args: argparse.Namespace) -> dict[str, Any]:
    yunxiao: dict[str, Any] = {}
    query: dict[str, Any] = {}
    output: dict[str, Any] = {}

    if args.token is not None:
        yunxiao["token"] = args.token
    if args.org_id is not None:
        yunxiao["org_id"] = args.org_id
    if args.domain is not None:
        yunxiao["domain"] = args.domain
    if args.project_id is not None:
        yunxiao["project_id"] = args.project_id
    if args.project_name is not None:
        yunxiao["project_name"] = args.project_name

    if args.category is not None:
        query["category"] = args.category
    if args.page is not None:
        query["page"] = args.page
    if args.per_page is not None:
        query["per_page"] = args.per_page
    if args.order_by is not None:
        query["order_by"] = args.order_by
    if args.sort is not None:
        query["sort"] = args.sort
    if args.keyword is not None:
        query["keyword"] = args.keyword
    if args.all:
        query["fetch_all"] = True
    if args.conditions is not None:
        query["conditions"] = args.conditions

    if args.json:
        output["format"] = "json"
    elif args.format is not None:
        output["format"] = args.format

    patch: dict[str, Any] = {}
    if yunxiao:
        patch["yunxiao"] = yunxiao
    if query:
        patch["query"] = query
    if output:
        patch["output"] = output
    return patch


def fetch_bugs(config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    client = YunxiaoClient.from_config(config)
    yx = config["yunxiao"]
    query = config["query"]

    project = client.resolve_project(
        project_id=yx.get("project_id") or None,
        project_name=yx.get("project_name") or None,
    )
    space_id = str(project.get("id") or "")
    if not space_id:
        raise YunxiaoError("无法解析项目 ID。")

    keyword = (query.get("keyword") or "").strip() or None
    conditions = query.get("conditions") or None
    per_page = int(query.get("per_page") or 20)
    meta_headers: dict[str, str] = {}

    if query.get("fetch_all"):
        bugs = client.iter_workitems(
            space_id=space_id,
            category=str(query.get("category") or "Bug"),
            space_type=str(query.get("space_type") or "Project"),
            per_page=per_page,
            order_by=str(query.get("order_by") or "gmtCreate"),
            sort=str(query.get("sort") or "desc"),
            keyword=keyword,
            conditions=conditions,
        )
    else:
        bugs, meta_headers = client.search_workitems(
            space_id=space_id,
            category=str(query.get("category") or "Bug"),
            space_type=str(query.get("space_type") or "Project"),
            page=int(query.get("page") or 1),
            per_page=per_page,
            order_by=str(query.get("order_by") or "gmtCreate"),
            sort=str(query.get("sort") or "desc"),
            keyword=keyword,
            conditions=conditions,
        )

    return project, bugs, meta_headers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="连接云效项目并查询缺陷（Bug）列表",
    )
    parser.add_argument(
        "--config-dir",
        help="配置目录，默认仓库下 config/",
    )
    parser.add_argument(
        "--config",
        help="额外配置文件路径（优先级高于 local.json）",
    )
    parser.add_argument(
        "--show-config-layers",
        action="store_true",
        help="打印配置分层来源后退出",
    )
    parser.add_argument("--token", help="覆盖 token")
    parser.add_argument("--org-id", help="覆盖组织 ID")
    parser.add_argument("--domain", help="覆盖 API 域名")
    parser.add_argument("--project-id", help="项目 ID（spaceId）")
    parser.add_argument("--project-name", help="项目名称（用于解析 ID）")
    parser.add_argument(
        "--category",
        default=None,
        help="工作项类型，默认 Bug",
    )
    parser.add_argument("--keyword", "-k", help="按标题关键字过滤")
    parser.add_argument("--page", type=int, help="页码")
    parser.add_argument("--per-page", type=int, help="每页条数 1-200")
    parser.add_argument("--all", action="store_true", help="自动翻页拉取全部")
    parser.add_argument("--order-by", choices=("gmtCreate", "name"))
    parser.add_argument("--sort", choices=("desc", "asc"))
    parser.add_argument("--conditions", help="自定义 conditions JSON 字符串")
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        help="输出格式，默认 table",
    )
    parser.add_argument("--json", action="store_true", help="等价于 --format json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.show_config_layers:
        for line in describe_layers(
            config_dir=args.config_dir,
            extra_config=args.config,
        ):
            print(line)
        return 0

    try:
        config = load_config(
            config_dir=args.config_dir,
            extra_config=args.config,
            cli_overrides=_cli_overrides(args),
        )
        per_page = int(config["query"].get("per_page") or 20)
        if not 1 <= per_page <= 200:
            parser.error("query.per_page / --per-page 需在 1-200 之间")

        project, bugs, headers = fetch_bugs(config)
    except (YunxiaoError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    fmt = str((config.get("output") or {}).get("format") or "table")
    project_label = project.get("name") or project.get("id")

    if fmt == "json":
        print(
            json.dumps(
                {
                    "project": {
                        "id": project.get("id"),
                        "name": project.get("name"),
                    },
                    "total": headers.get("x-total") or len(bugs),
                    "bugs": bugs,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"# project={project_label} id={project.get('id')}", file=sys.stderr)
    if headers.get("x-total") is not None:
        print(
            f"# page={headers.get('x-page', config['query'].get('page'))} "
            f"perPage={headers.get('x-per-page', config['query'].get('per_page'))} "
            f"total={headers.get('x-total')}",
            file=sys.stderr,
        )
    else:
        print(f"# fetched={len(bugs)}", file=sys.stderr)

    _print_table([_bug_row(b) for b in bugs])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
