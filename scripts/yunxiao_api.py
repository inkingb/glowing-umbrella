#!/usr/bin/env python3
"""云效 OpenAPI 基础客户端。"""

from __future__ import annotations

import json
import os
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
        self.token = token or os.environ.get("YUNXIAO_TOKEN", "").strip()
        self.organization_id = (
            organization_id or os.environ.get("YUNXIAO_ORG_ID", "").strip()
        )
        self.domain = (
            domain
            or os.environ.get("YUNXIAO_DOMAIN", "").strip()
            or DEFAULT_DOMAIN
        ).rstrip("/")

        if not self.token:
            raise YunxiaoError(
                "缺少个人访问令牌。请设置环境变量 YUNXIAO_TOKEN，"
                "或在云效「个人设置 > 个人访问令牌」创建后传入。"
            )
        if not self.organization_id:
            raise YunxiaoError(
                "缺少组织 ID。请设置环境变量 YUNXIAO_ORG_ID，"
                "可在组织管理后台基本信息页或 URL "
                "https://devops.aliyun.com/organization/<orgId> 中获取。"
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
        if payload is None:
            return [], headers
        if isinstance(payload, list):
            return payload, headers
        if isinstance(payload, dict):
            for key in ("result", "data", "projects", "list"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value, headers
        raise YunxiaoError(f"无法解析项目列表响应: {payload!r}")
