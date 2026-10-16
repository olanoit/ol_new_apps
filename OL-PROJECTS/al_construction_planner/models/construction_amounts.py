# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10).

Quien no tiene el grupo «Planificación de obra: ve montos» trabaja con
cantidades, fechas, avance y estados, sin costos, precios, presupuestos,
comprometido, real ni saldos.

Los campos de monto NO llevan ``groups=``: en Odoo 19 el ORM verifica el grupo
también al leer el campo desde Python, y el avance, el control de saldo, las
políticas de exceso y los recálculos los leen con el usuario que registra.
La restricción se aplica en lo que llega al navegador: las vistas (cada campo
de monto recibe el grupo), las lecturas y agrupaciones del cliente web, las
exportaciones, los paneles OWL y los reportes.
"""
from lxml import etree

from odoo import api, models
from odoo.exceptions import AccessError

from .common import AMOUNTS_GROUP, can_see_amounts


class ConstructionAmountsMixin(models.AbstractModel):
    _name = 'construction.amounts.mixin'
    _description = 'Montos del planificador visibles solo con su grupo'

    @api.model
    def _construction_amount_fields(self):
        """Campos de monto del modelo. Cada modelo (y cada puente) suma los
        suyos con ``super()``."""
        return set()

    @api.model
    def _construction_hidden_amounts(self):
        """Campos de monto que el usuario actual no puede ver."""
        if can_see_amounts(self.env):
            return set()
        return self._construction_amount_fields()

    # ------------------------------------------------------------------
    # Vistas
    # ------------------------------------------------------------------
    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        self._construction_restrict_amounts(arch)
        return arch, view

    @api.model
    def _construction_restrict_amounts(self, node):
        """Pone el grupo de montos en los campos de monto del arch, también en
        las sublistas de otros modelos del planificador (líneas del plan)."""
        amounts = self._construction_amount_fields()
        for child in list(node):
            if not isinstance(child.tag, str):
                continue
            name = child.get('name') if child.tag == 'field' else child.get('for') \
                if child.tag == 'label' else None
            if name in amounts:
                self._construction_set_amount_group(child)
                continue
            field = self._fields.get(name) if child.tag == 'field' else None
            if field is not None and field.relational and len(child):
                comodel = self.env[field.comodel_name]
                if hasattr(comodel, '_construction_restrict_amounts'):
                    comodel._construction_restrict_amounts(child)
                continue
            self._construction_restrict_amounts(child)

    @staticmethod
    def _construction_set_amount_group(node):
        groups = node.get('groups')
        if not groups:
            node.set('groups', AMOUNTS_GROUP)
            return
        if AMOUNTS_GROUP in groups.split(','):
            return
        # El atributo «groups» es un O lógico: para exigir los dos se envuelve
        # el nodo en un <t> con el grupo de montos.
        wrapper = etree.Element('t', groups=AMOUNTS_GROUP)
        node.addprevious(wrapper)
        wrapper.append(node)

    # ------------------------------------------------------------------
    # Cliente web: lecturas, agrupaciones y exportaciones
    # ------------------------------------------------------------------
    @api.model
    def _construction_strip_specification(self, specification):
        hidden = self._construction_hidden_amounts()
        result = {}
        for name, spec in specification.items():
            if name in hidden:
                continue
            field = self._fields.get(name)
            if spec and spec.get('fields') and field is not None and field.relational:
                comodel = self.env[field.comodel_name]
                if hasattr(comodel, '_construction_strip_specification'):
                    spec = dict(spec, fields=comodel._construction_strip_specification(
                        spec['fields']))
            result[name] = spec
        return result

    def web_read(self, specification):
        return super().web_read(self._construction_strip_specification(specification))

    @api.model
    def _construction_check_aggregates(self, groupby=(), aggregates=()):
        hidden = self._construction_hidden_amounts()
        if not hidden:
            return
        names = {spec.split(':')[0].split('.')[0] for spec in list(groupby) + list(aggregates)}
        if names & hidden:
            raise AccessError(self.env._(
                'Los montos de la planificación solo los ve el grupo «Planificación de obra: '
                've montos».'))

    @api.model
    def web_read_group(self, domain, groupby, aggregates=(), *args, **kwargs):
        self._construction_check_aggregates(groupby, aggregates)
        return super().web_read_group(domain, groupby, aggregates, *args, **kwargs)

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), *args, **kwargs):
        self._construction_check_aggregates(groupby, aggregates)
        return super().formatted_read_group(domain, groupby, aggregates, *args, **kwargs)

    @api.model
    def formatted_read_grouping_sets(self, domain, grouping_sets, aggregates=(), **kwargs):
        self._construction_check_aggregates(
            [name for grouping in grouping_sets for name in grouping], aggregates)
        return super().formatted_read_grouping_sets(domain, grouping_sets, aggregates, **kwargs)

    def export_data(self, fields_to_export):
        """Exportación a Excel: las columnas de monto salen vacías."""
        result = super().export_data(fields_to_export)
        hidden = self._construction_hidden_amounts()
        if not hidden:
            return result
        blank = []
        for index, path in enumerate(fields_to_export):
            model, parts = self, path.replace('.id', '').split('/')
            for part in parts:
                if part in getattr(model, '_construction_hidden_amounts', lambda: set())():
                    blank.append(index)
                    break
                field = model._fields.get(part)
                if field is None or not field.relational:
                    break
                model = self.env[field.comodel_name]
        for row in result.get('datas', []):
            for index in blank:
                row[index] = False
        return result


# Modelos del núcleo con montos: se suman al mixin aquí, después de definidos.
class ConstructionResourcePlan(models.Model):
    _name = 'construction.resource.plan'
    _inherit = ['construction.resource.plan', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {
            'amount_material', 'amount_service', 'amount_contract', 'amount_labor',
            'amount_production', 'amount_equipment', 'amount_total', 'amount_budgeted',
            'amount_committed', 'amount_actual', 'amount_remaining', 'stage_summary_html',
            'control_html'}


class ConstructionResourcePlanLine(models.Model):
    _name = 'construction.resource.plan.line'
    _inherit = ['construction.resource.plan.line', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {
            'price_unit_planned', 'amount_planned', 'amount_budgeted', 'amount_baseline',
            'amount_version_diff', 'amount_deviation', 'amount_committed', 'amount_actual',
            'amount_remaining'}


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'construction_plan_amount'}


class ConstructionSpaceStage(models.Model):
    _name = 'construction.space.stage'
    _inherit = ['construction.space.stage', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_planned'}


class ConstructionTaskProgress(models.Model):
    _name = 'construction.task.progress'
    _inherit = ['construction.task.progress', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount'}


class ConstructionMeasurement(models.Model):
    _name = 'construction.measurement'
    _inherit = ['construction.measurement', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_difference'}


class ConstructionMeasurementLine(models.Model):
    _name = 'construction.measurement.line'
    _inherit = ['construction.measurement.line', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'unit_amount', 'amount_difference'}


class ConstructionTypology(models.Model):
    _name = 'construction.typology'
    _inherit = ['construction.typology', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'space_contract_amount'}


class ConstructionExecutionTemplate(models.Model):
    _name = 'construction.execution.template'
    _inherit = ['construction.execution.template', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_unit'}


class ConstructionExecutionTemplateLine(models.Model):
    _name = 'construction.execution.template.line'
    _inherit = ['construction.execution.template.line', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'price_unit', 'amount_unit'}


class ConstructionLaborActivity(models.Model):
    _name = 'construction.labor.activity'
    _inherit = ['construction.labor.activity', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'default_price'}


class ConstructionLaborRate(models.Model):
    _name = 'construction.labor.rate'
    _inherit = ['construction.labor.rate', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'price'}


class ConstructionExceedLog(models.Model):
    _name = 'construction.exceed.log'
    _inherit = ['construction.exceed.log', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount'}
