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
# La plantilla de turno solo tiene compañía si está instalado project_forecast
# (no es dependencia): con check_company la vista no valida sin él.
EXEMPT_FIELDS = ('l10n_pe.sire.rce.line.move_id', 'l10n_pe.sire.rvie.line.move_id',
                 'l10n_pe.sire.rce.nd.line.move_id', 'l10n_pe.sire.action.wizard.move_ids',
                 'l10n_pe.hr.shift.cycle.assignment.template_id')


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

    def test_company_settings_marked(self):
        """Cada ajuste propio guardado en la compañía lleva el ícono de Odoo
        «valores por compañía» (``<setting company_dependent="1">``)."""
        Settings = self.env['res.config.settings']
        company_fields = {
            fname for fname, field in Settings._fields.items()
            if field._module in self.own
            and (field.related or '').startswith('company_id.')
        }
        arch = etree.fromstring(Settings.get_view(view_type='form')['arch'])
        offenders = sorted({
            node.get('name') for setting in arch.iter('setting')
            if setting.get('company_dependent') != '1'
            for node in setting.iter('field') if node.get('name') in company_fields
        })
        self.assertTrue(company_fields)
        self.assertFalse(offenders, 'Ajustes por compañía sin company_dependent: %s' % offenders)

    def test_root_delegated_fields_reach_branches(self):
        """Lo que es del RUC (agente de retención, PLE simplificado, SIREC,
        sentido de destinos…) llega a las sucursales, como el ejercicio
        fiscal en Odoo."""
        Company = self.env['res.company']
        own = [fname for fname in Company._get_company_root_delegated_field_names()
               if Company._fields[fname]._module in self.own]
        branch = Company.create({'name': 'Sucursal de control',
                                 'parent_id': self.env.company.id})
        for fname in own:
            self.assertEqual(branch[fname], self.env.company[fname], fname)

    def test_wizards_check_company(self):
        """Los asistentes con compañía validan en el servidor que lo que
        reciben (empleados, documentos, parámetros) sea de esa compañía:
        el filtro de la vista solo actúa en pantalla."""
        missing_auto, offenders = [], []
        for name in self.env.registry:
            model = self.env[name]
            if not model._transient or model._original_module not in self.own \
                    or 'company_id' not in model._fields:
                continue
            if not model._check_company_auto:
                missing_auto.append(name)
            # Si la compañía sale de un campo (related), ese campo la define.
            source = (model._fields['company_id'].related or '').split('.')[0]
            for fname, field in model._fields.items():
                if (field.type in ('many2one', 'many2many') and fname not in ('company_id', source)
                        and field._module in self.own and not field.related
                        and field.comodel_name not in SHARED_COMODELS
                        and field.comodel_name in self.env
                        and 'company_id' in self.env[field.comodel_name]._fields
                        and not field.check_company
                        and '%s.%s' % (name, fname) not in EXEMPT_FIELDS):
                    offenders.append('%s.%s' % (name, fname))
        self.assertFalse(missing_auto, 'Asistentes sin _check_company_auto: %s' % missing_auto)
        self.assertFalse(offenders, 'Asistentes sin check_company: %s' % offenders)
