# Diferencias BASE (migrada) ↔ BASE MG (Excel del cliente)

Generado por `f02_reglas.py`.

- Solo en BASE MG (41): AAFP_AQ, ADELANTO_AQ, AF_AQ, AONP_AQ, A_JUB_AQ, BAS_AQ, BAS_M_AQ, BONIFC, BONR_AQ, BUC, COMFI_AQ, COMI_AQ, COMMIX_AQ, CONAFOV, DES_SIN, DMED_AQ, DOM, DPAT_AQ, ESC, FAL_AQ, FER_AQ, HE25_AQ, HE35_AQ, LCGH_AQ, LSGH_AQ, MOV, NETO_AQ, ONP_AQ, OTRDSC, PREST_AQ, QUINTA_AQ, SEGI_AQ, SENF_AQ, SMAR_AQ, TAR_AQ, TAT_AQ, TDESN_AQ, TDES_AQ, TINGR_AQ, TOT_EXT_AQ, VAC_AQ
- Solo en BASE (3): NETVACA, REMAFE, VACAFE
- Comunes (61), de los cuales 18 con código Python distinto

## Reglas comunes con código distinto

### AF — Asignación Familiar

**BASE (migrada v19):**

```python
if version.children > 0 and version.l10n_pe_labor_regime != 'fourth-fifth':
    if worked_days['DVAC'].number_of_days ==30 or worked_days['SENF'].number_of_days ==30 or worked_days['SMAR'].number_of_days ==30:
        result=0
    else:
        result = payslip.family_allowance
else:
    result = 0
```

**BASE MG (cliente, saneada):**

```python
# 1. Condición Mandatoria: El empleado debe tener hijos y no pertenecer al régimen 'fourth-fifth'
if employee.children > 0 and version.l10n_pe_labor_regime != 'fourth-fifth':
    
    # Lista de regímenes que NO deben recibir Asignación Familiar (excluidos)
    regimenes_excluidos = ['construccion']

    # 2. Verificar el Régimen Laboral: Si NO está en la lista de excluidos
    if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() not in regimenes_excluidos:
        
        # Helper function to safely get number_of_days or 0
        def get_days(code):
            return worked_days[code].number_of_days if code in worked_days else 0

        # 3. Excepción por Ausencia Completa (30 días)
        if get_days('DVAC') == 30 or \
           get_days('SENF') == 30 or \
           get_days('SMAR') == 30:
            
            result = 0
        else:
            # 4. Cálculo de la Asignación Familiar
            result = (payslip.rmv or 0) * 0.10
            
    else:
        # 5. Si el régimen ES 'construccion civil' (excluido)
        result = 0

else:
    # 6. Si no cumple la Condición Mandatoria (sin hijos o régimen incorrecto)
    result = 0
```

### A_JUB — AFP Aporte Fondo de Pensiones

**BASE (migrada v19):**

```python
if payslip.membership_id.name == 'ONP':
    result = 0
elif payslip.membership_id.name == 'AFP HABITAT':
    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
elif payslip.membership_id.name == 'AFP INTEGRA':
    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
elif payslip.membership_id.name == 'AFP PRIMA':
    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
elif payslip.membership_id.name == 'AFP PROFUTURO':
    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':
    result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
elif payslip.membership_id.name == 'SIN RÉGIMEN':
    result = 0
else:
    result = 0
```

**BASE MG (cliente, saneada):**

```python
# Regímenes con cálculo distinto de AFP
regimenes_excluidos = ['construccion']

# Verificar si el régimen laboral no está en la lista de excluidos
if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() not in regimenes_excluidos:
    if payslip.membership_id.name == 'ONP':
        result = 0
    elif payslip.membership_id.name == 'AFP HABITAT':
        result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP INTEGRA':
        result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP PRIMA':
        result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP PROFUTURO':
        result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
    elif payslip.membership_id.name == 'JUB PROFUT TRANSITO':
        result = round((payslip.l10n_pe_retirement_fund/100) * AAFP, 2)
    elif payslip.membership_id.name == 'SIN REGIMEN':
        result = 0
else:
    # Si el régimen laboral es 'construccion civil' se calcula así
    if payslip.membership_id.name == 'ONP':
        result = 0
    else:
        result = (BAS + DOM + HE100 + VATRU + BUC + BONIFC) * 0.1 + \
                 (BAS + DOM + HE100 + VATRU + BUC + BONIFC) * 0.01
```

