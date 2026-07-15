# 云效项目列表查询脚本

基于阿里云云效 OpenAPI [`SearchProjects`](https://help.aliyun.com/zh/yunxiao/developer-reference/searchprojects) 查询组织下的项目列表。仅依赖 Python 3 标准库。

## 准备

1. 在云效创建**个人访问令牌**（个人设置 → 个人访问令牌），需具备「项目协作 > 项目 > 只读」。
2. 获取**组织 ID**：打开 `https://devops.aliyun.com/organization/<orgId>`，或在组织管理后台基本信息页查看。

```bash
export YUNXIAO_TOKEN='pt-xxxx'
export YUNXIAO_ORG_ID='your-org-id'
# 可选，默认中心版
# export YUNXIAO_DOMAIN='https://openapi-rdc.aliyuncs.com'
```

也可复制 `.env.example` 为本地配置文件后自行 `source`。

## 用法

```bash
# 表格输出（默认第 1 页，每页 20 条）
python3 scripts/list_projects.py

# 按名称关键字过滤
python3 scripts/list_projects.py --keyword demo

# 自动翻页拉取全部
python3 scripts/list_projects.py --all --per-page 50

# 输出原始 JSON
python3 scripts/list_projects.py --json

# 命令行传入凭证（不写入环境变量）
python3 scripts/list_projects.py --token pt-xxxx --org-id your-org-id
```

## 文件

| 路径 | 说明 |
| --- | --- |
| `scripts/list_projects.py` | CLI：查询并打印项目列表 |
| `scripts/yunxiao_api.py` | 云效 API 客户端（SearchProjects） |
| `.env.example` | 环境变量示例 |

## curl 等价示例

```bash
curl -sS -X POST \
  "https://openapi-rdc.aliyuncs.com/oapi/v1/projex/organizations/${YUNXIAO_ORG_ID}/projects:search" \
  -H "Content-Type: application/json" \
  -H "x-yunxiao-token: ${YUNXIAO_TOKEN}" \
  --data '{"orderBy":"gmtCreate","page":1,"perPage":20,"sort":"desc"}'
```
