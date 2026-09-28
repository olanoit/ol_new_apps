# -*- coding: utf-8 -*-
"""Fórmulas corregidas por la auditoría de planillas (27/09/2026).

Las reglas salariales van en datos ``noupdate``: actualizar el módulo no
corrige las bases ya instaladas. ``hr.salary.rule._l10n_pe_sync_formulas``
reescribe, por xmlid, solo las reglas cuya fórmula sigue IGUAL a alguna
de las entregadas antes (una fórmula ajustada a mano se respeta y se avisa
en el log). Es idempotente: lo llama la migración y también un
``<function>`` de datos en cada actualización, para cubrir bases que ya
estaban en la versión nueva cuando se amplió la lista de variantes.
"""

# xmlid -> (fórmula entregada antes, fórmula nueva). La «antes» puede ser
# una tupla con todas las variantes entregadas en versiones anteriores.
L10N_PE_AUDIT_RULES = {
    'salary_rule_FER': (
        "result = worked_days['FER'].number_of_days * (version.wage/30)",
        "# Feriado o descanso semanal LABORADO (D.Leg. 713 arts. 3-4 y 9): la\n# remuneración del día de descanso ya va en el sueldo (DOM); la labor se\n# paga ADEMÁS con una sobretasa del 100 %, es decir, doble.\nresult = worked_days['FER'].number_of_days * (version.wage/30) * 2",
    ),
    'salary_rule_AF': ((
        # Antes de los derechohabientes (bases que nunca recibieron esa
        # versión de la fórmula: el dato va en noupdate).
        "if version.children > 0 and version.l10n_pe_labor_regime != 'fourth-fifth':\n    if worked_days['DVAC'].number_of_days ==30 or worked_days['SENF'].number_of_days ==30 or worked_days['SMAR'].number_of_days ==30:\n        result=0\n    else:\n        result = payslip.family_allowance\nelse:\n    result = 0",
        "if payslip.l10n_pe_family_allowance_ok and version.l10n_pe_labor_regime != 'fourth-fifth':\n    if worked_days['DVAC'].number_of_days ==30 or worked_days['SENF'].number_of_days ==30 or worked_days['SMAR'].number_of_days ==30:\n        result=0\n    else:\n        result = payslip.family_allowance\nelse:\n    result = 0"),
        "# Ley 25129: no alcanza a los practicantes (modalidades formativas, Ley\n# 28518), que perciben una subvención y no una remuneración.\nif payslip.l10n_pe_family_allowance_ok and version.l10n_pe_labor_regime != 'practicante':\n    if worked_days['DVAC'].number_of_days ==30 or worked_days['SENF'].number_of_days ==30 or worked_days['SMAR'].number_of_days ==30:\n        result=0\n    else:\n        result = payslip.family_allowance\nelse:\n    result = 0",
    ),
    'salary_rule_ONP': (
        "if payslip.membership_id.name == 'ONP':\n    result = round((payslip.l10n_pe_retirement_fund/100) * AONP, 2)\nelse:\n    result = 0",
        '# SNP: afiliación que no es AFP (ONP; «sin régimen» tiene tasa 0). Por\n# flag y tasas, nunca por el nombre de la entidad.\nif payslip.membership_id and not payslip.membership_id.is_afp:\n    result = round((payslip.l10n_pe_retirement_fund/100) * AONP, 2)\nelse:\n    result = 0',
    ),
    'salary_rule_A_JUB': (
        "if payslip.membership_id.name == 'ONP':\n    result = 0\nelif payslip.membership_id.name == 'AFP HABITAT':\n    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)\nelif payslip.membership_id.name == 'AFP INTEGRA':\n    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)\nelif payslip.membership_id.name == 'AFP PRIMA':\n    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)\nelif payslip.membership_id.name == 'AFP PROFUTURO':\n    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)\nelif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':\n    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)\nelif payslip.membership_id.name == 'SIN RÉGIMEN':\n    result = 0\nelse:\n    result = 0",
        'if payslip.membership_id.is_afp:\n    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)\nelse:\n    result = 0',
    ),
    'salary_rule_COMFI': (
        "if version.l10n_pe_commission_type == 'flow':\n    if payslip.membership_id.name == 'ONP':\n        result = 0\n    elif payslip.membership_id.name == 'AFP HABITAT':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'AFP INTEGRA':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'AFP PRIMA':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'AFP PROFUTURO':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    else:\n        result = 0\nelse:\n    result = 0",
        "if version.l10n_pe_commission_type == 'flow' and payslip.membership_id.is_afp:\n    result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\nelse:\n    result = 0",
    ),
    'salary_rule_COMMIX': (
        "if version.l10n_pe_commission_type == 'mixed':\n    if payslip.membership_id.name == 'ONP':\n        result = 0\n    elif payslip.membership_id.name == 'AFP HABITAT':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'AFP INTEGRA':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'AFP PRIMA':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'AFP PROFUTURO':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':\n        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\n    else:\n        result = 0\nelse:\n    result = 0",
        "if version.l10n_pe_commission_type == 'mixed' and payslip.membership_id.is_afp:\n    result = round((payslip.l10n_pe_commission/100) * AAFP, 2)\nelse:\n    result = 0",
    ),
    'salary_rule_SEGI': (
        "if version.l10n_pe_is_older:\n    result = 0\nelse:\n    if payslip.membership_id.name == 'ONP':\n        result = 0\n    elif payslip.membership_id.name in ('AFP HABITAT', 'AFP INTEGRA', 'AFP PRIMA', 'AFP PROFUTURO'):\n        if AAFP < payslip.l10n_pe_insurable_remuneration:\n            result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)\n        else:\n            result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)\n    elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':\n        result = 0\n    else:\n        result = 0",
        '# Prima de seguro sobre el afecto, con el tope asegurable de la SBS. Los\n# mayores de 65 no la pagan; las entidades sin prima (p. ej. jubilado en\n# tránsito) tienen tasa 0.\nif version.l10n_pe_is_older or not payslip.membership_id.is_afp:\n    result = 0\nelif AAFP < payslip.l10n_pe_insurable_remuneration:\n    result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)\nelse:\n    result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)',
    ),
    'salary_rule_ESSALUD': (
        "if version.l10n_pe_labor_regime not in ('fourth-fifth', 'practicante'):\n    if version.social_insurance_id.name == 'EPS':\n        result = AESSALUD * version.social_insurance_id.percent/100\n    else:\n        if AESSALUD > payslip.rmv:\n            result = AESSALUD * 0.09\n        else:\n            result = payslip.rmv * 0.09\nelse:\n    result = 0",
        "if version.l10n_pe_labor_regime != 'practicante':\n    if version.social_insurance_id.name == 'EPS':\n        result = AESSALUD * version.social_insurance_id.percent/100\n    else:\n        if AESSALUD > payslip.rmv:\n            result = AESSALUD * 0.09\n        else:\n            result = payslip.rmv * 0.09\nelse:\n    result = 0",
    ),
    'salary_rule_NETVACA': (
        'net_vac = VAC+VATRU-((TAT-QUINTA) * VACAFE)\nif net_rem < 0:\n    result = net_vac + net_rem\nelse:\n    result = (net_vac - ADE_VAC) if abs(net_vac - ADE_VAC) >0.1 else 0',
        '# El neto de remuneraciones SIN el tope en cero de NETREMU se recalcula\n# aquí: antes se leía la variable local de otra regla.\nnet_rem = TINGR-TDESN-VAC-VATRU-GRA_TRU-BON9_TRU-CTS_TRU-((TAT-QUINTA) * REMAFE)-QUINTA+ADE_VAC\nnet_vac = VAC+VATRU-((TAT-QUINTA) * VACAFE)\nif net_rem < 0:\n    result = net_vac + net_rem\nelse:\n    result = (net_vac - ADE_VAC) if abs(net_vac - ADE_VAC) >0.1 else 0',
    ),
}


L10N_PE_EXTRA_HOURS_TYPES = ('wd_HE25', 'wd_HE35', 'wd_HE100')
