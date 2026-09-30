from sqlalchemy import Boolean, CheckConstraint, Column, Integer, SmallInteger, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


class NodeRow(Base):
    __tablename__ = "nodes"

    code = Column(String(128), primary_key=True)
    kind = Column(String(16), nullable=False)
    name = Column(String(255))

    __table_args__ = (CheckConstraint("kind in ('source','junction','sink')", name="chk_nodes_kind"),)


class EdgeRow(Base):
    __tablename__ = "edges"

    code = Column(String(128), primary_key=True)
    from_code = Column(String(128), nullable=False)
    to_code = Column(String(128), nullable=False)
    has_valve = Column(Boolean, nullable=False, default=False)
    valve_closed = Column(Boolean, nullable=False, default=False)
    name = Column(String(255))

    __table_args__ = (
        CheckConstraint("valve_closed = FALSE OR has_valve = TRUE", name="chk_edges_valve"),
    )


class MetaRow(Base):
    __tablename__ = "network_meta"

    id = Column(SmallInteger, primary_key=True, default=1)
    version = Column(Integer, nullable=False, default=1)
    initialized = Column(Boolean, nullable=False, default=False)

    __table_args__ = (CheckConstraint("id = 1", name="chk_meta_singleton"),)


_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