### BAS — Basico

**BASE (migrada v19):**

```python
if version.wage_type == 'hourly':
    hour_lab = worked_days['DLAB'].number_of_hours+worked_days['DOM'].number_of_hours+worked_days['FAL'].number_of_hours+worked_days['LSGH'].number_of_hours
    if version.schedule_pay == 'daily':
        result = hour_lab * (version.wage/version.resource_calendar_id.hours_per_day)
    elif version.schedule_pay == 'weekly':
        result = hour_lab * (version.wage/version.resource_calendar_id.full_time_required_hours)
    else:
        result = hour_lab * (version.wage/30/8)
else:
    total_dias = worked_days['DLAB'].number_of_days+worked_days['DOM'].number_of_days+worked_days['FAL'].number_of_days+worked_days['DVAC'].number_of_days+worked_days['DMED'].number_of_days+worked_days['DPAT'].number_of_days+worked_days['LCGH'].number_of_days+worked_days['LSGH'].number_of_days+worked_days['SMAR'].number_of_days+worked_days['SENF'].number_of_days
    dias_lab = worked_days['DLAB'].number_of_days+worked_days['DOM'].number_of_days+worked_days['FAL'].number_of_days+worked_days['LSGH'].number_of_days
    if total_dias >= payslip.date_to.day:
        if dias_lab >= payslip.date_to.day:
            result = version.wage
        else:
            result = ((dias_lab + (30-payslip.date_to.day)) * (version.wage/30)) if dias_lab != 0 else 0
    else:
        result = dias_lab * (version.wage/30)
```

**BASE MG (cliente, saneada):**

```python
# ----------------------------------------------------------
# CÁLCULO PARA CONTRATOS POR HORA (corrigiendo minutos)
# ----------------------------------------------------------

def normalizar_horas(horas):
    if not horas:
        return 0.0

    # Si viene como string "39:30"
    if isinstance(horas, str) and ":" in horas:
        h, m = horas.split(":")
        return int(h) + int(m) / 60.0

    # Si viene como número decimal (ejemplo 39.50) => ya está en base 60
    if isinstance(horas, (int, float)):
        return float(horas)

    return 0.0


if version.wage_type == 'hourly':
    # Sumar horas normalizadas de cada tipo de día
    dlab = normalizar_horas(worked_days.get('DLAB').number_of_hours if worked_days.get('DLAB') else 0.0)
    dom  = normalizar_horas(worked_days.get('DOM').number_of_hours if worked_days.get('DOM') else 0.0)
    fal  = normalizar_horas(worked_days.get('FAL').number_of_hours if worked_days.get('FAL') else 0.0)
    lsg  = normalizar_horas(worked_days.get('LSGH').number_of_hours if worked_days.get('LSGH') else 0.0)

    hour_lab = dlab + dom + fal + lsg

    # Calcular pago según frecuencia
    if version.schedule_pay == 'daily':
        result = hour_lab * (version.wage / version.resource_calendar_id.hours_per_day)
    elif version.schedule_pay == 'weekly':
        # Pago semanal: sueldo semanal / horas semanales del calendario (ej. 48h)
        horas_semanales = version.resource_calendar_id.full_time_required_hours or 48.0
        tarifa_hora = version.wage / horas_semanales
        result = hour_lab * tarifa_hora
    else:
        # Para otras frecuencias, dejamos el cálculo estándar
        result =  round(hour_lab * (version.wage / 30.0 / 8.0),2)
# ----------------------------------------------------------
# CÁLCULO PARA CONTRATOS CON SALARIO FIJO
# ----------------------------------------------------------
else:
    # Suma de TODOS los días reportados
    total_dias = (
        worked_days.get('DLAB', 0).number_of_days +    # Días laborales normales
        worked_days.get('DOM', 0).number_of_days +     # Días dominicales trabajados
        worked_days.get('FAL', 0).number_of_days +     # Faltas
        worked_days.get('DVAC', 0).number_of_days +    # Vacaciones
        worked_days.get('DMED', 0).number_of_days +    # Licencias médicas
        worked_days.get('DPAT', 0).number_of_days +    # Días paternales
        worked_days.get('LCGH', 0).number_of_days +    # Licencias con goce de haber
        worked_days.get('LSGH', 0).number_of_days +    # Licencias sin goce de haber
        worked_days.get('SMAR', 0).number_of_days +    # Suspensiones
        worked_days.get('SENF', 0).number_of_days      # Días especiales
    )

    # Valor diario fijo sobre 30 días
    diaria = version.wage / 30

    # Días que deben descontarse del básico porque se pagan en reglas aparte
    dias_descuento = (
        worked_days.get('DVAC', 0).number_of_days +    # Vacaciones
        worked_days.get('DMED', 0).number_of_days +    # Licencias médicas
        worked_days.get('DPAT', 0).number_of_days +    # Paternidad
        worked_days.get('LCGH', 0).number_of_days +    # Licencias con goce
        worked_days.get('LSGH', 0).number_of_days +    # Licencias sin goce
        worked_days.get('SMAR', 0).number_of_days +    # Suspensiones
        worked_days.get('SENF', 0).number_of_days      # Días especiales
    )

    # Días que sí corresponden al básico = 30 - descuentos (sin restar faltas)
    dias_basico = 30 - dias_descuento

    # Resultado final: sueldo básico proporcional
    result = dias_basico * diaria
```

