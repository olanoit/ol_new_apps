# -*- coding: utf-8 -*-
"""Motor de extracción/mapeo genérico (config-driven).

Funciones puras, sin ORM, para:

  * navegar una respuesta (dict/list) por una **ruta con puntos**
    (``data.direccion`` o ``ubigeo.2`` para índices de lista);
  * construir strings por **plantilla** con marcadores ``{ruta}``
    (``{nombres} {apellido_paterno}``);
  * aplicar **transformaciones** simples al valor extraído.

Todo lo que dependa del ORM (resolución de ubigeo, escritura en el
partner) vive en el modelo ``l10n_pe.api.connection``; aquí solo hay
lógica pura y testeable de forma aislada.
"""
import re

_PLACEHOLDER_RE = re.compile(r'\{([^{}]+)\}')


def get_path(data, path):
    """Navega ``data`` por ``path`` (con puntos). Soporta índices de lista.

    Ejemplos::

        get_path({'a': {'b': 1}}, 'a.b')        -> 1
        get_path({'u': ['x', 'y', 'z']}, 'u.2') -> 'z'
        get_path({'a': 1}, 'a.b')               -> None  (no existe)

    Devuelve ``None`` si cualquier tramo de la ruta no existe.
    """
    if not path:
        return None
    current = data
    for part in path.split('.'):
        part = part.strip()
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def render_source(data, source):
    """Extrae el valor de ``source`` desde ``data``.

    - Si ``source`` contiene marcadores ``{ruta}``, construye un string
      reemplazando cada marcador por su valor (concatenación).
    - Si no, trata ``source`` como una ruta simple y devuelve el valor
      crudo (que puede no ser string: bool, número, lista...).
    """
    if source is None:
        return None
    if '{' in source and '}' in source:
        def _sub(match):
            value = get_path(data, match.group(1).strip())
            return '' if value is None else str(value)
        return _PLACEHOLDER_RE.sub(_sub, source)
    return get_path(data, source)


def apply_transform(value, transform):
    """Aplica una transformación textual simple al valor."""
    if value is None:
        return None
    if transform in (None, '', 'none'):
        return value
    text = value if isinstance(value, str) else str(value)
    if transform == 'upper':
        return text.upper()
    if transform == 'lower':
        return text.lower()
    if transform == 'title':
        return text.title()
    if transform == 'strip':
        return text.strip()
    if transform == 'capitalize':
        return text.capitalize()
    return value


def truthy(value):
    """Interpreta un valor de 'éxito' de una API (bool/str/int)."""
    if isinstance(value, str):
        return value.strip().lower() not in ('', 'false', '0', 'no', 'null')
    return bool(value)
