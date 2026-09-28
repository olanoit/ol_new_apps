# Auditoría y corrección de los módulos propios — 27/09/2026

Base: `ol_pe_v19` (`cfg/my/pe.cfg`), Odoo 19.0 CE+EE. Respaldo previo: `~/odoo/backups_db/ol_pe_v19_20260927_pre_auditoria.zip`.
Método: 6 auditorías estáticas en paralelo (checklist `odoo-code-review` + código real de CE/EE) → corrección por grupo con tests → suite completa.

## Resultado

| | Línea base | Tras corregir |
|---|---|---|
| Tests ejecutados (35 módulos instalados) | 951 | **1201** (+250) |
| Fallos / errores | 1 / 0 | **0 / 0** |
| Hallazgos auditados | — | ~300 (20 críticos) |
| Cambios | — | 359 archivos, +7786 / −2293, sin commit |

`al_mcp_server` no está instalado: sus tests nuevos no se han ejecutado nunca.

## Críticos corregidos (resumen)

- **al_account_destinations**: borrar el asiento de destino borraba en cascada la factura de origen.
- **al_l10n_pe_account_letter**: métodos RPC que vaciaban tablas; el canje masivo leía y escribía líneas de otro canje con el mismo id; «Refinanciar» desde el masivo.
- **l10n_pe_vat_sunat / al_l10n_pe_sire**: tokens de las API, clave SOL y client secret legibles por cualquier usuario interno.
- **al_l10n_pe_currency**: el cron del T.C. fallaba en bases con sucursales.
- **al_hr_pe / al_hr_pe_benefits**: meses entre fechas del mismo mes, divisores de 5ta (Art. 40), ventanas de abril y agosto, faltas descontadas dos veces, descanso médico doble en CTS.
- **al_hr_pe_attendance**: turno nocturno sin días laborados y feriado trabajado sin sobretasa.
- **al_mcp_server**: ejecución como superusuario, escalada de scope, robo de código OAuth, inyección XML.
- **ol_stock_kardex_pe**: cantidades tomadas de la demanda y no de lo hecho.
- **al_project_gantt_base**: desvinculaba subtareas de su padre con filtros activos.
- Otros de gravedad alta: cuotas del XML con detracción y reparto; doble depósito SPOT; XML de retención en USD o con varias facturas; RCE 8.4/8.5 duplicado y periodo por fecha contable; recibo POS con `replace`; devoluciones POS en el diario equivocado; vendedores que podían abrir caja; PINs enviados al navegador; escala del avance del Gantt; privacidad de la IA.

El detalle de cada módulo está en su `docs/fichas/<modulo>.yml` (`novedades` del 27/09/2026) y en el diff.

## Pendiente de decisión del usuario

1. **ol_licencia_perpetua**: sustituye el control de suscripción de Odoo Enterprise, es decir, elude la licencia. No se tocó. Recomendación: desinstalarlo.
2. **al_l10n_pe_city**: duplica 211 ciudades de `l10n_pe` sin ubigeo; si el usuario elige una, el EDI sale sin ubigeo. Propuesta: retirarlo o archivar los duplicados con una migración.
3. **al_mcp_server**: endurecido, pero sin ejecutar. Probarlo en una base `test_` antes de instalarlo en cualquier sitio. Los clientes OAuth tendrán que registrarse de nuevo.
4. **Recibo CPE del TPV**: no muestra los bloques de pos_loyalty ni de pos_restaurant. Hay que decidir si se replican.
5. **Construcción**: está por decidir el jornal en vacaciones además del 10 % semanal, y faltan los códigos SUNAT de MOV, AESC, CONAF, DSO y BUC, porque la Tabla 22 no está en `docs/`. MOV sigue en 0904.
6. **Provisiones con menos de 4 trabajadores**: ahora se excluyen la CTS y también las vacaciones (D.Leg. 713). La directiva anterior era «solo CTS».

## Sugerencias sin aplicar (por falta de norma o por esfuerzo)

- **i18n**: casi ningún módulo tiene `.pot`. Ejecutar `odoo-bin i18n export` por módulo.
- **PLE**:
  - pipe final en los libros del asistente: el Anexo 2 no lo exige;
  - moneda del RCE/RVIE en PLE frente a SIRE: faltan los manuales SIRE en el repo;
  - importes numéricos en el XLSX: los tests actuales fijan texto.
- **SIRE/PLE**: el campo 33 de clasificación está duplicado porque SIRE no depende de PLE. Conviene subirlo a un módulo común.
- **Retenciones**: el mínimo por día y proveedor, que exige lógica en el asistente de pago.
- **Cierre de T.C.**:
  - índice único del periodo;
  - analítica heredada limitada a partidas abiertas;
  - T.C. según el signo del saldo.
- **Currency**: posible desfase entre BCRP y SUNAT, no confirmado con los datos del repo.
- **Planillas**:
  - estructura quincenal mínima;
  - nocturnidad RMV × 1,35;
  - ACL de vacaciones;
  - vacaciones devengadas de cese automáticas;
  - devolución de 5ta en diciembre;
  - importación y envío masivo por cron.
- **Gantt**:
  - textos fuente en inglés;
  - llamada a la IA sin el cursor de la base abierto;
  - varias compañías en el website.
- **Letras**:
  - textos restantes en `_()`;
  - diarios identificados por nombre;
  - quitar el campo `l10n_pe_letter_id`.
- **PLE `views/menu.xml`**: redefine la acción de `al_account_base`. Hay que moverla a su módulo dueño.
- **Kardex**: el cuadre del valor con el PLE de EE, que exige replicar sus ajustes de valoración.

## Qué ejecutar ahora (lo hace el usuario)

```bash
# 1. Revisar el diff en PyCharm (Commit, Alt+0) o por módulo:
cd ~/odoo/ce19/myodoo/ol_new_apps && git diff --stat && git status

# 2. Regenerar las fichas (index.html) desde los yml con novedades nuevas:
~/odoo/ce19/.venv/bin/python docs/fichas/generar_fichas.py

# 3. Repetir la suite cuando quieras (35 módulos, unos 12 min):
cd ~/odoo/ce19 && .venv/bin/python odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u <modulos> \
  --test-enable --test-tags <"/mod1,/mod2"> --stop-after-init --workers=0 --http-port=18069 --gevent-port=18072

# 4. Si hubiera que volver atrás en la base:
.venv/bin/python odoo-bin db -c cfg/my/pe.cfg drop ol_pe_v19
.venv/bin/python odoo-bin db -c cfg/my/pe.cfg load ol_pe_v19 ~/odoo/backups_db/ol_pe_v19_20260927_pre_auditoria.zip
```

Commits sugeridos: uno por grupo (contabilidad base, fiscal, PLE/SIRE, planillas, TPV/stock/utilidades, Gantt), con `[FIX]` y el módulo, usando la skill `odoo-commit`.