### COMFI — AFP Comisión Sobre Flujo

**BASE (migrada v19):**

```python
if version.l10n_pe_commission_type == 'flow':
    if payslip.membership_id.name == 'ONP':
        result = 0
    elif payslip.membership_id.name == 'AFP HABITAT':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP INTEGRA':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP PRIMA':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP PROFUTURO':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    else:
        result = 0
else:
    result = 0
```

**BASE MG (cliente, saneada):**

```python
if version.l10n_pe_commission_type == 'flow':
	if payslip.membership_id.name == 'ONP':
		result = 0
	elif payslip.membership_id.name == 'AFP HABITAT':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'AFP INTEGRA':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'AFP PRIMA':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'AFP PROFUTURO':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'JUB PROFUT TRANSITO':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'SIN REGIMEN':
		result = 0
else:
	result = 0
```

### COMMIX — AFP Comisión Mixta

**BASE (migrada v19):**

```python
if version.l10n_pe_commission_type == 'mixed':
    if payslip.membership_id.name == 'ONP':
        result = 0
    elif payslip.membership_id.name == 'AFP HABITAT':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP INTEGRA':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP PRIMA':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'AFP PROFUTURO':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':
        result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
    else:
        result = 0
else:
    result = 0
```

**BASE MG (cliente, saneada):**

```python
if version.l10n_pe_commission_type == 'mixed':
	if payslip.membership_id.name == 'ONP':
		result = 0
	elif payslip.membership_id.name == 'AFP HABITAT':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'AFP INTEGRA':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'AFP PRIMA':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'AFP PROFUTURO':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'JUB PROFUT TRANSITO':
		result = round((payslip.l10n_pe_commission/100) * AAFP, 2)
	elif payslip.membership_id.name == 'SIN REGIMEN':
		result = 0
else:
	result = 0
```

### CTS_TRU — CTS Trunca

**BASE (migrada v19):**

```python
result = inputs['CTS_TRU'].amount if inputs['CTS_TRU'] else 0
```

**BASE MG (cliente, saneada):**

```python
total_dias = (
    worked_days.get('DLAB').number_of_days if worked_days.get('DLAB') else 0.0
)

# Lista de regímenes a los que aplica el cálculo
regimenes_validos = ['construccion']

if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() in regimenes_validos:
    result = round(BAS * 0.15, 2)
else:
    result = inputs['CTS_TRU'].amount if inputs.get('CTS_TRU') else 0
```

### ESSALUD — EsSalud

**BASE (migrada v19):**

```python
if version.l10n_pe_labor_regime not in ('fourth-fifth', 'practicante'):
    if version.social_insurance_id.name == 'EPS':
        result = AESSALUD * version.social_insurance_id.percent/100
    else:
        if AESSALUD > payslip.rmv:
            result = AESSALUD * 0.09
        else:
            result = payslip.rmv * 0.09
else:
    result = 0
```

**BASE MG (cliente, saneada):**

```python
# Si el régimen laboral no es 'construccion civil'
if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() not in ('construccion',):
    if version.l10n_pe_labor_regime not in ('fourth-fifth', 'practicante'):
        if version.social_insurance_id.name == 'EPS':
            result = AESSALUD * version.social_insurance_id.percent / 100
        else:
            if AESSALUD > payslip.rmv:
                result = AESSALUD * 0.09
            else:
                result = payslip.rmv * 0.09
    else:
        result = 0
else:
    # Si el régimen laboral es construcción civil
    result = (BAS + DOM + HE100 + VATRU + BUC + BONIFC) * 0.09
```

