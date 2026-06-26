from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent


@dataclass
class DatabaseConfig:
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "trading_bot"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "trader"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass
class TinkoffConfig:
    token: str = field(default_factory=lambda: os.getenv("TINKOFF_TOKEN", ""))
    account_id: str = field(default_factory=lambda: os.getenv("TINKOFF_ACCOUNT_ID", ""))
    sandbox: bool = field(default_factory=lambda: os.getenv("TINKOFF_SANDBOX", "true").lower() == "true")


@dataclass
class TelegramConfig:
    token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))


@dataclass
class RiskConfig:
    max_position_pct: float = field(default_factory=lambda: float(os.getenv("RISK_MAX_POSITION_PCT", "0.05")))
    atr_stop_multiplier: float = field(default_factory=lambda: float(os.getenv("RISK_ATR_STOP_MULT", "2.0")))
    max_daily_loss_pct: float = field(default_factory=lambda: float(os.getenv("RISK_MAX_DAILY_LOSS_PCT", "0.02")))
    max_open_positions: int = field(default_factory=lambda: int(os.getenv("RISK_MAX_OPEN_POSITIONS", "5")))


@dataclass
class AppConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    tinkoff: TinkoffConfig = field(default_factory=TinkoffConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)

    moex_base_url: str = "https://iss.moex.com/iss"
    rules_file: Path = BASE_DIR / "knowledge" / "rules.yaml"
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Торгуемые тикеры по умолчанию
    tickers: list = field(default_factory=lambda: os.getenv(
        "TICKERS", "SBER,GAZP,LKOH,YNDX,NVTK"
    ).split(","))

    # Интервал опроса сигналов в секундах
    poll_interval: int = field(default_factory=lambda: int(os.getenv("POLL_INTERVAL", "60")))


config = AppConfig()
