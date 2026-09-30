from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置，全部可通过同名大写环境变量覆盖。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL 连接串（SQLAlchemy 方言）
    database_url: str = "postgresql+psycopg2://water:water@localhost:5432/water_network"
    # 首次启动且库为空时是否写入演示管网
    seed_demo: bool = True
    app_name: str = "water-network-isolation"


@lru_cache
def get_settings() -> Settings:
    return Settings()
