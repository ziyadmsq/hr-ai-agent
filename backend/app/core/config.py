from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://hr_saas:hr_saas_dev@localhost:5432/hr_saas"

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None

    # Groq
    GROQ_API_KEY: Optional[str] = None

    # WhatsApp (Twilio)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"  # Twilio sandbox default

    # Email (SMTP)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "hr-assistant@example.com"
    SMTP_USE_TLS: bool = True

    # SendGrid (alternative email provider)
    SENDGRID_API_KEY: Optional[str] = None

    # Webhook verification
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = "hr-saas-whatsapp-verify"
    EMAIL_WEBHOOK_SECRET: Optional[str] = None

    # App
    APP_NAME: str = "AI HR SaaS Platform"
    DEBUG: bool = False

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

