from datetime import datetime, timezone
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, JSON, Numeric, LargeBinary, Text, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(12), default='user')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(2), default='uz')
    theme: Mapped[str] = mapped_column(String(10), default='light')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class Recovery(Base):
    __tablename__ = 'recoveries'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Station(Base):
    __tablename__ = 'stations'
    __table_args__ = (CheckConstraint('latitude >= -90 AND latitude <= 90'), CheckConstraint('longitude >= -180 AND longitude <= 180'))
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(400))
    descriptions: Mapped[dict] = mapped_column(JSON, default=dict)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    hours: Mapped[dict] = mapped_column(JSON, default=dict)
    is_24h: Mapped[bool] = mapped_column(Boolean, default=False)
    override: Mapped[str] = mapped_column(String(12), default='normal')
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    products: Mapped[list['Product']] = relationship(cascade='all, delete-orphan', lazy='selectin')

class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (UniqueConstraint('station_id', 'category', 'name'), CheckConstraint('price IS NULL OR price >= 0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id', ondelete='CASCADE'), index=True)
    category: Mapped[str] = mapped_column(String(12), index=True)
    name: Mapped[str] = mapped_column(String(80))
    price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    unit: Mapped[str] = mapped_column(String(12))
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    pressure: Mapped[float | None] = mapped_column(Float)
    pressure_unit: Mapped[str | None] = mapped_column(String(8))
    pressure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    power_kw: Mapped[float | None] = mapped_column(Float)
    connectors: Mapped[list] = mapped_column(JSON, default=list)
    connector_available: Mapped[int | None] = mapped_column(Integer)

class Favorite(Base):
    __tablename__ = 'favorites'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Visit(Base):
    __tablename__ = 'visits'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    route_id: Mapped[str] = mapped_column(ForeignKey('route_sessions.id'), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index('ix_visit_account_station_time', 'user_id', 'station_id', 'created_at'),)

class Rating(Base):
    __tablename__ = 'ratings'
    __table_args__ = (CheckConstraint('stars >= 1 AND stars <= 5'),)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), primary_key=True)
    stars: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class RouteSession(Base):
    __tablename__ = 'route_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'))
    live_origin: Mapped[bool] = mapped_column(Boolean)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived: Mapped[bool] = mapped_column(Boolean, default=False)

class Support(Base):
    __tablename__ = 'support_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default='new')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(80))
    station_id: Mapped[int | None] = mapped_column(ForeignKey('stations.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class RateLimit(Base):
    __tablename__ = 'rate_limits'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)

class ProviderCache(Base):
    __tablename__ = 'provider_cache'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
