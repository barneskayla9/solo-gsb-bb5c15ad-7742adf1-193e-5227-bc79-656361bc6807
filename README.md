# 供水管网故障隔离服务

基于 **Python 3.11 + FastAPI + PostgreSQL + SQLAlchemy** 实现。录入带编号的水源、用水点、连接点及两端节点明确的管段（管段可设阀门）；针对故障管段预演关阀隔离方案，校验通过后可原子提交。

## 一、核心业务规则

### 导入校验（`POST /network/import`）

整网原子导入，以下情况一次性收集全部错误并拒绝（HTTP 422），库中状态不变：

- **悬空端点**：管段的起点/终点在节点表中不存在；
- **重号**：节点编号或管段编号重复；
- **自环**：管段起点与终点为同一节点；
- 无阀管段标记为阀门关闭。

导入成功后版本号重置为 **1**，全部阀门按导入数据给定的初始状态生效。

### 隔离判定

把管网视为**无向图**（水沿管段双向流动）。方案图中移除：

1. 故障管段；
2. 拟关闭阀门所在管段；
3. 所有此前已经关闭的阀门所在管段（**已关闭阀门继续生效**）。

只有故障管段的**两个端点**在方案图中都**无法从任一水源到达**，方案才可提交。

### 失供用水点（仅预演/响应中返回）

`失供 = 提交前由任一水源可达的用水点 − 方案后可达的用水点`

即只统计本次关阀新造成的失供点；此前已失供的点不计入。结果按编号排序（字符串序，编号建议定宽补零，如 `U01`）。

### 提交的事务保证（`POST /isolation/commit`）

提交在单个数据库事务中执行 `network_meta` 单行 `SELECT ... FOR UPDATE`，基于当前版本重新做全部校验。以下情况**拒绝且完全不改状态**（阀位、版本均不变）：

| 拒绝原因 | HTTP | error.code |
| --- | --- | --- |
| 版本过期（请求版本 ≠ 当前版本） | 409 | `version_conflict` |
| 拟关闭管段上没有阀门 | 422 | `edge_without_valve` |
| 请求中重复关闭 / 阀门此前已关闭 | 422 | `duplicate_close` / `valve_already_closed` |
| 管段或故障管段不存在 | 422 | `edge_not_found` / `fault_edge_not_found` |
| 不能隔离（至少一端仍可达水源） | 422 | `isolation_not_achievable` |
| 尚未导入管网 | 409 | `network_not_initialized` |

校验全部通过后：原子地把拟关闭阀门置为关闭，并把版本号 **+1**。

> 预演接口（`/isolation/preview`）只读、不改状态；同样要求传入读取时的版本号，版本过期返回 409，便于尽早发现过期读取；不能隔离时返回 200 且 `can_isolate=false`（预演是咨询性的）。

## 二、一键启动

前置：已安装 Docker 与 Docker Compose v2。

```bash
docker compose up --build
```

启动内容：

- **PostgreSQL 16** 容器 `water-db`，端口 **5432**，带健康检查，数据持久化到命名卷 `water_pgdata`；
- **API** 容器 `water-api`，端口 **8000**，等待数据库健康后启动；
- API 启动时自动执行幂等建表（`app/schema.sql`）并初始化数据库；
- 默认写入一套环形**演示管网**（可通过 `SEED_DEMO=false` 关闭）。

停止 / 清空数据：

```bash
docker compose down          # 停止
docker compose down -v       # 停止并删除数据库卷（下次启动重新初始化演示数据）
```

服务地址：

- 健康检查：<http://localhost:8000/health>
- Swagger UI：<http://localhost:8000/docs>
- ReDoc：<http://localhost:8000/redoc>
- OpenAPI JSON：<http://localhost:8000/openapi.json>

## 三、配置

通过环境变量（或项目根目录 `.env`，参考 `.env.example`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://water:water@localhost:5432/water_network` | SQLAlchemy/psycopg2 连接串；compose 中指向 `db:5432` |
| `SEED_DEMO` | `true` | 首次启动且库为空时是否写入演示管网 |

compose 中数据库账号/密码/库名：`water / water / water_network`。

### 本地（不用 Docker）运行

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 自行准备 PostgreSQL，并设好 DATABASE_URL
uvicorn app.main:app --reload --port 8000
```

## 四、HTTP API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| POST | `/network/import` | 整网导入（原子替换，版本重置为 1） |
| GET | `/network` | 查询当前管网及版本号 |
| POST | `/isolation/preview` | 预演：能否隔离 + 失供用水点（只读） |
| POST | `/isolation/commit` | 提交：重新校验并原子更新阀位与版本 |

### 1) 导入管网

```bash
curl -sS -X POST http://localhost:8000/network/import \
  -H 'Content-Type: application/json' \
  --data @examples/network_sample.json
