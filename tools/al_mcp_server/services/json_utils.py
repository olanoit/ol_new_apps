import base64
import datetime
import decimal

from markupsafe import Markup


def odoo_json_default(obj):
    """Serializador JSON para los tipos del ORM de Odoo que no son nativos de JSON.

    Admite: recordsets, datetime/date, Decimal, bytes, Markup, set/frozenset.
    Para cualquier otro tipo recurre a str(), de modo que dumps() nunca falla.
    """
    if hasattr(obj, "_name") and hasattr(obj, "ids"):
        if len(obj) == 1:
            return {"id": obj.id, "display_name": str(obj.display_name)}
        return [{"id": r.id, "display_name": str(r.display_name)} for r in obj]
    if isinstance(obj, datetime.datetime):
        return obj.isoformat(sep="T", timespec="seconds")
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode()
    if isinstance(obj, Markup):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    return str(obj)
