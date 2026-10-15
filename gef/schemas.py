import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False, allow_inf_nan=False)

class Names(Strict):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    @field_validator('first_name','last_name')
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip(): raise ValueError('NAME_REQUIRED')
        return value.strip()

class Login(Strict):
    username: str = Field(min_length=3, max_length=32, pattern=r'^[A-Za-z0-9_]+$')
    password: str = Field(min_length=8, max_length=128)

class Registration(Login, Names):
    confirm_password: str
    confirmed: bool
    @model_validator(mode='after')
    def confirm(self):
        if self.password != self.confirm_password or not self.confirmed:
            raise ValueError('PASSWORD_MISMATCH')
        return self

class Reset(Login):
    recovery_code: str = Field(min_length=20, max_length=200)

class Password(Strict):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class Preferences(Strict):
    language: Literal['uz', 'ru', 'en']
    theme: Literal['light', 'dark']

class Point(Strict):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class ProductInput(Strict):
    category: Literal['fuel', 'metan', 'propan', 'elektr']
    name: str = Field(min_length=1, max_length=80)
    price: Decimal | None = Field(default=None, ge=0, le=100000000, decimal_places=2)
    unit: Literal['liter', 'm3', 'kwh', 'minute', 'session']
    available: bool = True
    pressure: float | None = Field(default=None, ge=0, le=10000)
    pressure_unit: Literal['bar', 'MPa'] | None = None
    pressure_at: datetime | None = None
    power_kw: float | None = Field(default=None, gt=0, le=2000)
    connectors: list[str] = Field(default_factory=list, max_length=20)
    connector_available: int | None = Field(default=None, ge=0, le=1000)
    @field_validator('name')
    @classmethod
    def name_nonblank(cls, value):
        if not value.strip(): raise ValueError('NAME_REQUIRED')
        return value.strip()
    @model_validator(mode='after')
    def compatible(self):
        units = {'fuel':['liter'], 'metan':['m3'], 'propan':['liter'], 'elektr':['kwh','minute','session']}
        if self.unit not in units[self.category]:
            raise ValueError('INCOMPATIBLE_UNIT')
        if self.category not in ['metan', 'propan'] and self.pressure is not None:
            raise ValueError('PRESSURE_CATEGORY')
        if self.pressure is not None and (not self.pressure_unit or not self.pressure_at):
            raise ValueError('PRESSURE_TIMESTAMP')
        if self.pressure_at:
            if self.pressure_at.tzinfo is None:
                raise ValueError('TIMEZONE_REQUIRED')
            if self.pressure_at > datetime.now(timezone.utc):
                raise ValueError('FUTURE_PRESSURE')
        if self.category != 'elektr' and (self.power_kw is not None or self.connectors or self.connector_available is not None):
            raise ValueError('EV_CATEGORY')
        if any(len(c) > 40 for c in self.connectors):
            raise ValueError('CONNECTOR_LENGTH')
        return self

class StationInput(Point):
    name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=2, max_length=400)
    descriptions: dict[str, str] = Field(default_factory=dict)
    hours: dict[str, list[list[str]]] = Field(default_factory=dict)
    is_24h: bool = False
    override: Literal['normal', 'open', 'closed'] = 'normal'
    published: bool = False
    products: list[ProductInput] = Field(min_length=1, max_length=40)
    request_key: str = Field(min_length=16, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    @field_validator('name','address')
    @classmethod
    def station_nonblank(cls, value):
        if len(value.strip())<2: raise ValueError('NAME_REQUIRED')
        return value.strip()
    @model_validator(mode='after')
    def valid_schedule(self):
        if any(k not in ['uz','ru','en'] or len(v) > 3000 for k,v in self.descriptions.items()):
            raise ValueError('DESCRIPTION_INVALID')
        if not self.is_24h and set(self.hours) != set(map(str,range(7))):
            raise ValueError('HOURS_REQUIRED')
        for day, intervals in self.hours.items():
            if day not in list(map(str,range(7))) or len(intervals) > 4:
                raise ValueError('HOURS_INVALID')
            for interval in intervals:
                if len(interval)!=2 or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', s) for s in interval) or interval[0]==interval[1]:
                    raise ValueError('HOURS_INVALID')
        keys = [(p.category,p.name) for p in self.products]
        if len(keys)!=len(set(keys)):
            raise ValueError('DUPLICATE_PRODUCT')
        return self

class RouteInput(Point):
    station_id: int = Field(gt=0)
    origin_kind: Literal['live','manual']
    route_id: str | None = Field(default=None, max_length=64)

class Arrival(Point):
    route_id: str = Field(max_length=64)
    accuracy: float = Field(gt=0, le=100)
    position_timestamp: datetime
    confirmed: bool

class Stars(Strict):
    stars: int = Field(ge=1, le=5)

class Message(Strict):
    message: str = Field(min_length=5, max_length=4000)
    @field_validator('message')
    @classmethod
    def nonblank(cls,value):
        if len(value.strip())<5: raise ValueError('MESSAGE_REQUIRED')
        return value.strip()

class Chat(Strict):
    message: str = Field(min_length=1, max_length=1500)
    language: Literal['uz','ru','en'] = 'uz'
    origin: Point | None = None

class SupportStatus(Strict):
    status: Literal['new','in_progress','resolved']

class TelegramData(Strict):
    init_data: str = Field(max_length=16000)
