# Plan de implementación — suite de farmacias y boticas (`al_pharmacy_*`)

> Administración completa de una farmacia o botica sobre Odoo 19: un núcleo
> **general** (sirve en cualquier país) y una capa **localizada para Perú**
> (DIGEMID, Observatorio de precios, controlados, Ley 32033, SUNAT).
> Fecha: 2026-10-18 · Branch: `19.0` · Investigación previa:
> [`INVESTIGACION.md`](INVESTIGACION.md).

Marcas: **[Verificado]** en el código 19.0 · **[Propuesta]** ·
**[Por validar]** con Vicente o con un Q.F. · **[VERIFICAR]** en la norma.

---

## 0. Resumen

- **Por qué:** ningún módulo de Odoo Apps cubre la normativa peruana, y el
  software local (FarmaTec, Farmasis, InfoFarma…) no tiene contabilidad,
  compras ni multicompañía de nivel ERP. La suite ya tiene casi todo lo
  transversal: comprobantes en el TPV, Yape/Plin, cliente por RUC/DNI,
  kárdex SUNAT, libro de reclamaciones, tienda web con pagos y el paquete
  `al_industry_pharmacy`.
- **Qué falta:** el maestro farmacéutico, la venta fraccionada con precio por
  presentación, la receta y la dispensación, las buenas prácticas de
  almacenamiento, los controlados y los reportes a DIGEMID.
- **Cómo:** 6 módulos nuevos (4 generales y 2 de Perú) en un prototipo y 4
  entregas (≈ 46–55 días de desarrollo), más 3 módulos opcionales. El
  paquete `al_industry_pharmacy` pasa a instalarlos.

## 1. Lo que ya existe y se reutiliza

| Necesidad | Pieza | Estado |
|---|---|---|
| Lotes, vencimiento, fechas de alerta y de retiro, FEFO | `product_expiry` (CE): `expiration_time`, `alert_time`, `removal_time`; `product.removal` FEFO | [Verificado] |
| Venta con lote en el TPV | `pos.pack.operation.lot` (CE) | [Verificado] |
| Presentaciones con código de barras | `product.template.uom_ids` («Packagings») y `uom.uom.relative_factor` | [Verificado] |
| Cajero identificado (Q.F. o técnico) | `pos_hr` | [Verificado] |
| Fidelización y cupones en el TPV | `pos_loyalty` | [Verificado] |
| Boleta y factura en el TPV, cliente por RUC/DNI, Yape/Plin, tema | `al_l10n_pe_edi_pos`, `al_pos_pe_partner_lookup`, `al_pos_pe_wallet_qr`, `al_pos_theme` | en la suite |
| Kárdex SUNAT, libro de reclamaciones, tienda web y pagos | `ol_stock_kardex_pe`, `al_l10n_pe_complaints_book`, `al_website_sale_pe`, `al_payment_*` | en la suite |
| Datos DIGEMID básicos del producto | `al_industry_pharmacy` (5 campos `pharmacy_*` en `product.template`) | v2, se trasladan al núcleo |
| Controles de calidad, firma, documentos, citas | `quality_control`, `sign`, `documents`, `appointment` | solo Enterprise: opcionales |

**Límite verificado que condiciona el diseño:** en el TPV de Odoo 19 la línea
siempre va en la unidad del producto
(`pos.order.line.product_uom_id = related('product_id.uom_id')`) y las
listas de precios no distinguen la unidad. Escanear el código de una caja suma
sus unidades, pero **no hay precio propio por presentación** → lo resuelve
`al_pharmacy_pos` (riesgo R1).

## 2. Arquitectura de módulos

Carpeta: **área nueva `OL-HEALTH/`** (decidido el 18/10/2026), pensada para
farmacia y, más adelante, clínica u óptica. Se registra en `scripts/areas.py`,
el `addons_path` (local, servidores y documentación de instalación) y
`mkdocs/scripts/gen_pages.py`; `category` = `OL-HEALTH/Apps`. El paquete
`al_industry_pharmacy` sigue en `OL-INDUSTRIES/`.