```

```json
{
  "nodes": [
    {"code": "S1", "kind": "source",  "name": "一水厂"},
    {"code": "J1", "kind": "junction","name": "连接点1"},
    {"code": "U1", "kind": "sink",    "name": "用水点1"}
  ],
  "edges": [
    {"code": "P1", "from_code": "S1", "to_code": "J1", "has_valve": true, "valve_closed": false},
    {"code": "P2", "from_code": "J1", "to_code": "U1", "has_valve": false}
  ]
}
```

`kind` 取值：`source`（水源）/ `junction`（连接点）/ `sink`（用水点）。
`valve_closed` 仅在 `has_valve=true` 时允许为 `true`。允许两条管段连接同一对节点（并行管段，编号不同即可）。

导入失败响应（422）示例：

```json
{
  "error": {
    "code": "import_validation_failed",
    "message": "管网导入校验失败，共 3 处错误",
    "details": {
      "errors": [
        {"code": "duplicate_node",     "message": "节点编号重复：S1", "ref": "S1"},
        {"code": "dangling_endpoint",  "message": "管段 P1 的终点 GHOST 未定义（悬空端点）", "ref": "GHOST"},
        {"code": "self_loop",          "message": "管段 P2 两端节点相同（自环）", "ref": "P2"}
      ]
    }
  }
}
```

### 2) 预演隔离方案

演示管网为外环 `J1-P2-J2-P3-J3-P4-J4-P5-J5-P6-J1`，故障管段 `P3`（J2-J3，无阀）。

```bash
curl -sS -X POST http://localhost:8000/isolation/preview \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2","P4"],"version":1}'
```

响应（`can_isolate=true`：两端均不可达；`lost_sinks` 为新失供点，按编号排序）：

```json
{
  "can_isolate": true,
  "fault_edge": "P3",
  "version": 1,
  "closed_valves": ["P2", "P4"],
  "lost_sinks": ["U1", "U3"],
  "reachable_sinks_before": ["U1", "U2", "U3"],
  "reachable_sinks_after": ["U2"],
  "fault_endpoint_reachable": {"from": false, "to": false}
}
```

只关一个阀时无法隔离（预演返回 200，`can_isolate=false`）：

```bash
curl -sS -X POST http://localhost:8000/isolation/preview \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2"],"version":1}'
```

### 3) 提交方案

```bash
curl -sS -X POST http://localhost:8000/isolation/commit \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2","P4"],"version":1}'
```

成功后 `P2`、`P4` 阀门关闭，版本变为 **2**（响应中的 `version` 即新版本）。

不能隔离时提交被拒（422，状态不变）：

```bash
curl -i -X POST http://localhost:8000/isolation/commit \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2"],"version":1}'
```

```json
{
  "error": {
    "code": "isolation_not_achievable",
    "message": "故障管段 P3 无法隔离：起点仍可达=False，终点仍可达=True",
    "details": {"fault_edge": "P3", "fault_endpoint_reachable": {"from": false, "to": true}}
  }
}
```

版本过期时提交被拒（409，状态不变）：

```json
{
  "error": {
    "code": "version_conflict",
    "message": "管网版本已过期：请求基于版本 1，当前版本为 2",
    "details": {"requested_version": 1, "current_version": 2}
  }
}
```

### 4) 一键跑全部调用示例

```bash
chmod +x examples/demo.sh
./examples/demo.sh                 # 默认 http://localhost:8000
```

脚本依次演示：成功预演、不能隔离提交被拒、无阀管段/重复关闭拒绝、成功提交、版本过期拒绝、已关阀门继续生效的二次隔离、自定义导入、非法导入。

## 五、测试

图算法与方案校验为纯 Python 实现，无需数据库即可运行：

```bash
python3 -m unittest discover -s tests -v
```

## 六、项目结构

```
.
├── app/
│   ├── main.py          # FastAPI 入口、生命周期（建表/演示数据）、统一错误处理
│   ├── config.py        # 环境变量配置
│   ├── database.py      # 建表与数据库就绪等待
│   ├── schema.sql       # 幂等 DDL（nodes / edges / network_meta）
│   ├── models.py        # SQLAlchemy ORM、引擎与会话工厂
│   ├── schemas.py       # Pydantic 请求/响应模型
│   ├── graph.py         # 无向图可达性、隔离判定、失供差集、方案校验（纯逻辑）
│   ├── repo.py          # ORM 行 -> Graph 装配
│   ├── demo.py          # 演示管网数据
│   └── routers/
│       ├── network.py   # 导入 / 查询
│       └── isolation.py # 预演 / 提交（事务 + FOR UPDATE）
├── examples/            # 调用示例（JSON + demo.sh）
├── tests/test_graph.py  # 纯逻辑单元测试
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