### GRA_TRU — Gratificación Trunca

**BASE (migrada v19):**

```python
result = inputs['GRA_TRU'].amount if inputs['GRA_TRU'] else 0
```

**BASE MG (cliente, saneada):**

```python
# Numero de horas a considerar
Jornal = 40

# Dias considerar en el calculo Agosto-Diciembre
Total_dias_grati = 150

# Haber diario
sueldo_diario = version.wage

# Días laborados
total_dias = (
    worked_days.get('DLAB').number_of_days if worked_days.get('DLAB') else 0.0
)

# Horas Laboradas
def normalizar_horas(horas):
    if not horas:
        return 0.0

    # Si viene como string "39:30"
    if isinstance(horas, str) and ":" in horas:
        h, m = horas.split(":")
        return int(h) + int(m) / 60.0

    # Si viene como número decimal (ejemplo 39.50) => ya está en base 60
    if isinstance(horas, (int, float)):
        return float(horas)

    return 0.0


if version.wage_type == 'hourly':
    # Sumar horas normalizadas de cada tipo de día
    dlab = normalizar_horas(worked_days.get('DLAB').number_of_hours if worked_days.get('DLAB') else 0.0)
    dom  = normalizar_horas(worked_days.get('DOM').number_of_hours if worked_days.get('DOM') else 0.0)

    hour_lab = dlab + dom


# Lista de regímenes válidos
regimenes_validos = ['construccion']

if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() in regimenes_validos:
    # Cálculo especial para Construcción Civil
    result = round(((Jornal * sueldo_diario) * (total_dias + (hour_lab / 48))) / Total_dias_grati, 2)
else:
    # Caso general
    result = inputs['GRA_TRU'].amount if inputs.get('GRA_TRU') else 0
```

### HE100 — Horas extras 100%

**BASE (migrada v19):**

```python
result = (((version.wage+AF)/30/8) * (1+100/100)) * worked_days['HE100'].number_of_hours
```

**BASE MG (cliente, saneada):**

```python
result = (((version.wage+AF)/30/8) * (1+worked_days['HE100'].rate/100)) * worked_days['HE100'].number_of_hours
```

### HE25 — Horas extras 25%

**BASE (migrada v19):**

```python
result = (((version.wage+AF)/30/8) * (1+25/100)) * worked_days['HE25'].number_of_hours
```

**BASE MG (cliente, saneada):**

```python
result = (((version.wage+AF)/30/8) * (1+worked_days['HE25'].rate/100)) * worked_days['HE25'].number_of_hours
```

### HE35 — Horas extras 35%

**BASE (migrada v19):**

```python
result = (((version.wage+AF)/30/8) * (1+35/100)) * worked_days['HE35'].number_of_hours
```

**BASE MG (cliente, saneada):**

```python
result = (((version.wage+AF)/30/8) * (1+worked_days['HE35'].rate/100)) * worked_days['HE35'].number_of_hours
```

### NETREMU — Neto Remuneraciones

**BASE (migrada v19):**

```python
net_rem = TINGR-TDESN-VAC-VATRU-GRA_TRU-BON9_TRU-CTS_TRU-((TAT-QUINTA) * REMAFE)-QUINTA+ADE_VAC
if net_rem < 0:
    result = 0
else:
    result = net_rem
```

**BASE MG (cliente, saneada):**

```python
result = NETO-GRA_TRU-BON9_TRU-CTS_TRU
```

### ONP — ONP

**BASE (migrada v19):**

```python
if payslip.membership_id.name == 'ONP':
    result = round((payslip.l10n_pe_retirement_fund/100) * AONP, 2)
else:
    result = 0
```

**BASE MG (cliente, saneada):**

```python
# Lista de regímenes excluidos
regimenes_excluidos = ['construccion']

# Verificar si el régimen laboral NO está en la lista de excluidos
if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() not in regimenes_excluidos:
    if payslip.membership_id.name == 'ONP':
        result = round((payslip.l10n_pe_retirement_fund / 100) * AONP, 2)
    else:
        # El empleado no es ONP, por lo tanto no se aplica esta regla
        result = 0
else:
    # El régimen laboral ES 'construccion civil'
    if payslip.membership_id.name == 'ONP':
        # Esta es la parte del cálculo especial para Construcción Civil
        result = (BAS + DOM + HE100 + VATRU + BUC + BONIFC) * 0.13
    else:
        # Si es construcción civil pero no ONP
        result = 0
```