```text
                       al_industry_pharmacy  (paquete: instala y configura)
                                 │
   ┌──────────── general ────────┼──────────── Perú ─────────────┐
   │                             │                               │
al_pharmacy_pos ──┐      al_pharmacy_stock          al_l10n_pe_pharmacy_digemid
   │              │              │                               │
   └── al_pharmacy_prescription ─┤              al_l10n_pe_pharmacy_controlled
                                 │                               │
                         al_pharmacy_base ◄──────────────────────┘
```

| Módulo | Capa | Depende de | Licencia |
|---|---|---|---|
| `al_pharmacy_base` | general | `product`, `stock`, `product_expiry`, `mail` | OPL-1 |
| `al_pharmacy_stock` | general | `al_pharmacy_base`, `purchase_stock` | OPL-1 |
| `al_pharmacy_prescription` | general | `al_pharmacy_base`, `sale_stock` | OPL-1 |
| `al_pharmacy_pos` | general | `al_pharmacy_prescription`, `al_pharmacy_stock`, `point_of_sale`, `pos_hr` | OPL-1 |
| `al_l10n_pe_pharmacy_controlled` | Perú | `al_pharmacy_prescription`, `al_pharmacy_stock`, `l10n_pe` | OPL-1 |
| `al_l10n_pe_pharmacy_digemid` | Perú | `al_pharmacy_base`, `l10n_pe`, `al_account_base` | OPL-1 |
| `al_industry_pharmacy` (v3) | paquete | los anteriores + los actuales | OPL-1 |
| *Opcionales:* `al_pharmacy_website`, `al_pharmacy_care`, `al_pharmacy_insurance` | general | ver §8 | OPL-1 |

Reglas del proyecto que aplican a todos: multicompañía (`company_id`,
`check_company`, reglas), compañía de solo lectura, `ir.model.access.csv` por
modelo, vistas `<list>`, `models.Constraint`, `group_ids` y
`res.groups.privilege`, interfaz en español con solo la primera mayúscula,
ficha en `docs/fichas/`, página en `mkdocs/content/industries/` y
`application: False` (la aplicación visible es el paquete).

## 3. `al_pharmacy_base` — maestro farmacéutico y gobierno del establecimiento

**Modelos y campos [Propuesta]**

| Elemento | Detalle |
|---|---|
| `pharmacy.ingredient` | Principio activo (DCI): nombre, código ATC opcional, sinónimos. Global. |
| `pharmacy.dosage.form`, `pharmacy.route` | Catálogos de forma farmacéutica (tableta, jarabe…) y vía. Datos semilla. |
| `pharmacy.product.ingredient` | Línea producto ↔ DCI con concentración (valor + unidad: mg, mL, UI, %). Admite combinaciones. |
| `product.template` | `pharmacy_ok`; DCI (líneas); forma, vía; **condición de venta** (`otc` / `prescription` / `special_prescription`); registro sanitario (número, titular, **fecha de vencimiento**); laboratorio (`res.partner`); tipo (`generic_dci` / `generic_brand` / `innovator`); empresa vinculada; cadena de frío y condiciones de almacenamiento; ficha clínica (indicaciones, contraindicaciones, efectos adversos); **ubicación en estante**. |
| Equivalentes | `pharmacy_equivalence_key` calculada (DCI + concentración + forma, ordenada) y `pharmacy_equivalent_ids`: base de las alternativas en TPV y web. |
| Turnos de Q.F. | `pharmacy.shift`: Q.F. (empleado con colegiatura COP), local, inicio/fin, director técnico o reemplazo. `res.company` / `stock.warehouse`: director técnico. |
| Libro de ocurrencias | `pharmacy.logbook.entry` solo-ampliable: correlativo por local, fecha, usuario, tipo (rotación, ausencia, SRA, incidente, otro). Corrección = asiento nuevo que referencia al anterior; sin `write`/`unlink` (restricción + regla). |
| Grupos | `res.groups.privilege` «Farmacia»: técnico en farmacia, químico farmacéutico, director técnico, administrador. |

**Migración:** los 5 campos `pharmacy_*` de `al_industry_pharmacy` se
declaran en el núcleo **con el mismo nombre** y desaparecen del paquete
(la columna se conserva). `pharmacy_concentration` y `pharmacy_active_ingredient`
(texto) se convierten en líneas DCI con un `post-migrate` que crea los
principios activos por nombre. **[Por validar]** con datos reales.

