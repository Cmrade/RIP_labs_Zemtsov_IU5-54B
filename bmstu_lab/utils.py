import json
from decimal import Decimal
from datetime import date, datetime
from django.db.models import Model
from django.db.models.query import QuerySet


class DecimalEncoder(json.JSONEncoder):
    """Кастомный JSON encoder для обработки Decimal и других несериализуемых типов"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Если Decimal представляет целое число, возвращаем int
            if obj == int(obj):
                return int(obj)
            # Иначе возвращаем float
            return float(obj)
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, Model):
            return str(obj)
        elif isinstance(obj, QuerySet):
            return list(obj.values())
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)


def decimal_to_float(obj):
    """Рекурсивно преобразует все Decimal в int или float в словаре или списке"""
    if isinstance(obj, Decimal):
        # Если Decimal представляет целое число, преобразуем в int
        if obj == int(obj):
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(v) for v in obj]
    else:
        return obj


def ensure_int_values(data, fields):
    """Убедиться, что указанные поля содержат целочисленные значения"""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in fields and value is not None:
                try:
                    data[key] = int(value)
                except (ValueError, TypeError):
                    data[key] = 0
        # Рекурсивно обработать вложенные словари и списки
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                data[key] = ensure_int_values(value, fields)
    elif isinstance(data, list):
        return [ensure_int_values(item, fields) for item in data]
    return data