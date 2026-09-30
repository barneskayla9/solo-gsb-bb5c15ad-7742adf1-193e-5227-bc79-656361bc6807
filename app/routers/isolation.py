"""故障隔离：预演（只读）与提交（原子更新阀位和版本）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..errors import APIError
from ..graph import analyze, issues_to_api_error, validate_plan
from ..models import EdgeRow, MetaRow
from ..repo import load_graph
from ..schemas import IsolationPreviewRequest, IsolationResultResponse
from .deps import get_db

router = APIRouter(tags=["isolation"])


def _ensure_initialized(meta: MetaRow) -> None:
    if meta is None or not meta.initialized:
        raise APIError(status_code=409, code="network_not_initialized", message="尚未导入管网，请先调用 /network/import")


def _check_version(current: int, requested: int) -> None:
    if current != requested:
        raise APIError(
            status_code=409,
            code="version_conflict",
            message=f"管网版本已过期：请求基于版本 {requested}，当前版本为 {current}",
            details={"requested_version": requested, "current_version": current},
        )


def _to_response(result, fault_edge: str, version: int, proposed_closed: list[str]) -> IsolationResultResponse:
    return IsolationResultResponse(
        can_isolate=result.can_isolate,
        fault_edge=fault_edge,
        version=version,
        closed_valves=sorted(dict.fromkeys(proposed_closed)),
        lost_sinks=list(result.lost_sinks),
        reachable_sinks_before=list(result.reachable_sinks_before),
        reachable_sinks_after=list(result.reachable_sinks_after),
        fault_endpoint_reachable={
            "from": result.fault_u_reachable_after,
            "to": result.fault_v_reachable_after,
        },
    )


@router.post("/isolation/preview", response_model=IsolationResultResponse)
def preview(req: IsolationPreviewRequest, db: Session = Depends(get_db)):
    """预演：不改任何状态，返回能否隔离与失供用水点。

    已关闭阀门继续生效；版本过期、无阀管段、重复关闭等同样拒绝。
    """
    meta = db.get(MetaRow, 1)
    _ensure_initialized(meta)
    _check_version(meta.version, req.version)

    graph, version = load_graph(db)
    issues = validate_plan(graph, req.fault_edge, req.proposed_closed)
    if issues:
        raise issues_to_api_error(issues)

    result = analyze(graph, req.fault_edge, req.proposed_closed)
    return _to_response(result, req.fault_edge, version, req.proposed_closed)


@router.post("/isolation/commit", response_model=IsolationResultResponse)
def commit(req: IsolationPreviewRequest, db: Session = Depends(get_db)):
    """提交隔离方案。

    基于当前版本在单个事务内重新校验：版本过期 / 无阀管段 / 重复关闭 /
    不能隔离时一律回滚，不改变任何阀位与版本。通过后原子关闭阀门并把版本 +1。
    """
    # 事务起点：锁定版本单行，串行化并发提交
    with db.begin():
        meta = db.get(MetaRow, 1, with_for_update=True)
        _ensure_initialized(meta)
        _check_version(meta.version, req.version)

        # 在锁内重新加载当前管网
        graph, current_version = load_graph(db)
        issues = validate_plan(graph, req.fault_edge, req.proposed_closed)
        if issues:
            raise issues_to_api_error(issues)

        result = analyze(graph, req.fault_edge, req.proposed_closed)
        if not result.can_isolate:
            raise APIError(
                status_code=422,
                code="isolation_not_achievable",
                message=(
                    f"故障管段 {req.fault_edge} 无法隔离："
                    f"起点仍可达={result.fault_u_reachable_after}，"
                    f"终点仍可达={result.fault_v_reachable_after}"
                ),
                details={
                    "fault_edge": req.fault_edge,
                    "fault_endpoint_reachable": {
                        "from": result.fault_u_reachable_after,
                        "to": result.fault_v_reachable_after,
                    },
                    "reachable_sinks_after": list(result.reachable_sinks_after),
                },
            )

        # 原子更新阀位（版本行锁已保证无并发写入）
        targets = sorted(set(req.proposed_closed))
        if targets:
            db.query(EdgeRow).filter(EdgeRow.code.in_(targets)).update(
                {EdgeRow.valve_closed: True}, synchronize_session=False
            )
        meta.version = current_version + 1

        new_version = current_version + 1

    # 事务已提交后返回（闭包外仍可访问 result）
    return _to_response(result, req.fault_edge, new_version, targets)
