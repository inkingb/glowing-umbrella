#!/usr/bin/env python3
"""查询阿里云云效（Yunxiao）项目列表。

依赖环境变量：
  YUNXIAO_TOKEN   个人访问令牌（请求头 x-yunxiao-token）
  YUNXIAO_ORG_ID  组织 / 企业 ID

可选：
  YUNXIAO_DOMAIN  API 域名，默认 https://openapi-rdc.aliyuncs.com

用法示例：
  export YUNXIAO_TOKEN=pt-xxxx
  export YUNXIAO_ORG_ID=your-org-id
  python3 scripts/list_projects.py
  python3 scripts/list_projects.py --keyword demo --json
  python3 scripts/list_projects.py --all --per-page 50
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 允许直接执行本文件：python3 scripts/list_projects.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yunxiao_api import YunxiaoClient, YunxiaoError  # noqa: E402


def _fmt_ts(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        # 云效常返回毫秒时间戳（字符串或数字）
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


def fetch_projects(args: argparse.Namespace) -> list[dict[str, Any]]:
    client = YunxiaoClient(
        token=args.token,
        organization_id=args.org_id,
        domain=args.domain,
    )

    if not args.all:
        projects, headers = client.search_projects(
            page=args.page,
            per_page=args.per_page,
            order_by=args.order_by,
            sort=args.sort,
            keyword=args.keyword,
            conditions=args.conditions,
            extra_conditions=args.extra_conditions,
        )
        total = headers.get("x-total")
        if not args.json and total is not None:
            print(
                f"# page={headers.get('x-page', args.page)} "
                f"perPage={headers.get('x-per-page', args.per_page)} "
                f"total={total}",
                file=sys.stderr,
            )
        return projects

    # 拉取全部页
    page = 1
    per_page = args.per_page
    all_projects: list[dict[str, Any]] = []
    while True:
        projects, headers = client.search_projects(
            page=page,
            per_page=per_page,
            order_by=args.order_by,
            sort=args.sort,
            keyword=args.keyword,
            conditions=args.conditions,
            extra_conditions=args.extra_conditions,
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

    if not args.json:
        print(f"# fetched={len(all_projects)}", file=sys.stderr)
    return all_projects


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="查询阿里云云效项目列表（SearchProjects）",
    )
    parser.add_argument(
        "--token",
        help="个人访问令牌，默认读 YUNXIAO_TOKEN",
    )
    parser.add_argument(
        "--org-id",
        help="组织 ID，默认读 YUNXIAO_ORG_ID",
    )
    parser.add_argument(
        "--domain",
        help="API 域名，默认读 YUNXIAO_DOMAIN 或中心版域名",
    )
    parser.add_argument(
        "--keyword",
        "-k",
        help="按项目名称关键字过滤",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=20,
        help="每页条数，1-200，默认 20",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="自动翻页拉取全部项目",
    )
    parser.add_argument(
        "--order-by",
        choices=("gmtCreate", "name"),
        default="gmtCreate",
        help="排序字段，默认 gmtCreate",
    )
    parser.add_argument(
        "--sort",
        choices=("desc", "asc"),
        default="desc",
        help="排序方向，默认 desc",
    )
    parser.add_argument(
        "--conditions",
        help="自定义 conditions JSON 字符串（覆盖 --keyword）",
    )
    parser.add_argument(
        "--extra-conditions",
        help="额外过滤条件 JSON 字符串（如我参与的/我管理的）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出原始 JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not 1 <= args.per_page <= 200:
        parser.error("--per-page 需在 1-200 之间")

    try:
        projects = fetch_projects(args)
    except YunxiaoError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(projects, ensure_ascii=False, indent=2))
    else:
        _print_table([_project_row(p) for p in projects])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
