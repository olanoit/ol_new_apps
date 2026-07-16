# -*- coding: utf-8 -*-
"""Scraping del portal e-consultaruc.sunat.gob.pe usando BeautifulSoup.

Reemplaza la implementación original basada en búsqueda de strings
``str.find(...)`` (~700 líneas) por consultas BS4 declarativas.

Hay dos endpoints distintos en SUNAT:

  * ``cl-ti-itmrconsruc`` — consulta individual con número aleatorio
    (``numRnd``). Devuelve HTML con detalle del contribuyente y
    permite consultar también representantes legales y locales anexos.
  * ``cl-ti-itmrconsmulruc`` — consulta multi-RUC con captcha. Genera
    un ZIP con un CSV pipe-separado. Más rápido pero sin detalle de
    representantes ni locales.

Ambos se exponen como funciones puras que devuelven ``RucResult``.
"""
import io
import logging
from io import BytesIO
from zipfile import ZipFile

from bs4 import BeautifulSoup

from . import http

_logger = logging.getLogger(__name__)


SUNAT_HOST = 'https://e-consultaruc.sunat.gob.pe'
SUNAT_INDIVIDUAL = SUNAT_HOST + '/cl-ti-itmrconsruc/jcrS00Alias'
SUNAT_MULTI = SUNAT_HOST + '/cl-ti-itmrconsmulruc/jrmS00Alias'

# Número de intentos para superar el 401 inicial del portal.
SUNAT_MAX_RETRIES = 6


# ---------------------------------------------------------------------- #
# Consulta individual (con representantes legales y locales anexos)      #
# ---------------------------------------------------------------------- #

def fetch_ruc(ruc, *, with_legal_reps=False, with_annex=False):
    """Consulta individual al portal SUNAT.

    Devuelve un ``services.providers.RucResult`` poblado con los
    datos del contribuyente. Si ``with_legal_reps`` o ``with_annex``
    están activos, hace consultas adicionales y los anexa al resultado.
    """
    # Import diferido para evitar ciclo de imports.
    from .results import RucResult

    import requests
    session = requests.Session()

    # 1) GET inicial para obtener cookies y numRnd.
    r0 = http.get(
        SUNAT_INDIVIDUAL, service='SUNAT', session=session, retries=1,
    )
    if r0.status_code != 200:
        raise http.HttpError(
            'SUNAT no respondió al GET inicial.',
            status_code=r0.status_code, body=r0.text, service='SUNAT',
        )

    # 2) POST a consPorTipdoc con un DNI conocido para forzar el
    #    portal a generar el numRnd asociado a esta sesión.
    seed_dni = '12345678'
    seed_params = {
        'accion': 'consPorTipdoc',
        'razSoc': '', 'nroRuc': '', 'nrodoc': seed_dni,
        'contexto': 'ti-it', 'modo': '1',
        'rbtnTipo': '2', 'tipdoc': '1', 'search2': seed_dni,
    }
    r1 = http.post(
        SUNAT_INDIVIDUAL, service='SUNAT', session=session,
        data=seed_params, retries=SUNAT_MAX_RETRIES,
    )
    num_rnd = _extract_num_rnd(r1.text)
    if not num_rnd:
        raise http.HttpError(
            'No se pudo extraer numRnd del portal SUNAT.',
            status_code=r1.status_code, body=r1.text, service='SUNAT',
        )

    # 3) Consulta del RUC propiamente dicho.
    base = _query_ruc(session, ruc, num_rnd)
    result = _parse_ruc_html(base, ruc)

    if with_legal_reps:
        result.legal_representatives = _query_legal_reps(
            session, ruc, result.name, num_rnd,
        )
    if with_annex:
        result.annexed_locals = _query_annex(
            session, ruc, result.name, num_rnd,
        )
    return result


def _query_ruc(session, ruc, num_rnd):
    url = '%s?accion=consPorRuc&nroRuc=%s&contexto=ti-it&modo=1&numRnd=%s' % (
        SUNAT_INDIVIDUAL, ruc, num_rnd,
    )
    r = http.post(url, service='SUNAT', session=session, retries=SUNAT_MAX_RETRIES)
    if r.status_code != 200:
        raise http.HttpError(
            'SUNAT rechazó la consulta de RUC %s.' % ruc,
            status_code=r.status_code, body=r.text, service='SUNAT',
        )
    return r.text


def _query_legal_reps(session, ruc, name, num_rnd):
    url = ('%s?accion=getRepLeg&desRuc=%s&nroRuc=%s'
           '&contexto=ti-it&modo=1&numRnd=%s') % (
        SUNAT_INDIVIDUAL, name or '', ruc, num_rnd,
    )
    try:
        r = http.post(
            url, service='SUNAT', session=session, retries=SUNAT_MAX_RETRIES,
        )
        return _parse_legal_reps(r.text)
    except http.HttpError as exc:
        _logger.warning('Representantes legales no disponibles: %s', exc)
        return []


