#!/usr/bin/env python3
"""云效 OpenAPI 客户端：项目与缺陷（Bug）查询。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_DOMAIN = "https://openapi-rdc.aliyuncs.com"


class YunxiaoError(RuntimeError):
    """云效 API 调用失败。"""


class YunxiaoClient:
    def __init__(
        self,
        token: str | None = None,
        organization_id: str | None = None,
        domain: str | None = None,
    ) -> None:
        self.token = (token or "").strip()
        self.organization_id = (organization_id or "").strip()
        self.domain = (domain or DEFAULT_DOMAIN).rstrip("/")

        if not self.token:
            raise YunxiaoError(
                "缺少个人访问令牌。请在 config/local.json 设置 yunxiao.token，"
                "或设置环境变量 YUNXIAO_TOKEN。"
            )
        if not self.organization_id:
            raise YunxiaoError(
                "缺少组织 ID。请在 config/local.json 设置 yunxiao.org_id，"
                "或设置环境变量 YUNXIAO_ORG_ID。"
            )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> YunxiaoClient:
        yx = config.get("yunxiao") or {}
        return cls(
            token=yx.get("token"),
            organization_id=yx.get("org_id"),
            domain=yx.get("domain") or DEFAULT_DOMAIN,
        )

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        url = f"{self.domain}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "x-yunxiao-token": self.token,
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                payload = json.loads(raw) if raw else None
                response_headers = {k.lower(): v for k, v in resp.headers.items()}
                return payload, response_headers
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise YunxiaoError(
                f"HTTP {exc.code} {exc.reason}: {detail or '(empty body)'}"
            ) from exc
        except urllib.error.URLError as exc:
            raise YunxiaoError(f"网络请求失败: {exc.reason}") from exc

    @staticmethod
    def _as_list(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        raise YunxiaoError(f"无法解析列表响应: {payload!r}")

    def search_projects(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        order_by: str = "gmtCreate",
        sort: str = "desc",
        keyword: str | None = None,
        conditions: str | None = None,
        extra_conditions: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """调用 SearchProjects，返回 (项目列表, 响应头)。"""
        if conditions is None and keyword:
            conditions = json.dumps(
                {
                    "conditionGroups": [
                        [
                            {
                                "className": "string",
                                "fieldIdentifier": "name",
                                "format": "input",
                                "operator": "BETWEEN",
                                "toValue": None,
                                "value": [keyword],
                            }
                        ]
                    ]
                },
                ensure_ascii=False,
            )

        body: dict[str, Any] = {
            "orderBy": order_by,
            "page": page,
            "perPage": per_page,
            "sort": sort,
        }
        if conditions:
            body["conditions"] = conditions
        if extra_conditions:
            body["extraConditions"] = extra_conditions

        path = (
            f"/oapi/v1/projex/organizations/{self.organization_id}/projects:search"
        )
        payload, headers = self.request("POST", path, body)
        return self._as_list(payload, ("result", "data", "projects", "list")), headers

    def resolve_project(
        self,
        *,
        project_id: str | None = None,
        project_name: str | None = None,
    ) -> dict[str, Any]:
        """按 ID 或名称定位项目。名称匹配优先精确相等，否则取唯一前缀/包含匹配。"""
        pid = (project_id or "").strip()
        pname = (project_name or "").strip()
        if pid:
            return {"id": pid, "name": pname or pid}

        if not pname:
            raise YunxiaoError(
                "未指定项目。请在配置中设置 yunxiao.project_id 或 "
                "yunxiao.project_name，或使用 --project-id / --project-name。"
            )

        projects, _ = self.search_projects(
            page=1,
            per_page=50,
            keyword=pname,
            order_by="name",
            sort="asc",
        )
        exact = [p for p in projects if str(p.get("name") or "") == pname]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise YunxiaoError(f"项目名「{pname}」精确匹配到多个项目，请改用 project_id。")

        partial = [
            p
            for p in projects
            if pname.lower() in str(p.get("name") or "").lower()
        ]
        if len(partial) == 1:
            return partial[0]
        if not partial:
            raise YunxiaoError(f"未找到名称包含「{pname}」的项目。")
        names = ", ".join(str(p.get("name")) for p in partial[:10])
        raise YunxiaoError(
            f"项目名「{pname}」匹配到多个项目（{names}），请改用 --project-id。"
        )

    def search_workitems(
        self,
        *,
        space_id: str,
        category: str = "Bug",
        space_type: str = "Project",
        page: int = 1,
        per_page: int = 20,
        order_by: str = "gmtCreate",
        sort: str = "desc",
        keyword: str | None = None,
        conditions: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """调用 SearchWorkitems；category=Bug 时查询缺陷列表。"""
        if not space_id:
            raise YunxiaoError("space_id / project_id 不能为空。")

        if conditions is None and keyword:
            conditions = json.dumps(
                {
                    "conditionGroups": [
                        [
                            {
                                "fieldIdentifier": "subject",
                                "operator": "CONTAINS",
                                "value": [keyword],
                                "toValue": None,
                                "className": "string",
                                "format": "input",
                            }
                        ]
                    ]
                },
                ensure_ascii=False,
            )

        body: dict[str, Any] = {
            "category": category,
            "spaceId": space_id,
            "spaceType": space_type or "Project",
            "orderBy": order_by,
            "page": page,
            "perPage": per_page,
            "sort": sort,
        }
        if conditions:
            body["conditions"] = conditions

        path = (
            f"/oapi/v1/projex/organizations/{self.organization_id}/workitems:search"
        )
        payload, headers = self.request("POST", path, body)
        return self._as_list(payload, ("result", "data", "workitems", "list")), headers

    def iter_workitems(
        self,
        *,
        space_id: str,
        category: str = "Bug",
        space_type: str = "Project",
        per_page: int = 20,
        order_by: str = "gmtCreate",
        sort: str = "desc",
        keyword: str | None = None,
        conditions: str | None = None,
        max_pages: int = 1000,
    ) -> list[dict[str, Any]]:
        """自动翻页拉取全部工作项。"""
        page = 1
        items: list[dict[str, Any]] = []
        while page <= max_pages:
            batch, headers = self.search_workitems(
                space_id=space_id,
                category=category,
                space_type=space_type,
                page=page,
                per_page=per_page,
                order_by=order_by,
                sort=sort,
                keyword=keyword,
                conditions=conditions,
            )
            items.extend(batch)
            if not batch:
                break
            next_page = headers.get("x-next-page")
            total_pages = headers.get("x-total-pages")
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
            if len(batch) < per_page:
                break
            page += 1
        else:
            raise YunxiaoError(f"分页超过 {max_pages} 页，已中止。")
        return items
