# -*- coding: utf-8 -*-
"""Paquete 6, CR-56: el parte diario pasa a ser uno por persona, obra y día
(y uno de obra por día): se quita el índice único anterior por obra y día."""


def migrate(cr, version):
    cr.execute('DROP INDEX IF EXISTS construction_daily_report_project_date_unique')