### SEGI — AFP Prima de Seguros

**BASE (migrada v19):**

```python
if version.l10n_pe_is_older:
    result = 0
else:
    if payslip.membership_id.name == 'ONP':
        result = 0
    elif payslip.membership_id.name in ('AFP HABITAT', 'AFP INTEGRA', 'AFP PRIMA', 'AFP PROFUTURO'):
        if AAFP < payslip.l10n_pe_insurable_remuneration:
            result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)
        else:
            result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)
    elif payslip.membership_id.name == 'JUB. PROFUTURO TRÁNSITO':
        result = 0
    else:
        result = 0
```

**BASE MG (cliente, saneada):**

```python
# Regímenes con cálculo distinto de AFP
regimenes_excluidos = ['construccion']

# Verificar si el régimen laboral no está en la lista de excluidos
if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() not in regimenes_excluidos:
    if version.l10n_pe_is_older:
        result = 0
    else:
        if payslip.membership_id.name == 'ONP':
            result = 0
        elif payslip.membership_id.name == 'AFP HABITAT':
            if AAFP < payslip.l10n_pe_insurable_remuneration:
                result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)
            else:
                result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)
        elif payslip.membership_id.name == 'AFP INTEGRA':
            if AAFP < payslip.l10n_pe_insurable_remuneration:
                result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)
            else:
                result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)
        elif payslip.membership_id.name == 'AFP PRIMA':
            if AAFP < payslip.l10n_pe_insurable_remuneration:
                result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)
            else:
                result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)
        elif payslip.membership_id.name == 'AFP PROFUTURO':
            if AAFP < payslip.l10n_pe_insurable_remuneration:
                result = round((payslip.l10n_pe_prima_insurance/100) * AAFP, 2)
            else:
                result = round((payslip.l10n_pe_prima_insurance/100) * payslip.l10n_pe_insurable_remuneration, 2)
        elif payslip.membership_id.name == 'JUB PROFUT TRANSITO':
            result = 0
        elif payslip.membership_id.name == 'SIN REGIMEN':
            result = 0
else:
    # Si el régimen laboral es 'construccion civil' se calcula así
    if payslip.membership_id.name == 'ONP':
        result = 0
    else:
        result = (BAS + DOM + HE100 + VATRU + BUC + BONIFC) * 0.0137
```

### TAT — Total Aportes Trabajador

**BASE (migrada v19):**

```python
result = ONP+A_JUB+COMFI+COMMIX+SEGI+QUINTA
```

**BASE MG (cliente, saneada):**

```python
result = ONP+A_JUB+COMFI+COMMIX+SEGI+QUINTA+CONAFOV
```

### TDES — Total descuentos

**BASE (migrada v19):**

```python
result = TAT + TDESN
```

**BASE MG (cliente, saneada):**

```python
result = TAT + TDESN + OTRDSC
```

### TINGR — Total Ingresos

**BASE (migrada v19):**

```python
result = BAS_M+AF+TOT_EXT+BONR+BONI_EX+SMAR+SENF+COMP_VAC+VAC+VATRU+GRA+GRA_TRU+BON9+BON9_TRU+CTS+CTS_TRU+COMI+UTIL
```

**BASE MG (cliente, saneada):**

```python
result = BAS_M+AF+TOT_EXT+BONR+BONI_EX+SMAR+SENF+COMP_VAC+VAC+VATRU+GRA+GRA_TRU+BON9+BON9_TRU+CTS+CTS_TRU+COMI+UTIL+ESC+MOV+DOM+BUC+BONIFC
```

### VATRU — Vacaciones Truncas

**BASE (migrada v19):**

```python
result = inputs['VAC_TRU'].amount if inputs['VAC_TRU'] else 0
```

**BASE MG (cliente, saneada):**

```python
# Días laborados
total_dias = (
    worked_days.get('DLAB').number_of_days if worked_days.get('DLAB') else 0.0
)

# Lista de regímenes válidos
regimenes_validos = ['construccion']

if version.l10n_pe_labor_regime and version.l10n_pe_labor_regime.strip().lower() in regimenes_validos:
    # Cálculo especial para Construcción Civil
    result = round(BAS * 0.10, 2)
else:
    # Caso general
    result = inputs['VAC_TRU'].amount if inputs.get('VAC_TRU') else 0
```
