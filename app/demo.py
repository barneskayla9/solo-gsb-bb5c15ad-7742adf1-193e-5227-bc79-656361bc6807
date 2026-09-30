"""环形演示管网（首次启动、库为空且 SEED_DEMO=true 时写入）。

  S1 —P1— J1 —P2— J2 —P3(故障演示,无阀)— J3 —P4— J4 —P5— J5
                   |                          |             |
                   P7                         P8            P6
                   |                          |             |
                   U1                         U2            |
                                       U3 —P9(无阀)— J3     |
                                                          J1
  外环：J1-P2-J2-P3-J3-P4-J4-P5-J5-P6-J1（环）

场景一：故障 P3（J2-J3），关闭 P2、P4 可隔离，失供 U1、U3，U2 经环另一侧保供。
场景二：提交后 P2/P4 已关闭，故障 P5（J4-J5），再关 P6 可隔离，仅 U2 失供
       （U1/U3 此前已失供，不计入）。
"""

from .schemas import EdgeIn, NodeIn

DEMO_NODES = [
    NodeIn(code="S1", kind="source", name="一水厂"),
    NodeIn(code="J1", kind="junction", name="连接点1"),
    NodeIn(code="J2", kind="junction", name="连接点2"),
    NodeIn(code="J3", kind="junction", name="连接点3"),
    NodeIn(code="J4", kind="junction", name="连接点4"),
    NodeIn(code="J5", kind="junction", name="连接点5"),
    NodeIn(code="U1", kind="sink", name="用水点1"),
    NodeIn(code="U2", kind="sink", name="用水点2"),
    NodeIn(code="U3", kind="sink", name="用水点3"),
]

DEMO_EDGES = [
    EdgeIn(code="P1", from_code="S1", to_code="J1", has_valve=True),
    EdgeIn(code="P2", from_code="J1", to_code="J2", has_valve=True),
    EdgeIn(code="P3", from_code="J2", to_code="J3", has_valve=False, name="故障演示管段"),
    EdgeIn(code="P4", from_code="J3", to_code="J4", has_valve=True),
    EdgeIn(code="P5", from_code="J4", to_code="J5", has_valve=True),
    EdgeIn(code="P6", from_code="J5", to_code="J1", has_valve=True),
    EdgeIn(code="P7", from_code="J2", to_code="U1", has_valve=True),
    EdgeIn(code="P8", from_code="J4", to_code="U2", has_valve=True),
    EdgeIn(code="P9", from_code="J3", to_code="U3", has_valve=False),
]
