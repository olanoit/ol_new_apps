Historial de cambios — Perú - SIRE (RVIE / RCE)
===============================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_l10n_pe_sire.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 5.20260803 — 27/09/2026

- Las credenciales de la API SIRE (usuario y clave SOL, client ID y secret) y el token solo los ven y editan los administradores; antes cualquier usuario interno podía leerlos.
- Solo los usuarios contables pueden solicitar, aceptar o reemplazar la propuesta y registrar el preliminar; un usuario de solo lectura ya no puede enviar nada a SUNAT.
- Cada compañía ve únicamente sus periodos RVIE y RCE.
- El TXT de la propuesta cargado a mano se lee aunque SUNAT lo entregue con tildes en latin-1.
- Las líneas del sistema usan el RUC y la razón social de la empresa aunque la factura esté a nombre de una persona de contacto.
- No se informan los borradores cancelados que nunca se emitieron ni los diarios excluidos de los libros electrónicos.
- Las notas de débito de compra arrastran el comprobante que modifican, y en ventas el IVAP va a sus propias columnas.
- Mensajes claros cuando SUNAT responde algo que no es JSON; la carga del reemplazo nunca envía el token fuera de sunat.gob.pe.
- Un periodo por libro, compañía y mes garantizado también en la base de datos.

## 14/09/2026

- Menú SIRE ordenado en la app Perú y campos de comparación en Configuración ▸ Tributos SUNAT.

## 3.20260803 — 03/08/2026

- Envío a SUNAT por API: aceptar propuesta, enviar reemplazo, consultar envío y registrar preliminar.
- Resumen de la comparación en el periodo y aviso de CAR repetido.
- Comparación más rápida en periodos con miles de comprobantes.

## 2.20260719 — 19/07/2026

- Etiquetas en español en nombres, estados y campos de comparación.
- Sección propia en Ajustes ▸ Perú.

## 1.20260719 — 19/07/2026

- Propuesta RVIE y RCE por API o carga manual, comparación por CAR, XLSX y TXT de reemplazo.