def _query_annex(session, ruc, name, num_rnd):
    url = ('%s?accion=getLocAnex&desRuc=%s&nroRuc=%s'
           '&contexto=ti-it&modo=1&numRnd=%s') % (
        SUNAT_INDIVIDUAL, name or '', ruc, num_rnd,
    )
    try:
        r = http.post(
            url, service='SUNAT', session=session, retries=SUNAT_MAX_RETRIES,
        )
        return _parse_annex(r.text)
    except http.HttpError as exc:
        _logger.warning('Locales anexos no disponibles: %s', exc)
        return []


def _extract_num_rnd(html):
    """Extrae el ``numRnd`` del HTML inicial de SUNAT."""
    soup = BeautifulSoup(html, 'html.parser')
    inp = soup.find('input', attrs={'name': 'numRnd'})
    return inp.get('value', '').strip() if inp else ''


def _parse_ruc_html(html, ruc):
    """Convierte el HTML del detalle de RUC en un ``RucResult``."""
    from .results import RucResult

    soup = BeautifulSoup(html, 'html.parser')

    # SUNAT señaliza error con un <p class="error">.
    err = soup.find('p', class_='error')
    if err and err.get_text(strip=True):
        raise http.HttpError(
            'SUNAT: %s' % err.get_text(strip=True),
            status_code=200, body=html, service='SUNAT',
        )

    # Cabecera "20XXXXXXXXX - RAZON SOCIAL"
    headers = soup.select('div.list-group h4.list-group-item-heading')
    items = soup.select('div.list-group p.list-group-item-text')
    if not headers:
        raise http.HttpError(
            'SUNAT no devolvió detalle para %s.' % ruc,
            status_code=200, body=html, service='SUNAT',
        )

    # La cabecera "20XXXXXXXXX - RAZON SOCIAL" es uno de los h4, pero su
    # posición NO es fija (SUNAT intercala etiquetas como "Número de RUC:").
    # Se localiza por su patrón: "<dígitos> - <razón social>". Los <p> texto
    # vienen en orden:
    #   0 Tipo Contribuyente   1 Nombre Comercial   2 Fecha Inscripción
    #   3 Fecha Inicio Act.     4 Estado             5 Condición
    #   6 Domicilio Fiscal      ...
    header_text = ''
    for h in headers:
        txt = h.get_text(strip=True)
        if ' - ' not in txt:
            continue
        left = txt.split(' - ', 1)[0].strip()
        if left == ruc:
            header_text = txt
            break
        if not header_text and left.isdigit():
            header_text = txt
    if ' - ' in header_text:
        ruc_field, name_field = header_text.split(' - ', 1)
    else:
        ruc_field, name_field = ruc, header_text or ruc

    def _at(idx):
        return items[idx].get_text(strip=True) if idx < len(items) else ''

    state = _at(4)
    condition = _at(5)
    address = _at(6)
    commercial_name = _at(1).strip('-').strip()

    # Si el estado es "BAJA DE OFICIO" SUNAT inserta una línea extra
    # arriba; se detecta porque hay 15+ items en lugar de 14.
    if len(items) > 14 and 'BAJA' in _at(0).upper():
        state = _at(5)
        condition = _at(6)
        address = _at(7)
        commercial_name = _at(2).strip('-').strip()

    district, province, department = _split_address(address)

    return RucResult(
        ruc=ruc_field.strip(),
        name=name_field.strip(),
        commercial_name=commercial_name,
        state=state,
        condition=condition,
        address=_address_street(address),
        district=district,
        province=province,
        department=department,
    )


def _split_address(address):
    """Devuelve (distrito, provincia, departamento) desde la cadena de
    Domicilio Fiscal de SUNAT.

    Ej.: "JR. LIBERTAD 123 - LIMA - LIMA - LIMA"
         → ('LIMA', 'LIMA', 'LIMA')
    """
    if not address or address.strip() == '-':
        return '', '', ''
    parts = [p.strip() for p in address.split('-')]
    if len(parts) < 3:
        return '', '', ''
    return (
        parts[-1].title(),
        parts[-2].title(),
        parts[-3].title(),
    )


def _address_street(address):
    """Extrae la calle del Domicilio Fiscal SUNAT.

    SUNAT mete (referencia) entre paréntesis y luego el guión separa
    distrito/provincia/departamento. Tomamos lo de antes del primer
    paréntesis o del primer guión.
    """
    if not address:
        return ''
    if '(' in address:
        return address.split('(', 1)[0].strip()
    parts = address.split('-')
    if len(parts) > 3:
        return '-'.join(parts[:-3]).strip()
    return parts[0].strip()


