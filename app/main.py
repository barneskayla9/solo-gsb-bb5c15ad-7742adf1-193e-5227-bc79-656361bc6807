import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import init_db
from .demo import DEMO_EDGES, DEMO_NODES
from .errors import APIError
from .models import EdgeRow, MetaRow, NodeRow, SessionLocal
from .routers import isolation, network

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("water-network")
settings = get_settings()


def seed_demo_network() -> None:
    """库为空且开启 SEED_DEMO 时写入环形演示管网。"""
    db = SessionLocal()
    try:
        with db.begin():
            meta = db.get(MetaRow, 1, with_for_update=True)
            if meta.initialized:
                return
            db.add_all(
                [NodeRow(code=n.code, kind=n.kind, name=n.name) for n in DEMO_NODES]
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
                    for e in DEMO_EDGES
                ]
            )
            meta.version = 1
            meta.initialized = True
        logger.info("已写入演示管网（%d 个节点，%d 个管段）", len(DEMO_NODES), len(DEMO_EDGES))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.seed_demo:
        seed_demo_network()
    yield


app = FastAPI(
    title="供水管网故障隔离服务",
    version="1.0.0",
    description=(
        "录入水源/用水点/连接点与带阀门管段；针对故障管段预演并提交关阀隔离方案。\n\n"
        "交互式文档：Swagger UI `/docs`，ReDoc `/redoc`。"
    ),
    lifespan=lifespan,
)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request_validation_failed",
                "message": "请求参数校验失败",
                "details": {"errors": exc.errors()},
            }
        },
    )


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(network.router)
app.include_router(isolation.router)
