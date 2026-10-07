# -*- coding: utf-8 -*-
"""Reglas multicompañía de la suite (guía de Odoo 19, «Multi-company
Guidelines»), comprobadas sobre todos los módulos propios instalados.

- Un modelo con ``company_id`` tiene regla de registro por compañía y
  ``_check_company_auto`` (Odoo valida en create/write que los registros
  relacionados sean de la misma compañía o compartidos).
- Sus Many2one hacia modelos con compañía llevan ``check_company=True``.
- En las vistas propias el campo Compañía es de solo lectura: se toma de la
  compañía activa y no se cambia (decisión del proyecto, 08/10/2026).

Los catálogos SUNAT y tablas globales (sin ``company_id``) son compartidos a
propósito y no entran aquí.
"""
from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

OWN_PREFIXES = ('al_', 'ol_')
OWN_MODULES = ('l10n_pe_vat_sunat',)
# De terceros o gestionados aparte: no se revisan.
EXCLUDED = ('ol_licencia_perpetua', 'al_l10n_pe_city')
SHARED_COMODELS = ('res.company', 'res.users', 'res.partner', 'res.currency')
# Excepciones justificadas: el periodo SIRE es de la compañía raíz (el RUC) y
# recoge comprobantes de sus sucursales; check_company solo admite la misma
# compañía o una superior, así que rechazaría los de las sucursales.
EXEMPT_FIELDS = ('l10n_pe.sire.rce.line.move_id', 'l10n_pe.sire.rvie.line.move_id',
                 'l10n_pe.sire.rce.nd.line.move_id')


@tagged('post_install', '-at_install')
class TestMulticompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        installed = cls.env['ir.module.module'].search([('state', '=', 'installed')])
        cls.own = {
            module.name for module in installed
            if (module.name.startswith(OWN_PREFIXES) or module.name in OWN_MODULES)
            and module.name not in EXCLUDED
        }

    def _own_models(self):
        for name in self.env.registry:
            model = self.env[name]
            if model._abstract or model._transient or not model._auto:
                continue
            if model._original_module in self.own:
                yield name, model

    def test_company_models_have_rule_and_check(self):
        rules = self.env['ir.rule'].sudo().search([])
        with_rule = {rule.model_id.model for rule in rules if 'company' in (rule.domain_force or '')}
        missing_rule, missing_auto = [], []
        for name, model in self._own_models():
            if 'company_id' not in model._fields:
                continue
            if name not in with_rule:
                missing_rule.append(name)
            if not model._check_company_auto:
                missing_auto.append(name)
        self.assertFalse(missing_rule, 'sin regla de compañía: %s' % missing_rule)
        self.assertFalse(missing_auto, 'sin _check_company_auto: %s' % missing_auto)

    def test_many2one_check_company(self):
        offenders = []
        for name, model in self._own_models():
            if 'company_id' not in model._fields:
                continue
            for fname, field in model._fields.items():
                if (field.type == 'many2one' and fname != 'company_id'
                        and field._module in self.own and not field.related
                        and field.comodel_name not in SHARED_COMODELS
                        and field.comodel_name in self.env
                        and 'company_id' in self.env[field.comodel_name]._fields
                        and not field.check_company
                        and '%s.%s' % (name, fname) not in EXEMPT_FIELDS):
                    offenders.append('%s.%s' % (name, fname))
        self.assertFalse(offenders, 'Many2one sin check_company: %s' % offenders)

    def test_company_readonly_in_own_views(self):
        views = self.env['ir.ui.view'].search([('type', 'in', ('form', 'list'))])
        offenders = []
        for view in views:
            xmlid = view.get_external_id().get(view.id) or ''
            module = xmlid.split('.')[0]
            if module not in self.own or view.model == 'res.config.settings':
                continue
            for node in etree.fromstring(view.arch_db).xpath("//field[@name='company_id']"):
                if node.getparent() is not None and node.getparent().tag == 'search':
                    continue
                hidden = node.get('invisible') in ('1', 'True') or \
                    node.get('column_invisible') in ('1', 'True')
                if not hidden and node.get('readonly') not in ('1', 'True'):
                    offenders.append(xmlid)
        self.assertFalse(sorted(set(offenders)), 'Compañía editable en: %s' % sorted(set(offenders)))