**Pruebas:** equivalencias (mismo DCI, distinta concentración ≠ equivalente);
libro inmodificable; reglas multicompañía; migración desde v2.

## 4. `al_pharmacy_stock` — buenas prácticas de almacenamiento

| Función | Detalle [Propuesta] |
|---|---|
| Recepción BPA | En recepciones de productos farmacéuticos: lote, vencimiento y RS obligatorios; casilla «envase conforme» y observación; si no conforme → ubicación de **cuarentena**. Bloqueo si el RS está vencido. |
| Estado del lote | `stock.lot.pharmacy_state`: disponible / cuarentena / bloqueado / vencido (cron diario). Los no disponibles no se reservan ni se venden (dominio de reserva + filtro en TPV). |
| Alertas de vencimiento | Tablero y actividad a 90/60/30 días (configurable por compañía); usa `alert_time` de `product_expiry`. |
| Devoluciones y bajas | Ubicaciones de devoluciones y de bajas por almacén; motivo obligatorio; reingreso solo con verificación del Q.F.; **acta de baja y destrucción** (PDF con `al_report_base`). |
| Devolución al proveedor | Por vencimiento o canje, con nota de crédito esperada y seguimiento. |
| Bonificaciones de compra | Línea de OC «bonificación» (p. ej. 12+1): cantidad sin costo que **prorratea** el costo del lote. **[Por validar]** el tratamiento contable con el contador. |
| Registro ambiental | `pharmacy.environment.reading`: equipo/ubicación, temperatura, humedad, fecha-hora, responsable; rangos por ubicación (ambiente 15–30 °C, refrigeración 2–8 °C); fuera de rango → acción correctiva obligatoria y aviso; cron que recuerda las lecturas del día. Entrada manual (sensores IoT en una fase posterior). |
| Equipos | Termohigrómetros y refrigeradoras con calibración y mantenimiento (fecha y certificado). |
| Inventario anual | Recordatorio y reporte de conteo (inventario físico nativo). |
| Recall | `pharmacy.alert` (número, fecha, origen —DIGEMID u otro—, productos, lotes, RS): al confirmar bloquea los lotes, lista el stock afectado por almacén y **los clientes que los compraron**. |

## 5. `al_pharmacy_prescription` — receta, paciente y dispensación

| Elemento | Detalle [Propuesta] |
|---|---|
| Prescriptor | `res.partner` con `pharmacy_prescriber`, profesión (médico, odontólogo, obstetra), colegiatura (CMP/COP/COP…), especialidad. |
| Paciente | `res.partner` con fecha de nacimiento, alergias (DCI), condiciones crónicas. Datos sensibles: grupo restringido (Ley 29733). |
| Receta | `pharmacy.prescription`: número, tipo (común / especial), prescriptor, establecimiento de salud, paciente, fecha, **vigencia**, diagnóstico (opcional), imagen o PDF, líneas (DCI o producto, concentración, forma, cantidad, posología, duración); estados borrador → validada → dispensada parcial → dispensada / vencida / anulada. |
| Dispensación | Línea de receta ↔ líneas de venta (TPV o pedido); cantidad dispensada y saldo; **alternativa entregada** (producto, laboratorio, Q.F.) registrada como pide BPOF 7.5.2.28; retención (folio). |
| Reglas | Producto con receta → exige receta válida (configurable: avisar o bloquear); receta vencida → bloqueo; alergia del paciente a un DCI → aviso. |
| Libro de recetas | Vista y PDF correlativo por local (preparados y recetas retenidas). |
| Etiqueta | Etiqueta de dispensación / fraccionado (producto, laboratorio, concentración, vía, lote, vencimiento, establecimiento) — BPOF 7.5.2.19. |

## 6. `al_pharmacy_pos` — punto de venta

