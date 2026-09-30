"""从 ORM 行装配纯逻辑层使用的 Graph。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .graph import Edge, Graph, Node
from .models import EdgeRow, MetaRow, NodeRow


def load_graph(db: Session) -> tuple[Graph, int]:
    """读取当前管网及版本号。"""
    nodes = {
        row.code: Node(code=row.code, kind=row.kind, name=row.name)
        for row in db.execute(select(NodeRow)).scalars()
    }
    edges = {
        row.code: Edge(
            code=row.code,
            from_code=row.from_code,
            to_code=row.to_code,
            has_valve=row.has_valve,
            valve_closed=row.valve_closed,
            name=row.name,
        )
        for row in db.execute(select(EdgeRow)).scalars()
    }
    version = db.get(MetaRow, 1).version
    return Graph(nodes=nodes, edges=edges), version
