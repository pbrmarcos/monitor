"""Personalização: perfil, nomes das frentes e cores. Tudo fica na tabela de configurações."""
import json
import re

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from .models import FRONTS, Setting

DEFAULT_THEME = {'primary': '#0D213A', 'accent': '#00D7EC'}
DEFAULT_PROFILE = {'name': 'Marcos', 'tagline': 'Seu espaço pessoal', 'avatar': ''}
AVATAR = re.compile(r'^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$')
COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')


def luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first: str, second: str) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class Preferences(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    tagline: str = Field(default='', max_length=60)
    avatar: str = Field(default='', max_length=200_000)
    fronts: list[str] = Field(min_length=4, max_length=4)
    primary: str
    accent: str

    @field_validator('name', 'tagline')
    @classmethod
    def trimmed(cls, value):
        return value.strip()

    @field_validator('avatar')
    @classmethod
    def image(cls, value):
        if value and not AVATAR.match(value):
            raise ValueError('Use uma imagem PNG, JPEG ou WebP.')
        return value

    @field_validator('fronts')
    @classmethod
    def names(cls, value):
        cleaned = [name.strip() for name in value]
        if any(not 1 <= len(name) <= 30 for name in cleaned):
            raise ValueError('Cada frente precisa de um nome com até 30 caracteres.')
        return cleaned

    @field_validator('primary', 'accent')
    @classmethod
    def color(cls, value):
        if not COLOR.match(value):
            raise ValueError('Informe a cor no formato #RRGGBB.')
        return value.upper()

    @field_validator('primary')
    @classmethod
    def readable(cls, value):
        # A cor principal é fundo do menu e dos botões e também cor do texto: precisa ser escura.
        if contrast(value, '#FFFFFF') < 7:
            raise ValueError('Escolha uma cor principal mais escura, para o texto continuar legível.')
        return value


def _load(db: Session, key: str, default):
    row = db.get(Setting, key)
    try:
        return json.loads(row.value) if row else default
    except ValueError:
        return default


def front_names(db: Session) -> dict[int, str]:
    saved = _load(db, 'front_names', None)
    names = saved if isinstance(saved, list) and len(saved) == 4 else list(FRONTS.values())
    return {index + 1: str(name) for index, name in enumerate(names)}


def read(db: Session) -> dict:
    profile = {**DEFAULT_PROFILE, **_load(db, 'profile', {})}
    theme = {**DEFAULT_THEME, **_load(db, 'theme', {})}
    return {**profile, 'fronts': list(front_names(db).values()), **theme}


def save(db: Session, payload: Preferences) -> dict:
    db.merge(Setting(key='profile', value=json.dumps({'name': payload.name, 'tagline': payload.tagline, 'avatar': payload.avatar})))
    db.merge(Setting(key='front_names', value=json.dumps(payload.fronts, ensure_ascii=False)))
    db.merge(Setting(key='theme', value=json.dumps({'primary': payload.primary, 'accent': payload.accent})))
    db.commit()
    return read(db)
