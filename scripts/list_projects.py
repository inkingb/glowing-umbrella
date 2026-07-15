#!/usr/bin/env python3
"""查询阿里云云效项目列表。

配置分层与 list_bugs.py 相同：
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

from config_loader import load_config  # noqa: E402
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


def _project_row(item: dict[str, Any]) -> dict[str, str]:
    status = item.get("status") or {}
    if isinstance(status, dict):
        status_name = status.get("name") or "-"
    else:
        status_name = str(status)
    creator = item.get("creator") or {}
    creator_name = creator.get("name") if isinstance(creator, dict) else "-"
    return {
        "id": str(item.get("id") or "-"),
        "name": str(item.get("name") or "-"),
        "customCode": str(item.get("customCode") or "-"),
        "status": status_name,
        "scope": str(item.get("scope") or "-"),
        "logicalStatus": str(item.get("logicalStatus") or "-"),
        "creator": str(creator_name or "-"),
        "gmtCreate": _fmt_ts(item.get("gmtCreate")),
    }


def _print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("未找到项目。")
        return
    headers = ["id", "name", "customCode", "status", "scope", "creator", "gmtCreate"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(row.get(h, "")))

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
    if args.extra_conditions is not None:
        query["extra_conditions"] = args.extra_conditions
    if args.json:
        output["format"] = "json"

    patch: dict[str, Any] = {}
    if yunxiao:
        patch["yunxiao"] = yunxiao
    if query:
        patch["query"] = query
    if output:
        patch["output"] = output
    return patch


def fetch_projects(config: dict[str, Any]) -> list[dict[str, Any]]:
    client = YunxiaoClient.from_config(config)
    query = config.get("query") or {}
    keyword = (query.get("keyword") or "").strip() or None
    per_page = int(query.get("per_page") or 20)

    if not query.get("fetch_all"):
        projects, headers = client.search_projects(
            page=int(query.get("page") or 1),
            per_page=per_page,
            order_by=str(query.get("order_by") or "gmtCreate"),
            sort=str(query.get("sort") or "desc"),
            keyword=keyword,
            conditions=query.get("conditions"),
            extra_conditions=query.get("extra_conditions"),
        )
        total = headers.get("x-total")
        fmt = str((config.get("output") or {}).get("format") or "table")
        if fmt != "json" and total is not None:
            print(
                f"# page={headers.get('x-page', query.get('page'))} "
                f"perPage={headers.get('x-per-page', per_page)} "
                f"total={total}",
                file=sys.stderr,
            )
        return projects

    page = 1
    all_projects: list[dict[str, Any]] = []
    while True:
        projects, headers = client.search_projects(
            page=page,
            per_page=per_page,
            order_by=str(query.get("order_by") or "gmtCreate"),
            sort=str(query.get("sort") or "desc"),
            keyword=keyword,
            conditions=query.get("conditions"),
            extra_conditions=query.get("extra_conditions"),
        )
        all_projects.extend(projects)
        total_pages = headers.get("x-total-pages")
        next_page = headers.get("x-next-page")
        if not projects:
            break
        if next_page:
            try:
                page = int(next_page)
                continue
            except ValueError:
                pass
        if total_pages:
            try:
                if page >= int(total_pages):
                    break
            except ValueError:
                pass
        if len(projects) < per_page:
            break
        page += 1
        if page > 1000:
            raise YunxiaoError("分页超过 1000 页，已中止，请缩小查询范围。")

    fmt = str((config.get("output") or {}).get("format") or "table")
    if fmt != "json":
        print(f"# fetched={len(all_projects)}", file=sys.stderr)
    return all_projects


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="查询阿里云云效项目列表（SearchProjects）",
    )
    parser.add_argument("--config-dir", help="配置目录，默认仓库下 config/")
    parser.add_argument("--config", help="额外配置文件")
    parser.add_argument("--token", help="个人访问令牌")
    parser.add_argument("--org-id", help="组织 ID")
    parser.add_argument("--domain", help="API 域名")
    parser.add_argument("--keyword", "-k", help="按项目名称关键字过滤")
    parser.add_argument("--page", type=int, help="页码")
    parser.add_argument("--per-page", type=int, help="每页条数，1-200")
    parser.add_argument("--all", action="store_true", help="自动翻页拉取全部项目")
    parser.add_argument("--order-by", choices=("gmtCreate", "name"))
    parser.add_argument("--sort", choices=("desc", "asc"))
    parser.add_argument("--conditions", help="自定义 conditions JSON 字符串")
    parser.add_argument("--extra-conditions", help="额外过滤条件 JSON 字符串")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(
            config_dir=args.config_dir,
            extra_config=args.config,
            cli_overrides=_cli_overrides(args),
        )
        per_page = int((config.get("query") or {}).get("per_page") or 20)
        if not 1 <= per_page <= 200:
            parser.error("--per-page 需在 1-200 之间")
        projects = fetch_projects(config)
    except (YunxiaoError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    fmt = str((config.get("output") or {}).get("format") or "table")
    if fmt == "json":
        print(json.dumps(projects, ensure_ascii=False, indent=2))
    else:
        _print_table([_project_row(p) for p in projects])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
