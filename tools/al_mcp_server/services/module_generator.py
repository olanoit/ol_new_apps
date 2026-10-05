"""
Generador de módulos MCP — build_zip + validate_spec
====================================================

Este servicio genera módulos Odoo 18 instalables a partir de una especificación JSON.
Es el motor de la herramienta MCP ``odoo_generate_module``.

Formato de la especificación
----------------------------
::

    {
      "technical_name": "my_module",
      "name": "My Module",
      "summary": "Descripción breve",
      "description": "Descripción larga",
      "category": "Productivity",
      "version": "17.0.1.0.0",
      "depends": ["base", "mail"],
      "license": "LGPL-3",
      "models": [
        {
          "name": "my.module.task",
          "description": "Una tarea de mi módulo",
          "inherit": null,
          "fields": [
            {"name": "name", "type": "char", "string": "Name", "required": true},
            {"name": "description", "type": "text", "string": "Description"},
            {"name": "user_id", "type": "many2one", "comodel": "res.users", "string": "Assigned To"},
            {"name": "state", "type": "selection",
             "selection": [["draft","Draft"],["done","Done"]], "default": "draft"},
            {"name": "date_due", "type": "date", "string": "Due Date"}
          ],
          "inherits_mail_thread": true,
          "rec_name": "name"
        }
      ],
      "menus": [
        {
          "name": "My Module",
          "sequence": 10,
          "children": [
            {"name": "Tasks", "action_model": "my.module.task"}
          ]
        }
      ],
      "security": {
        "groups": [
          {"name": "My Module User", "implied_by": "base.group_user"}
        ],
        "access_rights": [
          {"model": "my.module.task", "group": "base.group_user",
           "read": 1, "write": 1, "create": 1, "unlink": 0}
        ]
      },
      "views": {
        "auto_generate": true
      },
      "demo_data": []
    }

Tipos de campo permitidos
-------------------------
char, text, html, integer, float, monetary, boolean, date, datetime,
selection, many2one, one2many, many2many, binary

Notas
-----
- Los archivos Python generados se analizan con ``ast`` para detectar errores de sintaxis.
- El ZIP usa compresión deflate.
- ``validate_spec`` devuelve una lista de mensajes de error legibles.
  Una lista vacía significa que la especificación es válida.
"""

import ast
import csv
import io
import keyword
import logging
import re
import zipfile
from xml.sax.saxutils import escape as _sax_escape

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_VALID_LICENSES = {"OPL-1", "LGPL-3", "AGPL-3"}

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+\.\d+$")

_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_MODEL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*)+$")

# XML-ID completo "modulo.nombre" (grupos implicados y de acceso).
_XMLID_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def _x(value) -> str:
    """Escapa un valor para texto o atributo XML (entre comillas dobles).

    Todo texto del spec que acaba en los XML generados pasa por aquí: el XML
    se carga como superusuario al instalar, así que una etiqueta inyectada
    (<function>, <record>...) equivaldría a ejecutar código arbitrario.
    """
    return _sax_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def _int(value, default: int = 10) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_model_name(name):
    """Fuerza un nombre de modelo a la convención de Odoo (minúsculas con puntos).

    Ejemplos:
        'office.asset'  -> 'office.asset' (ya es válido)
        'OfficeAsset'   -> 'office.asset' (CamelCase)
        'officeAsset'   -> 'office.asset' (lowerCamelCase)
        'office_asset'  -> 'office.asset' (snake_case, sin punto)

    Los nombres que no se pueden separar sin ambigüedad (p. ej. 'officeasset')
    se devuelven sin cambios y validate_spec los rechaza.
    """
    if not isinstance(name, str) or not name:
        return name
    if _MODEL_NAME_RE.match(name):
        return name
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    if "." not in snake and "_" in snake:
        snake = snake.replace("_", ".")
    return snake

_RESERVED_ODOO_NAMES = frozenset({
    "base", "web", "mail", "bus", "digest", "portal", "auth_signup",
    "sale", "purchase", "account", "stock", "mrp", "project", "hr",
    "crm", "website",
})

