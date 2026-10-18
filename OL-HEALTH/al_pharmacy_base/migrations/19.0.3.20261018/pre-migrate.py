# -*- coding: utf-8 -*-
"""Los datos de demostración de laboratorios, principios activos, medicamentos y presentaciones vivían en al_industry_pharmacy: en
las bases que ya los tienen, pasan a este módulo (mismo nombre) y no se
duplican al cargar su nueva demo."""
from odoo.tools import SQL

NAMES = ('lab_andino', 'lab_rimac', 'lab_sol', 'ingredient_paracetamol', 'ingredient_ibuprofeno', 'ingredient_amoxicilina', 'ingredient_insulina_humana', 'ingredient_azitromicina', 'ingredient_losartan', 'ingredient_metformina', 'ingredient_clonazepam', 'ingredient_alprazolam', 'ingredient_loratadina', 'ingredient_omeprazol', 'product_paracetamol', 'product_dolofen', 'product_ibuprofen', 'product_ibuflam', 'product_loratadine', 'product_omeprazole', 'product_amoxicillin', 'product_amoxival', 'product_azithromycin', 'product_losartan', 'product_metformin', 'product_insulin', 'product_clonazepam', 'product_alprazolam', 'product_paracetamol_presentation_1', 'product_paracetamol_presentation_2', 'product_dolofen_presentation_1', 'product_dolofen_presentation_2', 'product_ibuprofen_presentation_1', 'product_ibuprofen_presentation_2', 'product_ibuflam_presentation_1', 'product_loratadine_presentation_1', 'product_omeprazole_presentation_1', 'product_omeprazole_presentation_2', 'product_amoxicillin_presentation_1', 'product_amoxicillin_presentation_2', 'product_amoxival_presentation_1', 'product_azithromycin_presentation_1', 'product_losartan_presentation_1', 'product_losartan_presentation_2', 'product_metformin_presentation_1', 'product_metformin_presentation_2', 'product_clonazepam_presentation_1', 'product_alprazolam_presentation_1')


def migrate(cr, version):
    cr.execute(SQL(
        """UPDATE ir_model_data old SET module = %s
            WHERE old.module = 'al_industry_pharmacy' AND old.name IN %s
              AND NOT EXISTS (SELECT 1 FROM ir_model_data new
                               WHERE new.module = %s AND new.name = old.name)""",
        'al_pharmacy_base', tuple(NAMES), 'al_pharmacy_base'))
