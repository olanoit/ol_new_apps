# Guion de prueba F6 — `al_construction_material_request` en Odoo.sh

Rama: **ConstruccionDEV** de `vcatacora/DemoConstruccion` (desarrollo: base
nueva con datos demo en cada compilación). Submódulo `olanoit/ol_new_apps`
en `1392cc8` (commit `a9e8056` del repo del cliente, 07/10/2026).

Todo lo que lleva `[DEMO]` es ficticio: obras, materiales, costos,
existencias y el umbral de S/ 10 000.

---

## 0. La compilación

| # | Qué mirar | Esperado |
|---|---|---|
| 0.1 | Odoo.sh ▸ ConstruccionDEV ▸ última compilación | Verde. Si falla con «module not found», Odoo.sh no recorre las carpetas `OL-*/` del submódulo (ver §6) |
| 0.2 | Aplicaciones, filtro «al_» | Aparecen módulos de varias áreas (`al_l10n_pe_…`, `al_hr_pe…`), con la categoría `OL-<ÁREA>/Apps` |
| 0.3 | Aplicaciones ▸ «Requerimiento de obra» | Instalable o instalado. Instala también `base_tier_validation` (carpeta `OL-THIRD-PARTY/`) y `purchase_request` (submódulo `purchase-workflow`) |
| 0.4 | Si no estaba instalado: instalarlo | Sin errores. Aparece el menú raíz «Requerimientos de obra» |

> Los datos demo del módulo solo se cargan si el módulo se instala al crear
> la base (instalación de la compilación). Si se instala a mano después, el
> caso de §2 se arma con los pasos de §2-bis.

## 1. Configuración

| # | Paso | Esperado |
|---|---|---|
| 1.1 | Inventario ▸ Ajustes ▸ bloque «Requerimientos de obra» | Ubicación origen (existencias del almacén central), padre `OBRAS` y tipo «Despacho a obra» rellenos |
| 1.2 | Proyecto «[DEMO] Colegio A» ▸ pestaña de obra | «Es obra» marcado y ubicación `…/OBRAS/[DEMO] Colegio A` |
| 1.3 | Ajustes ▸ Usuarios: asignar al usuario de prueba los grupos Solicitante, Aprobador y Logística (privilegio «Requerimientos de obra») | |

## 2. Caso de aceptación: 100 bolsas pedidas, 60 en almacén

Requerimiento demo «[DEMO] Vaciado de zapatas del bloque A», obra
«[DEMO] Colegio A», 100 bolsas de «[DEMO] Cemento Portland tipo I».

| # | Paso | Esperado |
|---|---|---|
| 2.1 | Abrir el requerimiento | Línea con 100 bolsas; «Disponible en central» = 60 |
| 2.2 | «Solicitar aprobación» | Estado «En aprobación»; revisión de nivel 1 pendiente para el jefe de proyecto |
| 2.3 | Como jefe de proyecto: «Validar» (pide comentario) | Estado «Aprobado». El nivel 2 no aplica (importe < S/ 10 000) |
| 2.4 | Como Logística: «Procesar» | Estado «En proceso». Botones: 1 transferencia, 1 solicitud de compra |
| 2.5 | Transferencia «Despacho a obra» | 60 bolsas reservadas, origen central, destino la ubicación de la obra, proyecto rellenado, motivo GRE `04` si está la localización |
| 2.6 | Solicitud de compra | Aprobada, 40 bolsas, enlazada al requerimiento |
| 2.7 | Validar la transferencia | Línea del requerimiento: despachado 60, recibido en obra 60, situación «Parcial» |
| 2.8 | Compras: desde la solicitud, «Crear RFQ», confirmar la OC y recibir | Si la línea es «vía central»: entra al central y aparece una segunda transferencia central → obra por 40. Si es «directo a obra»: la recepción va a la ubicación de la obra |
| 2.9 | Validar la última transferencia (vía central) | Recibido en obra 100; requerimiento en «Hecho» |
| 2.10 | «Imprimir vale» | PDF A4 con materiales, aprobaciones, documentos y cuatro firmas, con estilos |

### 2-bis. Si no hay datos demo

1. Inventario: producto almacenable «Cemento», 60 unidades en el central.
2. Proyecto «Obra prueba», marcar «Es obra».
3. Requerimiento con 100 de cemento y seguir desde 2.2. Sin reglas de
   aprobación activas, «Solicitar aprobación» aprueba directamente.

## 3. Aprobación de dos niveles

| # | Paso | Esperado |
|---|---|---|
| 3.1 | Requerimiento con 400 bolsas (400 × 30 = S/ 12 000) | Dos revisiones al solicitar |
| 3.2 | Validar nivel 1 | Sigue «En aprobación»; ahora puede revisar Gerencia de operaciones |
| 3.3 | Rechazar en nivel 2 y luego «Volver a borrador» | Estado «Rechazado» → «Borrador», revisiones borradas |

## 4. Permisos

| # | Usuario | Esperado |
|---|---|---|
| 4.1 | Solicitante sin acceso a Inventario | Crea y ve los requerimientos de sus obras; ve «Disponible en central»; **no** ve «Procesar» |
| 4.2 | Aprobador | Ve además los que tiene por revisar |
| 4.3 | Otra compañía | No ve requerimientos ajenos |

## 5. Cancelación

Requerimiento procesado y sin OC: «Cancelar» → movimientos no hechos y
líneas de compra sin OC canceladas; lo ya despachado se conserva.

## 6. Si la compilación no encuentra los módulos

Odoo solo busca módulos un nivel por debajo de cada ruta. Si Odoo.sh no
añade `olanoit/ol_new_apps/OL-*` al addons path, la solución documentada es
ocultar el submódulo (carpeta con punto, p. ej. `.ol_new_apps`) y crear en
el repo del cliente una carpeta con enlaces simbólicos a los módulos que se
usan. Mientras tanto, ConstruccionDEV se devuelve a `0a3b7ff`.