_RESERVED_FIELD_NAMES = frozenset({
    "id", "create_date", "write_date", "create_uid", "write_uid",
    "__last_update", "display_name",
})

_FIELD_TYPE_ALLOWLIST = frozenset({
    "char", "text", "html", "integer", "float", "monetary", "boolean",
    "date", "datetime", "selection", "many2one", "one2many", "many2many",
    "binary",
})

_RELATIONAL_TYPES = frozenset({"many2one", "one2many", "many2many"})


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def validate_spec(spec: dict) -> list[str]:
    """Valida el diccionario de especificación de un módulo.

    Devuelve una lista de mensajes de error legibles. Una lista vacía significa
    que la especificación es válida y ``build_zip`` puede continuar.
    """
    errors = []

    # ---- campos obligatorios de primer nivel ------------------------------
    tech = spec.get("technical_name", "")
    if not tech:
        errors.append("technical_name es obligatorio.")
    else:
        if not _SNAKE_RE.match(tech):
            errors.append(
                f"technical_name {tech!r} debe estar en snake_case "
                "(letras minúsculas, dígitos y guiones bajos; debe empezar con una letra)."
            )
        if keyword.iskeyword(tech):
            errors.append(f"technical_name {tech!r} es una palabra reservada de Python.")
        if tech in _RESERVED_ODOO_NAMES:
            errors.append(
                f"technical_name {tech!r} entra en conflicto con el nombre de un módulo integrado de Odoo."
            )

    if not spec.get("name"):
        errors.append("name es obligatorio.")

    version = spec.get("version", "")
    if version and not _VERSION_RE.match(version):
        errors.append(
            f"version {version!r} debe coincidir con el patrón N.N.N.N.N "
            "(p. ej. 17.0.1.0.0)."
        )

    license_val = spec.get("license", "LGPL-3")
    if license_val not in _VALID_LICENSES:
        errors.append(
            f"license {license_val!r} no está en la lista permitida: "
            + ", ".join(sorted(_VALID_LICENSES))
        )

    depends = spec.get("depends", [])
    if depends is not None:
        if not isinstance(depends, list):
            errors.append("depends debe ser una lista de cadenas.")
        else:
            for dep in depends:
                if not isinstance(dep, str) or not dep.strip():
                    errors.append(
                        f"Cada entrada de depends debe ser una cadena no vacía; se obtuvo {dep!r}."
                    )

    # ---- modelos ------------------------------------------------------------
    models_spec = spec.get("models") or []
    if not isinstance(models_spec, list):
        errors.append("models debe ser una lista.")
    else:
        seen_model_names: set[str] = set()
        for i, model in enumerate(models_spec):
            prefix = f"models[{i}]"
            if isinstance(model, dict) and "name" in model:
                model["name"] = _normalize_model_name(model["name"])
            if isinstance(model, dict) and "inherit" in model:
                model["inherit"] = _normalize_model_name(model["inherit"])
            mname = model.get("name", "") if isinstance(model, dict) else ""
            if not mname:
                errors.append(f"{prefix}: name es obligatorio.")
            elif not _MODEL_NAME_RE.match(mname):
                errors.append(
                    f"{prefix}: el nombre de modelo {mname!r} debe estar en minúsculas con puntos "
                    "(p. ej. my.module.task)."
                )
            else:
                if mname in seen_model_names:
                    errors.append(
                        f"{prefix}: nombre de modelo duplicado {mname!r}."
                    )
                seen_model_names.add(mname)

            fields = model.get("fields") or []
            if not isinstance(fields, list):
                errors.append(f"{prefix}: fields debe ser una lista.")
                continue

            seen_field_names: set[str] = set()
            for j, fld in enumerate(fields):
                fprefix = f"{prefix}.fields[{j}]"
                if isinstance(fld, dict) and "comodel" in fld:
                    fld["comodel"] = _normalize_model_name(fld["comodel"])
                fname = fld.get("name", "")
                if not fname:
                    errors.append(f"{fprefix}: name es obligatorio.")
                    continue
                if not _SNAKE_RE.match(fname):
                    errors.append(
                        f"{fprefix}: el nombre de campo {fname!r} debe estar en snake_case."
                    )
                if keyword.iskeyword(fname):
                    errors.append(
                        f"{fprefix}: el nombre de campo {fname!r} es una palabra reservada de Python."
                    )
                if fname in _RESERVED_FIELD_NAMES:
                    errors.append(
                        f"{fprefix}: el nombre de campo {fname!r} es un nombre de campo reservado de Odoo."
                    )
                if fname in seen_field_names:
                    errors.append(
                        f"{fprefix}: nombre de campo duplicado {fname!r} en el modelo {mname!r}."
                    )
                seen_field_names.add(fname)

                ftype = fld.get("type", "")
                if not ftype:
                    errors.append(f"{fprefix}: type es obligatorio.")
                elif ftype not in _FIELD_TYPE_ALLOWLIST:
                    errors.append(
                        f"{fprefix}: el tipo de campo {ftype!r} no está en la lista permitida: "
                        + ", ".join(sorted(_FIELD_TYPE_ALLOWLIST))
                    )
                elif ftype in _RELATIONAL_TYPES and not fld.get("comodel"):
                    errors.append(
                        f"{fprefix}: el campo relacional {fname!r} de tipo {ftype!r} "
                        "requiere 'comodel'."
                    )
                elif ftype == "one2many" and not fld.get("inverse_field"):
                    errors.append(
                        f"{fprefix}: el campo one2many {fname!r} requiere 'inverse_field'."
                    )
                elif ftype == "selection" and not fld.get("selection"):
                    errors.append(
                        f"{fprefix}: el campo selection {fname!r} requiere la lista 'selection'."
                    )

    # ---- seguridad: acepta access_rights/groups de primer nivel (convención de
    # Claude) y los fusiona en spec.security.* para que los generadores vean un solo esquema.
    top_ars = spec.get("access_rights")
    top_groups = spec.get("groups")
    if isinstance(top_ars, list) or isinstance(top_groups, list):
        sec = spec.get("security")
        if not isinstance(sec, dict):
            sec = {}
            spec["security"] = sec
        if isinstance(top_ars, list):
            existing = sec.get("access_rights") if isinstance(sec.get("access_rights"), list) else []
            sec["access_rights"] = existing + top_ars
        if isinstance(top_groups, list):
            existing = sec.get("groups") if isinstance(sec.get("groups"), list) else []
            sec["groups"] = existing + top_groups

    # ---- seguridad: normaliza referencias a modelos (sin validar, solo ajusta)
    sec = spec.get("security")
    if isinstance(sec, dict):
        ars = sec.get("access_rights")
        if isinstance(ars, list):
            for ar in ars:
                if isinstance(ar, dict) and "model" in ar:
                    ar["model"] = _normalize_model_name(ar["model"])

    # ---- seguridad: valida las referencias que acaban en el XML / CSV -------
    sec = spec.get("security")
    if isinstance(sec, dict):
        for i, grp in enumerate(sec.get("groups") or []):
            if not isinstance(grp, dict) or not grp.get("name"):
                errors.append(f"security.groups[{i}]: name es obligatorio.")
                continue
            implied = grp.get("implied_by", "")
            if implied and not (isinstance(implied, str) and _XMLID_RE.match(implied)):
                errors.append(
                    f"security.groups[{i}]: implied_by {implied!r} debe ser un XML-ID 'modulo.nombre'."
                )
        for i, ar in enumerate(sec.get("access_rights") or []):
            if not isinstance(ar, dict):
                errors.append(f"security.access_rights[{i}]: debe ser un objeto.")
                continue
            if not _MODEL_NAME_RE.match(str(ar.get("model", ""))):
                errors.append(f"security.access_rights[{i}]: model no válido.")
            group = ar.get("group", "base.group_user")
            if not (isinstance(group, str) and _XMLID_RE.match(group)):
                errors.append(
                    f"security.access_rights[{i}]: group {group!r} debe ser un XML-ID 'modulo.nombre'."
                )
            for key in ("perm_read", "read", "perm_write", "write",
                        "perm_create", "create", "perm_unlink", "unlink"):
                if key in ar and str(ar[key]) not in ("0", "1", "True", "False"):
                    errors.append(f"security.access_rights[{i}]: {key} debe ser 0 o 1.")

    # ---- menus --------------------------------------------------------------
    menus = spec.get("menus") or []
    if not isinstance(menus, list):
        errors.append("menus debe ser una lista.")
    else:
        for i, menu in enumerate(menus):
            if not menu.get("name"):
                errors.append(f"menus[{i}]: name es obligatorio.")

    return errors


