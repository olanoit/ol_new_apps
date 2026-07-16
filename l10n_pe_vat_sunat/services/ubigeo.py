# -*- coding: utf-8 -*-
"""Resolución de ubigeo / distrito / ciudad / departamento.

Este módulo centraliza la lógica que antes estaba duplicada en cinco
sitios distintos del ``res_partner.py`` original. Funciona como
biblioteca pura: recibe ``env`` y devuelve un dict de valores listos
para ``record.write(...)``.

Estrategias soportadas:

  1. **Por código de ubigeo** (6 dígitos, p. ej. ``150101``) — la más
     fiable cuando la API la devuelve.
  2. **Por nombres** (distrito + provincia + departamento) con
     normalización ``=ilike`` y matching tolerante.
"""
import logging
import unicodedata

_logger = logging.getLogger(__name__)


# Conjuntos de modelos comunes; centralizar evita typos repetidos.
M_DISTRICT = 'l10n_pe.res.city.district'
M_CITY = 'res.city'
M_STATE = 'res.country.state'
M_COUNTRY = 'res.country'


def _norm(text):
    """Normaliza texto para comparar (sin acentos, MAYÚSCULAS, sin
    espacios redundantes).
    """
    if not text:
        return ''
    nfd = unicodedata.normalize('NFD', str(text))
    ascii_ = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return ' '.join(ascii_.upper().split())


def resolve_by_code(env, ubigeo_code):
    """Devuelve un dict con district/city/state/country a partir de un
    código ubigeo de 6 dígitos.

    Ejemplo: ``"150101"`` → Lima/Lima/Lima/Perú.

    Si el código no se encuentra, devuelve ``{}`` (el llamador no debe
    sobrescribir los valores actuales del partner).
    """
    if not ubigeo_code:
        return {}
    code = str(ubigeo_code).strip()
    if not code.isdigit() or len(code) != 6:
        return {}
    Distrito = env[M_DISTRICT].sudo()
    district = Distrito.search([('code', '=', code)], limit=1)
    if not district:
        return {}
    return _district_to_vals(district)


def resolve_by_names(env, *, district='', city='', state='', country_code='PE'):
    """Devuelve un dict con district/city/state/country a partir de
    nombres humanos.

    Tolerante a tildes, mayúsculas/minúsculas y espacios. Maneja el
    caso especial del Callao (provincia constitucional).

    Si no encuentra ningún distrito, intenta resolver por ciudad sola,
    luego por estado solo. Devuelve ``{}`` si nada coincide.
    """
    if not any((district, city, state)):
        return {}

    # Caso especial: Callao es provincia constitucional, no
    # departamento. El portal SUNAT lo escribe "PROV. CONST. DEL CALLAO".
    norm_city = _norm(city)
    if 'CALLAO' in norm_city and 'CONST' in norm_city:
        district = district or 'Callao'
        city = 'Callao'
        state = 'Callao'

    country = env[M_COUNTRY].sudo().search(
        [('code', '=', country_code)], limit=1,
    )
    if not country:
        return {}

    Distrito = env[M_DISTRICT].sudo()
    City = env[M_CITY].sudo()
    State = env[M_STATE].sudo()

    # 1) Match exacto distrito + ciudad
    if district and city:
        cities = City.search([
            ('name', '=ilike', city.strip()),
            ('country_id', '=', country.id),
        ])
        if cities:
            d = Distrito.search([
                ('name', '=ilike', district.strip()),
                ('city_id', 'in', cities.ids),
            ], limit=1)
            if d:
                return _district_to_vals(d)

    # 2) Distrito solo (la mayoría de distritos en PE son únicos)
    if district:
        d = Distrito.search([('name', '=ilike', district.strip())], limit=1)
        if d:
            return _district_to_vals(d)

    # 3) Ciudad/Provincia
    if city:
        c = City.search([
            ('name', '=ilike', city.strip()),
            ('country_id', '=', country.id),
        ], limit=1)
        if c:
            return _city_to_vals(c, country)

    # 4) Departamento/Estado
    if state:
        s = State.search([
            ('name', '=ilike', state.strip()),
            ('country_id', '=', country.id),
        ], limit=1)
        if s:
            return {'state_id': s.id, 'country_id': country.id}

    return {}


def resolve(env, *, ubigeo_code='', district='', city='', state='',
            country_code='PE'):
    """Helper: prueba primero por código, luego por nombres."""
    if ubigeo_code:
        vals = resolve_by_code(env, ubigeo_code)
        if vals:
            return vals
    return resolve_by_names(
        env, district=district, city=city, state=state,
        country_code=country_code,
    )


def _district_to_vals(district):
    """Convierte un ``l10n_pe.res.city.district`` en dict de write()."""
    city = district.city_id
    state = city.state_id if city else False
    country = state.country_id if state else False
    return {
        'l10n_pe_district': district.id,
        'city_id': city.id if city else False,
        'state_id': state.id if state else False,
        'country_id': country.id if country else False,
        'zip': district.code,
    }


def _city_to_vals(city, country):
    state = city.state_id
    return {
        'city_id': city.id,
        'state_id': state.id if state else False,
        'country_id': country.id,
    }
