"""通用工具"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session


def serialize_model(obj: Any) -> dict[str, Any]:
    """把 SQLAlchemy ORM 对象序列化成可 JSON 化的 dict"""
    if obj is None:
        return {}
    result: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            result[column.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[column.name] = float(value)
        else:
            result[column.name] = value
    return result


def round2(value: float | None) -> float:
    return round(float(value or 0), 2)
