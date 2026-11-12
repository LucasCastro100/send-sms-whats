"""Configuração do backend (lê o `.env` do backend e o da raiz do projeto)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Gestão de Membros API"
    secret_key: str = "dev-secret-mude-isto"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'app.db'}"
    # Pasta com os arquivos antigos (data.pdf, CSV, generos.json, exclusoes.json).
    data_dir: str = str(ROOT_DIR / "data")
    uploads_dir: str = str(BACKEND_DIR / "data" / "uploads")
    token_horas: int = 24 * 7
    cookie_name: str = "cb_session"
    cookie_secure: bool = False
    # `lax` funciona quando o painel e a API estão na mesma origem (proxy do
    # Next). Com o front em outro domínio (Vercel), use `none` + `secure=true`.
    cookie_samesite: str = "lax"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    evolution_base_url: str = "https://evolution.ideiasdev.tech"
    evolution_apikey: str = ""
    evolution_global_apikey: str = ""
    evolution_instance: str = "igreja-bot"
    evolution_instance_prefix: str = "cb-"

    # Grupos de destino do disparo manual/automático.
    jid_grupo_icm: str = "553498018995-1503451609@g.us"
    nome_grupo_icm: str = "ICM - IGREJA BOA VISTA"
    jid_grupo_zoom: str = ""
    nome_grupo_zoom: str = "Zoom"

    # Disparo diário automático (horário de Brasília), sempre pela tabela `icm`.
    disparo_automatico: bool = True
    disparo_hora: int = 7
    disparo_minuto: int = 0
    disparo_fonte: str = "icm"

    # Usuários iniciais (JSON, mesmo formato do APP_USERS do Streamlit).
    app_users: str = ""

    # Fallback quando não existe APP_USERS.
    admin_usuario: str = "lucas"
    admin_senha: str = "trocar123"
    admin_nome: str = "Lucas"

    def lista_cors(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origins.split(",") if origem.strip()]


settings = Settings()
