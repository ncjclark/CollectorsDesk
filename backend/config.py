from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    ebay_app_id: str = ""
    ebay_cert_id: str = ""
    ebay_dev_id: str = ""
    ebay_environment: str = "production"

    etsy_api_key: str = ""

    etsy_enabled: bool = True
    heritage_enabled: bool = True
    bgg_enabled: bool = True

    database_url: str = "sqlite:///./data/inventory.db"
    upload_dir: str = "./uploads"
    research_cache_ttl_hours: int = 24
    max_ebay_results: int = 100

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def ebay_finding_base_url(self) -> str:
        if self.ebay_environment == "sandbox":
            return "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"
        return "https://svcs.ebay.com/services/search/FindingService/v1"

    @property
    def ebay_browse_base_url(self) -> str:
        if self.ebay_environment == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"


settings = Settings()
