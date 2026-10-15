import os
from urllib.parse import urlparse
from dataclasses import dataclass, field
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()  # Read only. No filesystem writes or network work at import time.

@dataclass(frozen=True)
class Settings:
    environment: str = field(default_factory=lambda: os.getenv('APP_ENV', 'development'))
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', ''))
    session_secret: str = field(default_factory=lambda: os.getenv('SESSION_SECRET', ''))
    origin: str = field(default_factory=lambda: os.getenv('APP_ORIGIN', '').rstrip('/'))
    session_days: int = field(default_factory=lambda: int(os.getenv('SESSION_DAYS', '7')))
    tile_url: str = field(default_factory=lambda: os.getenv('TILE_URL', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'))
    tile_attribution: str = field(default_factory=lambda: os.getenv('TILE_ATTRIBUTION', '© OpenStreetMap contributors'))
    tile_fallback_url: str = field(default_factory=lambda: os.getenv('TILE_FALLBACK_URL', ''))
    tile_fallback_attribution: str = field(default_factory=lambda: os.getenv('TILE_FALLBACK_ATTRIBUTION', ''))
    geocoding_url: str = field(default_factory=lambda: os.getenv('GEOCODING_URL', ''))
    geocoding_interval: int = field(default_factory=lambda: int(os.getenv('GEOCODING_MIN_INTERVAL', '1')))
    routing_url: str = field(default_factory=lambda: os.getenv('ROUTING_URL', ''))
    routing_interval: int = field(default_factory=lambda: int(os.getenv('ROUTING_MIN_INTERVAL', '1')))
    routing_key: str = field(default_factory=lambda: os.getenv('ROUTING_API_KEY', ''))
    provider_agent: str = field(default_factory=lambda: os.getenv('PROVIDER_USER_AGENT', 'GEF_system/1.0'))
    ai_url: str = field(default_factory=lambda: os.getenv('AI_BASE_URL', 'https://api.openai.com/v1'))
    ai_key: str = field(default_factory=lambda: os.getenv('AI_API_KEY', ''))
    ai_model: str = field(default_factory=lambda: os.getenv('AI_MODEL', 'gpt-4.1-mini'))
    telegram_token: str = field(default_factory=lambda: os.getenv('TELEGRAM_BOT_TOKEN', ''))
    support_url: str = field(default_factory=lambda: os.getenv('SUPPORT_CHAT_URL', 'https://t.me/WebShadoWin'))
    pressure_hours: int = field(default_factory=lambda: int(os.getenv('PRESSURE_FRESH_HOURS', '6')))
    @property
    def production(self):
        return self.environment == 'production'
    @property
    def secure_cookie(self):
        return self.production or self.origin.startswith('https://')
    def problem(self):
        if not self.database_url:
            return 'DATABASE_REQUIRED'
        if len(self.session_secret) < 32:
            return 'SECRET_REQUIRED'
        if self.production and self.database_url.startswith('sqlite'):
            return 'POSTGRES_REQUIRED'
        parsed=urlparse(self.origin)
        if self.production and (parsed.scheme!='https' or not parsed.hostname or parsed.path not in ['', '/'] or parsed.query or parsed.fragment):
            return 'ORIGIN_REQUIRED'
        return None

@lru_cache
def settings():
    return Settings()
