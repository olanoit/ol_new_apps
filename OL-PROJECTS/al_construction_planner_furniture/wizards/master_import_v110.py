# -*- coding: utf-8 -*-
"""Listas de materiales por etapa desde el importador (paquete 1.10, M110-02).

Después de la receta de la tipología y de los materiales de sus módulos, el
importador arma las listas de fabricación de cada tipología según la cadena
de plantas del catálogo de etapas. Sin cadena no hace nada."""
from markupsafe import Markup, escape

from odoo import models


class ConstructionMasterImportWizard(models.TransientModel):
    _inherit = 'construction.master.import.wizard'

    def _analyze(self):
        result = super()._analyze()
        if not self.file or not self.project_id or not result.get('stats'):
            return result
        company = self._company()
        chain = self.env['construction.stage']._production_chain(company)
        missing = chain[:-1].filtered(
            lambda stage: not stage.with_company(company).intermediate_categ_id)
        if missing:
            result['warnings']['stage_no_category'].extend(
                missing.mapped(lambda stage: stage._label()))
        return result

    def _warning_messages(self):
        messages = super()._warning_messages()
        messages['stage_no_category'] = self.env._(
            'Etapas de la cadena de plantas sin «Categoría de lo que entrega» (el producto '
            'intermedio queda en la categoría por defecto)')
        return messages

    def _apply(self, data):
        summary = super()._apply(data)
        warnings = []
        codes = set(data.get('bom', {})) | set(data.get('typologies', {})) | {
            typology for typology, _module in data.get('module_bom', {})}
        typologies = self.env['construction.typology'].search(
            [('project_id', '=', self.project_id.id), ('code', 'in', list(codes))])
        for typology in typologies:
            warnings += self._sync_stage_boms(typology, self._company())
        if warnings:
            # sudo: como el mensaje del importador, va al historial de la obra.
            self.project_id.sudo().message_post(
                author_id=self.env.user.partner_id.id,
                body=Markup('%s<ul>%s</ul>') % (
                    self.env._('Listas de fabricación por etapa:'),
                    Markup('').join(Markup('<li>%s</li>') % escape(text) for text in warnings)))
        return summary

    def _sync_stage_boms(self, typology, company):
        """Listas de fabricación de la tipología (M110-02)."""
        return typology._construction_sync_stage_boms(company)
