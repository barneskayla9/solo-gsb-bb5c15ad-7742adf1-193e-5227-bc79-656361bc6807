"""管网导入与查询路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..errors import APIError
from ..models import EdgeRow, MetaRow, NodeRow
from ..repo import load_graph
from ..schemas import (
    EdgeOut,
    NetworkImportRequest,
    NetworkImportResponse,
    NetworkResponse,
    NodeOut,
)
from .deps import get_db

router = APIRouter(tags=["network"])


def _validate_import(payload: NetworkImportRequest) -> list[dict]:
    errors: list[dict] = []

    node_codes: set[str] = set()
    for n in payload.nodes:
        if n.code in node_codes:
            errors.append({"code": "duplicate_node", "message": f"节点编号重复：{n.code}", "ref": n.code})
        node_codes.add(n.code)

    edge_codes: set[str] = set()
    for e in payload.edges:
        if e.code in edge_codes:
            errors.append({"code": "duplicate_edge", "message": f"管段编号重复：{e.code}", "ref": e.code})
        edge_codes.add(e.code)
        if e.from_code == e.to_code:
            errors.append({"code": "self_loop", "message": f"管段 {e.code} 两端节点相同（自环）", "ref": e.code})
        if e.from_code not in node_codes:
            errors.append(
                {"code": "dangling_endpoint", "message": f"管段 {e.code} 的起点 {e.from_code} 未定义（悬空端点）", "ref": e.from_code}
            )
        if e.to_code not in node_codes:
            errors.append(
                {"code": "dangling_endpoint", "message": f"管段 {e.code} 的终点 {e.to_code} 未定义（悬空端点）", "ref": e.to_code}
            )
        if e.valve_closed and not e.has_valve:
            errors.append(
                {"code": "closed_valve_without_valve", "message": f"管段 {e.code} 没有阀门却标记为阀门关闭", "ref": e.code}
            )
    return errors


@router.post("/network/import", response_model=NetworkImportResponse)
def import_network(payload: NetworkImportRequest, db: Session = Depends(get_db)):
    """整网导入：全部校验通过后原子替换管网，版本重置为 1。

    拒绝：节点/管段重号、自环、悬空端点、无阀管段标记关阀。
    """
    errors = _validate_import(payload)
    if errors:
        raise APIError(
            status_code=422,
            code="import_validation_failed",
            message="管网导入校验失败，共 {} 处错误".format(len(errors)),
            details={"errors": errors},
        )

    with db.begin():
        # 先锁版本单行，与隔离提交互斥
        meta = db.get(MetaRow, 1, with_for_update=True)
        db.query(EdgeRow).delete(synchronize_session=False)
        db.query(NodeRow).delete(synchronize_session=False)
        db.add_all(
            [
                NodeRow(code=n.code, kind=n.kind, name=n.name)
                for n in payload.nodes
            ]
        )
        db.add_all(
            [
                EdgeRow(
                    code=e.code,
                    from_code=e.from_code,
                    to_code=e.to_code,
                    has_valve=e.has_valve,
                    valve_closed=e.valve_closed,
                    name=e.name,
                )
                for e in payload.edges
            ]
        )
        meta.version = 1
        meta.initialized = True

    return NetworkImportResponse(
        version=1,
        node_count=len(payload.nodes),
        edge_count=len(payload.edges),
        message="管网导入成功，版本已重置为 1",
    )


@router.get("/network", response_model=NetworkResponse)
def get_network(db: Session = Depends(get_db)):
    """读取当前版本的完整管网。"""
    meta = db.get(MetaRow, 1)
    graph, version = load_graph(db)
    return NetworkResponse(
        version=version,
        nodes=[
            NodeOut(code=n.code, kind=n.kind, name=n.name)
            for n in sorted(graph.nodes.values(), key=lambda x: x.code)
        ],
        edges=[
            EdgeOut(
                code=e.code,
                from_code=e.from_code,
                to_code=e.to_code,
                has_valve=e.has_valve,
                valve_closed=e.valve_closed,
                name=e.name,
            )
            for e in sorted(graph.edges.values(), key=lambda x: x.code)
        ],
    )