| Función | Detalle [Propuesta] |
|---|---|
| Búsqueda | Por nombre, DCI, laboratorio o código; distintivos Rx, controlado, cadena de frío, por vencer. |
| **Alternativas** | Al elegir un producto de marca: ventana con los equivalentes **genéricos DCI primero, ordenados por precio**, con stock (Ley 32033). Reemplazar en un clic. |
| **Venta fraccionada** | Selector de presentación (unidad / blíster / caja) con **precio propio por presentación**; la línea guarda la presentación y el número de presentaciones; el stock se descuenta en unidades. Ver R1. |
| Lotes | Lote obligatorio en productos con lote, sugerido por FEFO; lotes no disponibles (§4) ocultos; lectura GS1 (01/10/17). |
| Receta en caja | Capturar o buscar la receta del paciente; validar vigencia; dispensación parcial; bloqueo o aviso según condición de venta. |
| Q.F. en turno | Productos con receta solo si el cajero (pos_hr) o el supervisor es Q.F. **[VERIFICAR]** si bloquear o avisar. |
| Comprobante | Paciente, prescriptor y lote/vencimiento en el ticket (sobre el formato de `al_l10n_pe_edi_pos`); etiqueta del fraccionado. |
| Sin conexión | Datos de equivalencias y presentaciones cargados con `_load_pos_data_fields` / `_load_pos_data_read`; la receta se sincroniza al reconectar. |

## 7. Capa Perú

### 7.1 `al_l10n_pe_pharmacy_controlled` — estupefacientes y psicotrópicos

| Función | Detalle [Propuesta] |
|---|---|
| Fiscalización | Lista por producto/DCI: IIA, IIB, IIIA, IIIB, IIIC, IVA, IVB, VI, cannabis. |
| Receta especial | Validación de los datos del art. 23 (paciente con DNI, dirección, teléfono, diagnóstico; DCI; cantidad en número y letra; posología; prescriptor) y **vigencia de 3 días**; datos del adquiriente al atender; folio de retención. Bloqueo si falta algo. |
| Receta retenida | Listas IIB, IVA, IVB y VI: retención con folio. |
| Libros | Libro de estupefacientes y de psicotrópicos automáticos por DCI y local (movimientos con saldo), solo-ampliables. |
| Balance trimestral | Saldo inicial, entradas, salidas y saldo final por DCI con recetas foliadas y documentos de ingreso; formato de declaración jurada (XLSX y PDF); recordatorio del plazo [VERIFICAR art. 50]; saldos descartables (D7). |
| Canales | Prohibidos en delivery y web (§8). Cannabis: verificación en RENPUC (registro manual del número). |
| Doble verificación | Opcional: segundo Q.F. confirma la dispensación. |

### 7.2 `al_l10n_pe_pharmacy_digemid` — DIGEMID, genéricos y SUNAT

| Función | Detalle [Propuesta] |
|---|---|
| Catálogo | Código de producto DIGEMID (Observatorio) en el producto; importación del catálogo (CSV/XLSX) **[VERIFICAR]** si DIGEMID publica uno descargable. |
| Observatorio | Historial de precios por local; cambio de precio o alta → «pendiente de informar»; exportación con la **plantilla oficial vigente** (DIGEMID rechaza otra estructura, RD DFAU 018-2021) [VERIFICAR periodicidad y plantilla]; tablero de cumplimiento. |
| Genéricos 30 % | Importación del listado MINSA (RM 220-2024 [VERIFICAR actualización]); relación marca → genérico; reporte por ítem del cumplimiento y alerta; excepción de microempresa (ajuste de la compañía). |
| Precios visibles | Lista de precios por DCI, de menor a mayor (PDF y pantalla); aviso A4 de empresas vinculadas. |
| Farmacovigilancia | `pharmacy.adverse.event` con los campos de NotiMED, correlativo, gravedad y **plazo** (24 h graves; 15 días u 72 h [VERIFICAR]); asiento automático en el libro de ocurrencias. |
| Alertas | Importación manual de alertas DIGEMID al `pharmacy.alert` de §4. |
| IGV | Marca de inafecto/exonerado por producto con la norma (Ley 27450, Ley 28553) y el impuesto correcto en la línea del CPE; datos semilla de las listas [VERIFICAR vigentes]. |
| Establecimiento | Código de establecimiento, categoría (farmacia/botica), autorización sanitaria y su vencimiento, certificación BPOF. |

## 8. Opcionales (después de la entrega 4)

