from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(override=True)


BASE_DIR = Path(__file__).resolve().parents[1]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _domain(url: str) -> str | None:
    parsed = urlparse(url)
    return parsed.netloc or None


@dataclass(frozen=True)
class Settings:
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", os.getenv("BASE_URL", "https://openrouter.ai/api/v1"))
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", os.getenv("MODEL", "openai/gpt-4o-mini"))
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "http://localhost")
    openrouter_app_name: str = os.getenv("OPENROUTER_APP_NAME", "energy-seihr")
    data_national_grid: str | None = os.getenv("DATA_NATIONAL_GRID")
    data_carbon_intensity_api: str | None = os.getenv("DATA_CARBON_INTENSITY_API")
    data_defra_pm25: str | None = os.getenv("DATA_DEFRA_PM25")
    data_nhs_fingertips: str | None = os.getenv("DATA_NHS_FINGERTIPS")
    tavily_allowed_urls: list[str] = None
    hosted_data_dir: Path = BASE_DIR / "hosted-data"
    outputs_dir: Path = BASE_DIR / "outputs"
    backtest_start: str = os.getenv("BACKTEST_START", "2021-01-01")
    backtest_split: str = os.getenv("BACKTEST_SPLIT", "2023-04-01")
    backtest_end: str = os.getenv("BACKTEST_END", "2024-12-31")
    default_region: str = os.getenv("DEFAULT_REGION", "UK_Yorkshire")
    default_simulation_years: int = int(os.getenv("DEFAULT_SIMULATION_YEARS", "5"))

    def __post_init__(self) -> None:
        urls = _split_csv(os.getenv("TAVILY_ALLOWED_URLS"))
        if not urls:
            urls = [
                item
                for item in [
                    self.data_national_grid,
                    self.data_carbon_intensity_api,
                    self.data_defra_pm25,
                    self.data_nhs_fingertips,
                ]
                if item
            ]
        object.__setattr__(self, "tavily_allowed_urls", urls)

    @property
    def tavily_allowed_domains(self) -> list[str]:
        domains = [_domain(url) for url in self.tavily_allowed_urls]
        return sorted({domain for domain in domains if domain})


settings = Settings()
