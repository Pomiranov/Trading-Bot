from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent


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
    token: str = field(default_factory=lambda: os.getenv("TINKOFF_TOKEN", "").strip())
    account_id: str = field(default_factory=lambda: os.getenv("TINKOFF_ACCOUNT_ID", "").strip())
    sandbox: bool = field(default_factory=lambda: os.getenv("TINKOFF_SANDBOX", "true").lower() == "true")


@dataclass
class TelegramConfig:
    token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "").strip())
    chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip())
    allowed_chat_ids: list = field(default_factory=lambda: [
        int(x) for x in os.getenv("TELEGRAM_ALLOWED_IDS", "").split(",")
        if x.strip().lstrip("-").isdigit()
    ])


@dataclass
class DashboardConfig:
    host: str = field(default_factory=lambda: os.getenv("DASHBOARD_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "5001")))
    api_key: str = field(default_factory=lambda: os.getenv("DASHBOARD_API_KEY", "").strip())
    require_api_key_for_reads: bool = field(
        default_factory=lambda: os.getenv("DASHBOARD_REQUIRE_API_KEY", "false").lower() == "true"
    )


@dataclass
class BybitConfig:
    api_key: str = field(default_factory=lambda: os.getenv("BYBIT_API_KEY", "").strip())
    api_secret: str = field(default_factory=lambda: os.getenv("BYBIT_API_SECRET", "").strip())
    testnet: bool = field(default_factory=lambda: os.getenv("BYBIT_TESTNET", "false").lower() == "true")


@dataclass
class RiskConfig:
    max_position_pct: float = field(default_factory=lambda: float(os.getenv("RISK_MAX_POSITION_PCT", "0.05")))
    atr_stop_multiplier: float = field(default_factory=lambda: float(os.getenv("RISK_ATR_STOP_MULT", "2.0")))
    max_daily_loss_pct: float = field(default_factory=lambda: float(os.getenv("RISK_MAX_DAILY_LOSS_PCT", "0.02")))
    max_open_positions: int = field(default_factory=lambda: int(os.getenv("RISK_MAX_OPEN_POSITIONS", "5")))


@dataclass
class SecretsConfig:
    master_key: str = field(default_factory=lambda: os.getenv("SECRETS_MASTER_KEY", "").strip())


@dataclass
class LoggingConfig:
    file_path: str = field(default_factory=lambda: os.getenv("LOG_FILE", "").strip())
    max_bytes: int = field(default_factory=lambda: int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024))))
    backup_count: int = field(default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5")))


@dataclass
class AppConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    tinkoff: TinkoffConfig = field(default_factory=TinkoffConfig)
    bybit: BybitConfig = field(default_factory=BybitConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    secrets: SecretsConfig = field(default_factory=SecretsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    moex_base_url: str = "https://iss.moex.com/iss"
    rules_dir: Path = PROJECT_ROOT / "knowledge" / "rules"
    rules_file: Path = PROJECT_ROOT / "knowledge" / "rules" / "rules.yaml"
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    tickers: list = field(default_factory=lambda: os.getenv(
        "TICKERS", "SBER,GAZP,LKOH,YNDX,NVTK"
    ).split(","))

    poll_interval: int = field(default_factory=lambda: int(os.getenv("POLL_INTERVAL", "60")))


config = AppConfig()