| Módulo | Contenido |
|---|---|
| `al_pharmacy_website` | Tienda: alternativas DCI también en la web; subir la receta y que un Q.F. la valide antes de despachar; bloqueo de controlados; hoja de reparto con conformidad y cadena de frío (BPOF 7.5.5). |
| `al_pharmacy_care` | Seguimiento farmacoterapéutico (consentimiento, historia, PRM e intervención; opcional en BPOF 7.5.4); interacciones medicamentosas con severidad (base de datos propia, **sin** copiar bases con licencia); recordatorio de recompra. |
| `al_pharmacy_insurance` | Convenios con empresas, EPS y seguros: lista de precios, cobertura %, copago y topes; cuenta por cobrar a la aseguradora. |

## 9. Entregas y estimación

| Entrega | Contenido | Días |
|---|---|---|
| **E0 — Prototipo (spike)** | R1: venta por presentación en el TPV con precio propio, lote y CPE (boleta); decide el diseño antes de seguir. | 3–4 |
| **E1 — Núcleo** | `al_pharmacy_base` + migración de `al_industry_pharmacy`; `al_pharmacy_stock` (recepción, estados de lote, vencimientos, bajas, registro ambiental, recall). | 12–14 |
| **E2 — Venta** | `al_pharmacy_prescription` + `al_pharmacy_pos` (alternativas, fraccionado, lotes, receta, Q.F., etiquetas). | 14–16 |
| **E3 — Perú** | `al_l10n_pe_pharmacy_controlled` + `al_l10n_pe_pharmacy_digemid`. | 12–15 |
| **E4 — Paquete y salida** | `al_industry_pharmacy` v3, datos demo de una botica completa, fichas, documentación en `industries/`, guion de prueba funcional, despliegue. | 5–6 |
| **Total** | | **≈ 46–55** (+ opcionales) |

Cada entrega: pruebas `TransactionCase` (y `HttpCase` del TPV) en
`test_pe_pharmacy`, `gen_addons_table.py --check`, ficha y CHANGELOG,
commit `[ADD]`/`[IMP]`, despliegue a una base de demostración.

## 10. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | **Precio por presentación en el TPV:** la línea va en la unidad base y la lista de precios no distingue unidad [Verificado]. Precios como S/ 1,00 el blíster de 7 dan un precio unitario periódico. | E0 primero. Opción A: la línea guarda presentación y cantidad de presentaciones, `price_unit` con más decimales y subtotal fijado; Opción B: producto por presentación con desempaque automático (kit). Validar redondeo del CPE con SUNAT (`l10n_pe_edi`). |
| R2 | Plantilla y periodicidad del Observatorio sin documentación pública de API. | Exportación configurable; validar con un establecimiento real y la DIRIS. |
| R3 | Normas por confirmar ([VERIFICAR] en `INVESTIGACION.md`): plazos de SRA, art. 50 del balance, listado de genéricos 2025-2026, listas de IGV. | Parámetros en datos (no en código) y revisión con un Q.F. antes de E3. |
| R4 | Datos sensibles de pacientes (Ley 29733). | Grupo restringido, registro de accesos, consentimiento en `al_pharmacy_care`. |
| R5 | Rendimiento del TPV con 15–20 mil productos y sus equivalencias. | Clave de equivalencia indexada y carga perezosa en el TPV; prueba con el catálogo completo. |
| R6 | Interacciones: las bases de datos clínicas tienen licencia. | Fuera del alcance base; `al_pharmacy_care` con datos propios o de fuente abierta. |

## 11. Por decidir (antes de E1)

1. ~~Carpeta~~ → **decidido: área nueva `OL-HEALTH/`** (18/10/2026).
2. Recetas: ¿bloquear o solo avisar sin receta en productos `prescription`? (BPOF dice exigirla; muchas boticas avisan).
3. Q.F. en turno: ¿bloqueo o alerta?
4. Venta fraccionada: opción A o B de R1 (sale del prototipo).
5. Bonificaciones: prorrateo en el costo del lote o ingreso aparte (contador).
6. Cliente piloto y su catálogo (para el Observatorio y las pruebas de rendimiento).
7. Opcionales a incluir en la primera versión.
