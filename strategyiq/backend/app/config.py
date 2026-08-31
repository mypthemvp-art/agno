from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://strategyiq:strategyiq@localhost:5432/strategyiq"
    redis_url: str = "redis://localhost:6379/0"

    polygon_api_key: str = ""
    coingecko_api_key: str = ""
    fmp_api_key: str = ""
    grok_api_key: str = ""

    pinecone_api_key: str = ""
    pinecone_index: str = "strategyiq"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_elite_price_id: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    screener_cache_ttl: int = 900  # 15 minutes

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
