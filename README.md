# 云效（Yunxiao）简易工具

连接云效组织/项目，查询项目列表与项目下缺陷（Bug）列表。仅依赖 Python 3 标准库。

## 配置分层

优先级从低到高，后者覆盖前者：

| 层级 | 来源 | 说明 |
| --- | --- | --- |
| 1 | 代码内置默认值 | 安全默认，不含密钥 |
| 2 | `config/default.json` | 团队公共默认（可入库） |
| 3 | `config/local.json` | 本机私密配置（**勿提交**） |
| 4 | `--config` 文件 | 临时/环境叠加 |
| 5 | 环境变量 `YUNXIAO_*` | 适合 CI |
| 6 | 命令行参数 | 当前调用最高优先级 |

```bash
cp config/local.json.example config/local.json
# 编辑 local.json：填入 token / org_id / project_id 或 project_name
```

查看当前会加载哪些层：

```bash
python3 scripts/list_bugs.py --show-config-layers
```

### 常用配置项

```json
{
  "yunxiao": {
    "domain": "https://openapi-rdc.aliyuncs.com",
    "token": "pt-xxxx",
    "org_id": "your-org-id",
    "project_id": "",
    "project_name": "我的项目"
  },
  "query": {
    "category": "Bug",
    "page": 1,
    "per_page": 20,
    "keyword": "",
    "fetch_all": false
  },
  "output": {
    "format": "table"
  }
}
```

也可使用环境变量：`YUNXIAO_TOKEN`、`YUNXIAO_ORG_ID`、`YUNXIAO_DOMAIN`、`YUNXIAO_PROJECT_ID`、`YUNXIAO_PROJECT_NAME`。

Token 权限建议：

- 项目协作 > 项目 > 只读
- 项目协作 > 工作项 > 只读

组织 ID 可从 `https://devops.aliyun.com/organization/<orgId>` 获取。

## 用法

### 1. 列出组织下项目

```bash
python3 scripts/list_projects.py
python3 scripts/list_projects.py --keyword demo --json
```

### 2. 连接项目并查询 Bug 列表

```bash
# 使用 local.json 中的 project_id / project_name
python3 scripts/list_bugs.py

# 指定项目
python3 scripts/list_bugs.py --project-name "示例项目"
python3 scripts/list_bugs.py --project-id <spaceId>

# 按标题关键字过滤 / 拉全量 / JSON
python3 scripts/list_bugs.py -k 登录 --all --json
```

## 文件结构

| 路径 | 说明 |
| --- | --- |
| `config/default.json` | 公共默认配置 |
| `config/local.json.example` | 本机配置模板 |
| `scripts/config_loader.py` | 分层配置加载 |
| `scripts/yunxiao_api.py` | 云效 API 客户端 |
| `scripts/list_projects.py` | 查询项目列表 |
| `scripts/list_bugs.py` | 查询项目 Bug 列表 |