def build_zip(spec: dict) -> tuple[bytes, list[str]]:
    """Genera el ZIP de un módulo Odoo 18 instalable a partir de *spec*.

    Devuelve ``(zip_bytes, warnings)``, donde *zip_bytes* es el contenido
    del ZIP y *warnings* es una lista de avisos no bloqueantes.

    Lanza ``ValueError`` si la especificación no supera la validación o si
    un archivo Python generado contiene un error de sintaxis.
    """
    errors = validate_spec(spec)
    if errors:
        raise ValueError(
            "La validación de la especificación falló:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    warnings: list[str] = []
    tech = spec["technical_name"]
    models_spec = spec.get("models") or []
    security = spec.get("security") or {}
    if isinstance(security, list):
        security = {}
    views_cfg = spec.get("views") or {}
    if isinstance(views_cfg, list):
        views_cfg = {}
    auto_generate_views = views_cfg.get("auto_generate", True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        # __init__.py (raíz)
        root_init = _gen_init_root(models_spec)
        _write_py(zf, f"{tech}/__init__.py", root_init, tech)

        # __manifest__.py
        manifest_src = _gen_manifest(spec)
        _write_py(zf, f"{tech}/__manifest__.py", manifest_src, tech)

        # models/__init__.py
        if models_spec:
            model_init = _gen_init_models(models_spec)
            _write_py(zf, f"{tech}/models/__init__.py", model_init, tech)

            for model in models_spec:
                model_src = _gen_model(model)
                fname = _model_name_to_file(model["name"])
                _write_py(zf, f"{tech}/models/{fname}.py", model_src, tech)

        # security/ir.model.access.csv
        access_csv = _gen_access_csv(spec)
        zf.writestr(f"{tech}/security/ir.model.access.csv", access_csv)

        # security/security.xml (grupos)
        groups = security.get("groups") or []
        if groups:
            security_xml = _gen_security_groups(spec, tech)
            zf.writestr(f"{tech}/security/security.xml", security_xml)

        # views/<model>_views.xml
        if auto_generate_views and models_spec:
            for model in models_spec:
                view_xml = _gen_view(model, spec)
                fname = _model_name_to_file(model["name"])
                zf.writestr(f"{tech}/views/{fname}_views.xml", view_xml)

        # data/demo.xml
        demo_data = spec.get("demo_data") or []
        if demo_data:
            demo_xml = _gen_demo_data(spec)
            zf.writestr(f"{tech}/data/demo.xml", demo_xml)
        else:
            warnings.append(
                "No se proporcionó demo_data. Los datos de demostración son opcionales pero recomendados para pruebas."
            )

    return buf.getvalue(), warnings


# ---------------------------------------------------------------------------
# Generadores internos
# ---------------------------------------------------------------------------


def _gen_manifest(spec: dict) -> str:
    tech = spec["technical_name"]
    name = spec.get("name", tech)
    summary = spec.get("summary", "")
    description = spec.get("description", "")
    category = spec.get("category", "Productivity")
    version = spec.get("version", "17.0.1.0.0")
    license_val = spec.get("license", "LGPL-3")
    author = spec.get("author", "MCP Generator")
    depends = spec.get("depends") or ["base"]
    if isinstance(depends, list):
        depends_repr = repr(depends)
    else:
        depends_repr = repr([d.strip() for d in depends.split(",") if d.strip()])

    models_spec = spec.get("models") or []
    security = spec.get("security") or {}
    if isinstance(security, list):
        security = {}
    groups = security.get("groups") or []
    views_cfg = spec.get("views") or {}
    if isinstance(views_cfg, list):
        views_cfg = {}
    auto_generate_views = views_cfg.get("auto_generate", True)
    demo_data = spec.get("demo_data") or []

    data_files: list[str] = ["'security/ir.model.access.csv'"]
    if groups:
        data_files.append("'security/security.xml'")
    if auto_generate_views and models_spec:
        for model in models_spec:
            fname = _model_name_to_file(model["name"])
            data_files.append(f"'views/{fname}_views.xml'")
    if demo_data:
        data_files.append("'data/demo.xml'")

    data_lines = ",\n        ".join(data_files)

    lines = [
        "# -*- coding: utf-8 -*-",
        "{",
        f"    'name': {name!r},",
        f"    'version': {version!r},",
        f"    'summary': {summary!r},",
        f"    'description': {description!r},",
        f"    'category': {category!r},",
        f"    'author': {author!r},",
        f"    'license': {license_val!r},",
        f"    'depends': {depends_repr},",
        "    'data': [",
        f"        {data_lines},",
        "    ],",
        "    'installable': True,",
        "    'application': False,",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _gen_init_root(models_spec: list) -> str:
    if models_spec:
        return "from . import models\n"
    return "# Nada que importar\n"


def _gen_init_models(models_spec: list) -> str:
    lines = []
    for model in models_spec:
        fname = _model_name_to_file(model["name"])
        lines.append(f"from . import {fname}")
    return "\n".join(lines) + "\n"


def _gen_model(model_spec: dict) -> str:
    model_name = model_spec["name"]
    description = model_spec.get("description", model_name)
    fields = model_spec.get("fields") or []
    inherits_mail = model_spec.get("inherits_mail_thread", False)
    rec_name = model_spec.get("rec_name")
    inherit = model_spec.get("inherit")

    class_name = _model_name_to_class(model_name)

    field_lines: list[str] = []
    for fld in fields:
        field_lines.extend(_gen_field_lines(fld))

    # Determina el patrón de herencia:
    #   - inherit es una CADENA y != model_name  -> extiende un modelo existente (sin _name)
    #   - inherit es una LISTA                   -> patrón mixin (modelo NUEVO + _name + _inherit)
    #   - inherit es None o vacío                -> modelo nuevo simple
    is_extending = isinstance(inherit, str) and inherit and inherit != model_name

    if is_extending:
        # Hereda de un modelo existente: patrón de extensión
        if inherits_mail:
            chain = [inherit, "mail.thread", "mail.activity.mixin"]
        else:
            chain = [inherit]
        inherit_line = (
            f"    _inherit = {chain[0]!r}"
            if len(chain) == 1
            else "    _inherit = [" + ", ".join(repr(x) for x in chain) + "]"
        )
    else:
        # Modelo nuevo: reúne los mixins heredados (de inherit como lista o del indicador inherits_mail_thread)
        mixins: list = []
        if isinstance(inherit, list):
            mixins.extend(x for x in inherit if isinstance(x, str) and x and x != model_name)
        if inherits_mail:
            for m in ("mail.thread", "mail.activity.mixin"):
                if m not in mixins:
                    mixins.append(m)
        inherit_line = (
            ("    _inherit = [" + ", ".join(repr(x) for x in mixins) + "]")
            if mixins else ""
        )

    # Compone el cuerpo de la clase
    parts: list[str] = []
    parts.append("from odoo import api, fields, models, _")
    parts.append("")
    parts.append("")
    parts.append(f"class {class_name}(models.Model):")

    if is_extending:
        parts.append(inherit_line)
    else:
        parts.append(f"    _name = {model_name!r}")
        parts.append(f"    _description = {description!r}")
        if inherit_line:
            parts.append(inherit_line)

    if rec_name:
        parts.append(f"    _rec_name = {rec_name!r}")

    parts.append("")

    for line in field_lines:
        parts.append("    " + line if line else "")

    # Elimina las líneas en blanco finales
    while parts and parts[-1].strip() == "":
        parts.pop()

    return "\n".join(parts) + "\n"


def _gen_field_lines(fld: dict) -> list[str]:
    """Devuelve la lista de líneas de código de un campo (sin sangría inicial)."""
    fname = fld["name"]
    ftype = fld["type"]
    string = fld.get("string", fname.replace("_", " ").title())
    required = fld.get("required", False)
    readonly = fld.get("readonly", False)
    index = fld.get("index", False)
    default = fld.get("default")
    tracking = fld.get("tracking", False)
    help_text = fld.get("help", "")

    kwargs: list[str] = [f"string={string!r}"]

    if ftype == "char":
        field_cls = "fields.Char"
    elif ftype == "text":
        field_cls = "fields.Text"
    elif ftype == "html":
        field_cls = "fields.Html"
    elif ftype == "integer":
        field_cls = "fields.Integer"
    elif ftype == "float":
        field_cls = "fields.Float"
    elif ftype == "monetary":
        field_cls = "fields.Monetary"
    elif ftype == "boolean":
        field_cls = "fields.Boolean"
    elif ftype == "date":
        field_cls = "fields.Date"
    elif ftype == "datetime":
        field_cls = "fields.Datetime"
    elif ftype == "binary":
        field_cls = "fields.Binary"
    elif ftype == "selection":
        sel = fld.get("selection", [])
        field_cls = "fields.Selection"
        kwargs.insert(0, f"selection={sel!r}")
    elif ftype == "many2one":
        comodel = fld.get("comodel", "res.partner")
        ondelete = fld.get("ondelete", "set null")
        field_cls = "fields.Many2one"
        kwargs.insert(0, repr(comodel))
        kwargs.append(f"ondelete={ondelete!r}")
    elif ftype == "one2many":
        comodel = fld.get("comodel", "")
        inv = fld.get("inverse_field", "")
        field_cls = "fields.One2many"
        kwargs.insert(0, repr(comodel))
        kwargs.insert(1, repr(inv))
    elif ftype == "many2many":
        comodel = fld.get("comodel", "")
        field_cls = "fields.Many2many"
        kwargs.insert(0, repr(comodel))
    else:
        field_cls = "fields.Char"

    if required:
        kwargs.append("required=True")
    if readonly:
        kwargs.append("readonly=True")
    if index:
        kwargs.append("index=True")
    if tracking:
        kwargs.append("tracking=True")
    if default is not None:
        kwargs.append(f"default={default!r}")
    if help_text:
        kwargs.append(f"help={help_text!r}")

    args_str = ", ".join(kwargs)
    return [f"{fname} = {field_cls}({args_str})"]


def _gen_security_groups(spec: dict, tech: str) -> str:
    security = spec.get("security") or {}
    if isinstance(security, list):
        security = {}
    groups = security.get("groups") or []

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<odoo>",
        "",
    ]
    for grp in groups:
        gname = grp.get("name", "")
        implied = grp.get("implied_by", "")
        xml_id = _to_xml_id(gname)
        if implied and not _XMLID_RE.match(str(implied)):
            raise ValueError(f"implied_by {implied!r} no es un XML-ID válido.")
        lines.append(f'    <record id="group_{xml_id}" model="res.groups">')
        lines.append(f'        <field name="name">{_x(gname)}</field>')
        if implied:
            lines.append(f'        <field name="implied_ids" eval="[(4, ref(\'{implied}\'))]"/>')
        lines.append("    </record>")
        lines.append("")

    lines.append("</odoo>")
    return "\n".join(lines) + "\n"


def _gen_access_csv(spec: dict) -> str:
    tech = spec["technical_name"]
    security = spec.get("security") or {}
    if isinstance(security, list):
        security = {}
    access_rights = security.get("access_rights") or []
    models_spec = spec.get("models") or []

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        ["id", "name", "model_id:id", "group_id:id",
         "perm_read", "perm_write", "perm_create", "perm_unlink"]
    )

    def _perm(value) -> int:
        return 1 if str(value) in ("1", "True") else 0

    if access_rights:
        for ar in access_rights:
            model = str(ar.get("model", ""))
            group = str(ar.get("group", "base.group_user"))
            if not _MODEL_NAME_RE.match(model) or not _XMLID_RE.match(group):
                raise ValueError(f"Regla de acceso no válida: {ar!r}")
            # Acepta tanto las claves al estilo CSV de Odoo (perm_*) como las cortas
            r = _perm(ar.get("perm_read", ar.get("read", 1)))
            w = _perm(ar.get("perm_write", ar.get("write", 1)))
            c = _perm(ar.get("perm_create", ar.get("create", 1)))
            u = _perm(ar.get("perm_unlink", ar.get("unlink", 0)))
            model_xml_id = "model_" + model.replace(".", "_")
            row_id = _to_xml_id(str(ar.get("id") or "")) or (
                f"access_{model.replace('.', '_')}_{group.replace('.', '_')}"
            )
            row_name = str(ar.get("name") or f"{model} ({group})")
            writer.writerow([row_id, row_name, model_xml_id, group, r, w, c, u])
    else:
        # Genera automáticamente una línea solo para administradores por modelo
        for model in models_spec:
            mname = model["name"]
            model_xml_id = "model_" + mname.replace(".", "_")
            row_id = f"access_{mname.replace('.', '_')}_admin"
            writer.writerow([row_id, f"{mname} admin", model_xml_id, "base.group_system", 1, 1, 1, 1])

    return buf.getvalue()


def _gen_view(model_spec: dict, spec: dict) -> str:
    """Genera las vistas de lista, formulario y búsqueda, más la ir.actions.act_window."""
    model_name = model_spec["name"]
    tech = spec["technical_name"]
    fields = model_spec.get("fields") or []
    inherits_mail = model_spec.get("inherits_mail_thread", False)
    menus = spec.get("menus") or []

    # Deriva los ID
    safe = model_name.replace(".", "_")
    list_id = f"{safe}_list_view"
    form_id = f"{safe}_form_view"
    search_id = f"{safe}_search_view"
    action_id = f"{safe}_action"

    # ---- vista de lista ----------------------------------------------------
    # Primeros 6 campos escalares (ni relacionales ni binarios)
    scalar_types = {"char", "text", "integer", "float", "monetary", "boolean",
                    "date", "datetime", "selection"}
    list_fields = [f for f in fields if f.get("type") in scalar_types][:6]

    list_field_lines = "\n".join(
        f'            <field name="{f["name"]}"/>' for f in list_fields
    )
    if not list_field_lines:
        list_field_lines = ""

    # ---- vista de formulario -----------------------------------------------
    # Columna izquierda: char, many2one, text; columna derecha: date, datetime, selection
    left_types = {"char", "many2one", "text", "html"}
    right_types = {"date", "datetime", "selection", "integer", "float",
                   "monetary", "boolean"}
    left_fields = [f for f in fields if f.get("type") in left_types]
    right_fields = [f for f in fields if f.get("type") in right_types]

    def _form_field_line(f):
        return f'                    <field name="{f["name"]}"/>'

    left_lines = "\n".join(_form_field_line(f) for f in left_fields)
    right_lines = "\n".join(_form_field_line(f) for f in right_fields)

    chatter_block = ""
    if inherits_mail:
        chatter_block = "\n        <chatter/>"

    # ---- vista de búsqueda -------------------------------------------------
    search_char_fields = [f for f in fields
                          if f.get("type") in ("char", "text")][:4]
    selection_fields = [f for f in fields if f.get("type") == "selection"]

    search_field_lines = "\n".join(
        f'            <field name="{f["name"]}"/>' for f in search_char_fields
    )
    filter_lines = "\n".join(
        f'            <filter string="{_x(f.get("string", f["name"]))}" '
        f'name="filter_{f["name"]}" domain="[]"/>'
        for f in selection_fields
    )

    # ---- acciones de menú --------------------------------------------------
    # Construye el XML de menú de cada entrada que referencia este modelo
    menu_xml_parts: list[str] = []
    model_menus = _collect_model_menus(model_name, menus, tech)
    for entry in model_menus:
        menu_xml_parts.append(entry)

    menu_xml = "\n\n    ".join(menu_xml_parts)
    if menu_xml:
        menu_xml = "\n\n    " + menu_xml

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- Vista de lista -->
    <record id="{list_id}" model="ir.ui.view">
        <field name="name">{model_name}.list</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <list>
{list_field_lines}
            </list>
        </field>
    </record>

    <!-- Vista de formulario -->
    <record id="{form_id}" model="ir.ui.view">
        <field name="name">{model_name}.form</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <group>
{left_lines}
                        </group>
                        <group>
{right_lines}
                        </group>
                    </group>
                </sheet>{chatter_block}
            </form>
        </field>
    </record>

    <!-- Vista de búsqueda -->
    <record id="{search_id}" model="ir.ui.view">
        <field name="name">{model_name}.search</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <search>
{search_field_lines}
{filter_lines}
            </search>
        </field>
    </record>

    <!-- Acción -->
    <record id="{action_id}" model="ir.actions.act_window">
        <field name="name">{_x(model_spec.get("description", model_name))}</field>
        <field name="res_model">{model_name}</field>
        <field name="view_mode">list,form</field>
    </record>{menu_xml}

</odoo>
"""
    return xml


def _gen_demo_data(spec: dict) -> str:
    """Genera un demo.xml vacío: los registros reales se completan después de generar."""
    tech = spec["technical_name"]
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<odoo>",
        "    <!-- Datos de demostración -->",
        "</odoo>",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _write_py(zf: zipfile.ZipFile, arcname: str, source: str, tech: str) -> None:
    """Escribe *source* en *arcname* dentro de *zf*; lanza ValueError si hay errores de sintaxis."""
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(
            f"Error de sintaxis en el archivo generado {arcname!r}: {exc.msg} "
            f"(línea {exc.lineno})\n\nCódigo fuente:\n{source}"
        ) from exc
    zf.writestr(arcname, source)


def _model_name_to_file(model_name: str) -> str:
    """Convierte 'my.module.task' -> 'my_module_task'."""
    return model_name.replace(".", "_")


def _model_name_to_class(model_name: str) -> str:
    """Convierte 'my.module.task' -> 'MyModuleTask'."""
    return "".join(part.capitalize() for part in model_name.split("."))


def _to_xml_id(name: str) -> str:
    """Convierte un nombre visible en un fragmento de XML-ID seguro."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _collect_model_menus(model_name: str, menus: list, tech: str) -> list[str]:
    """Construye el XML de ir.ui.menu de cada entrada de menú cuyo action_model == model_name."""
    result: list[str] = []
    safe = model_name.replace(".", "_")
    action_id = f"{safe}_action"

    for top in menus:
        top_name = top.get("name", "")
        top_id = f"menu_{_to_xml_id(top_name)}"
        seq = _int(top.get("sequence", 10))
        children = top.get("children") or []

        # Emite el menú de primer nivel solo si aún no se ha emitido
        # (gana el primer modelo que lo referencia; los demás usan el id existente)
        matching_children = [c for c in children
                             if c.get("action_model") == model_name]
        if not matching_children:
            continue

        result.append(
            f'<menuitem id="{top_id}" name="{_x(top_name)}" sequence="{seq}"/>'
        )
        for child in matching_children:
            child_name = child.get("name", model_name)
            child_id = f"menu_{_to_xml_id(top_name)}_{_to_xml_id(child_name)}"
            child_seq = _int(child.get("sequence", 10))
            result.append(
                f'<menuitem id="{child_id}" name="{_x(child_name)}" '
                f'parent="{top_id}" '
                f'action="{action_id}" '
                f'sequence="{child_seq}"/>'
            )

    return result