def _parse_legal_reps(html):
    """Devuelve lista de dicts con representantes legales."""
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select('table tr')
    reps = []
    for tr in rows:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 4:
            continue
        # Cabecera: Documento | N° Doc | Nombre | Cargo | Fecha Desde
        if cells[0].upper() in ('DOCUMENTO', 'DOC', 'TIPO'):
            continue
        reps.append({
            'doc_type': cells[0],
            'doc_number': cells[1],
            'name': cells[2],
            'position': cells[3] if len(cells) > 3 else '',
            'from_date': cells[4] if len(cells) > 4 else '',
        })
    return reps


def _parse_annex(html):
    """Devuelve lista de dicts con locales anexos."""
    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select('table.table tr')
    locals_ = []
    for tr in rows:
        cells = [td.get_text(strip=True) for td in tr.find_all('td')]
        if len(cells) < 3:
            continue
        if cells[0].upper() in ('CÓDIGO', 'CODIGO', 'COD'):
            continue
        locals_.append({
            'code': cells[0],
            'type': cells[1],
            'address': cells[2],
            'activity': cells[3] if len(cells) > 3 else '',
        })
    return locals_


# ---------------------------------------------------------------------- #
# Consulta multi-RUC (ZIP CSV pipe-separado)                              #
# ---------------------------------------------------------------------- #

def fetch_ruc_multi(ruc):
    """Consulta el portal multi-RUC y devuelve ``RucResult``."""
    from .results import RucResult

    import requests
    session = requests.Session()

    captcha = http.post(
        '%s/captcha' % SUNAT_MULTI.rsplit('/', 1)[0],
        service='SUNAT-multi', session=session,
        data={'accion': 'random'}, retries=2,
    )
    if captcha.status_code != 200:
        raise http.HttpError(
            'SUNAT Multi-RUC: no se pudo obtener el captcha.',
            status_code=captcha.status_code, body=captcha.text,
            service='SUNAT-multi',
        )

    r = http.post(
        SUNAT_MULTI, service='SUNAT-multi', session=session,
        data={
            'accion': 'consManual',
            'selRuc': ruc,
            'numRnd': captcha.text,
        },
        retries=SUNAT_MAX_RETRIES,
    )
    if r.status_code != 200:
        raise http.HttpError(
            'SUNAT Multi-RUC rechazó la consulta de %s.' % ruc,
            status_code=r.status_code, body=r.text, service='SUNAT-multi',
        )

    soup = BeautifulSoup(r.content, 'html.parser')
    link = soup.find('a', href=True)
    if not link:
        raise http.HttpError(
            'SUNAT Multi-RUC no devolvió enlace al ZIP para %s.' % ruc,
            status_code=200, body=r.text, service='SUNAT-multi',
        )
    zip_url = link['href']
    zip_name = link.get_text(strip=True)
    txt_name = zip_name.replace('.zip', '.txt')

    zip_resp = http.get(zip_url, service='SUNAT-multi', retries=1)
    with ZipFile(BytesIO(zip_resp.content)) as zf:
        with zf.open(txt_name) as fh:
            lines = [ln.decode('utf-8') for ln in fh.readlines()]

    if len(lines) < 2:
        raise http.HttpError(
            'SUNAT Multi-RUC: archivo vacío para %s.' % ruc,
            status_code=200, body=zip_resp.text[:300], service='SUNAT-multi',
        )

    headers = [_normalize_header(c) for c in lines[0].split('|')]
    values = [v.strip() for v in lines[1].split('|')]
    record = dict(zip(headers, values))

    return RucResult(
        ruc=record.get('numeroruc', ruc),
        name=record.get('nombre__razonsocial', ''),
        commercial_name=record.get('nombre_comercial', ''),
        state=record.get('estado_del_contribuyente', ''),
        condition=record.get('condicion_del_contribuyente', ''),
        address=record.get('direccion', ''),
        ubigeo=record.get('ubigeo', ''),
        district=record.get('distrito', '').title(),
        province=record.get('provincia', '').title(),
        department=record.get('departamento', '').title(),
    )


def _normalize_header(header):
    """Convierte cabeceras "Estado del Contribuyente" en
    ``estado_del_contribuyente`` (snake_case ASCII).
    """
    text = (header or '').strip().lower()
    text = text.replace('ó', 'o').replace('á', 'a').replace('é', 'e')
    text = text.replace('í', 'i').replace('ú', 'u').replace('ñ', 'n')
    text = text.replace('-', '').replace(' ', '_')
    return text
