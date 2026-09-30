#!/usr/bin/env bash
# 供水管网故障隔离服务 —— 端到端调用示例
# 用法：./examples/demo.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://localhost:8000}"
j() { python3 -m json.tool 2>/dev/null || cat; }

echo "================ 0. 健康检查 ================"
curl -sS "$BASE/health" | j; echo

echo "================ 1. 读取当前管网（演示数据，版本=1） ================"
curl -sS "$BASE/network" | j; echo

echo "================ 2. 预演：故障 P5，只关 P6（版本1） ================"
curl -sS -X POST "$BASE/isolation/preview" -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P5","proposed_closed":["P6"],"version":1}' | j; echo

echo "================ 3. 提交（预期失败：不能隔离，422，状态不变） ================"
curl -sS -o /tmp/resp.json -w "HTTP %{http_code}\n" -X POST "$BASE/isolation/commit" \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P5","proposed_closed":["P6"],"version":1}'
cat /tmp/resp.json | j; echo

echo "================ 4. 预演：关闭无阀管段 P3（预期 422 invalid_plan） ================"
curl -sS -o /tmp/resp.json -w "HTTP %{http_code}\n" -X POST "$BASE/isolation/preview" \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P5","proposed_closed":["P3"],"version":1}'
cat /tmp/resp.json | j; echo

echo "================ 5. 预演：重复关闭 P6,P6（预期 422 duplicate_close） ================"
curl -sS -o /tmp/resp.json -w "HTTP %{http_code}\n" -X POST "$BASE/isolation/preview" \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P5","proposed_closed":["P6","P6"],"version":1}'
cat /tmp/resp.json | j; echo

echo "================ 6. 预演：故障 P3（无阀），关闭 P2、P4，版本1 ================"
curl -sS -X POST "$BASE/isolation/preview" -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2","P4"],"version":1}' | j; echo

echo "================ 7. 提交第 6 步方案（成功：版本 1 -> 2，P2/P4 关闭） ================"
curl -sS -X POST "$BASE/isolation/commit" -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2","P4"],"version":1}' | j; echo

echo "================ 8. 再次用旧版本 1 提交（预期 409 version_conflict） ================"
curl -sS -o /tmp/resp.json -w "HTTP %{http_code}\n" -X POST "$BASE/isolation/commit" \
  -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P3","proposed_closed":["P2","P4"],"version":1}'
cat /tmp/resp.json | j; echo

echo "================ 9. 已关阀门继续生效：版本2 下预演故障 P5 关 P6 ================"
echo "（P2/P4 已关，U1/U3 提交前已失供；仅 U2 计入失供）"
curl -sS -X POST "$BASE/isolation/preview" -H 'Content-Type: application/json' \
  -d '{"fault_edge":"P5","proposed_closed":["P6"],"version":2}' | j; echo

echo "================ 10. 导入自定义管网（示例 JSON） ================"
curl -sS -X POST "$BASE/network/import" -H 'Content-Type: application/json' \
  --data @"$(dirname "$0")/network_sample.json" | j; echo

echo "================ 11. 导入非法数据：悬空端点/重号/自环（预期 422） ================"
curl -sS -o /tmp/resp.json -w "HTTP %{http_code}\n" -X POST "$BASE/network/import" \
  -H 'Content-Type: application/json' -d '{
    "nodes": [
      {"code":"S1","kind":"source"},
      {"code":"S1","kind":"source"}
    ],
    "edges": [
      {"code":"P1","from_code":"S1","to_code":"GHOST","has_valve":false},
      {"code":"P2","from_code":"S1","to_code":"S1","has_valve":false},
      {"code":"P2","from_code":"S1","to_code":"S1","has_valve":false}
    ]
  }'
cat /tmp/resp.json | j; echo
