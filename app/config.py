from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Monad / EVM
    monad_rpc_url: str = "https://testnet-rpc.monad.xyz"
    chain_id: int = 10143
    contract_address: str = ""
    private_key: str = ""

    # AI
    ai_mode: str = "mock"  # "mock" | "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Storage
    storage_backend: str = "local"  # "local" | "ipfs"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Derived paths (not from env)
    @property
    def reports_dir(self) -> Path:
        path = BASE_DIR / "data" / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def metadata_dir(self) -> Path:
        path = BASE_DIR / "data" / "metadata"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def abi_path(self) -> Path:
        return BASE_DIR.parent / "abi" / "GreenReceiptNFT.json"


settings = Settings()
