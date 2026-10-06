# Requerimiento de materiales de obra (AL)

El personal de obra pide materiales para su obra. El requerimiento se aprueba
por niveles (`base_tier_validation`, OCA). Logística lo procesa: lo disponible
en el almacén central sale por transferencia interna a `OBRAS/<obra>` y el
faltante pasa a requerimiento de compra (`purchase_request`, OCA).
**Plan:** [`docs/construccion/PLAN_MODULO_al_construction_material_request.md`](../../docs/construccion/PLAN_MODULO_al_construction_material_request.md).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| F2 | Modelos, seguridad, vistas, secuencia `RQO/<año>/` | hecha |
| F3 | División stock/compra, transferencias, requerimiento de compra, tests | hecha |
| F4 | Aprobación multinivel (tier validation), datos demo | hecha |
| F5 | Kanban, botones, móvil, vale PDF | pendiente |

## Procesamiento (botón «Procesar», Logística)

1. Por línea: cantidad libre (`free_qty`) en el origen y sus sububicaciones,
   en la UdM de la línea (redondeo hacia abajo). Varias líneas del mismo
   producto se reparten el stock.
2. Lo disponible sale en **una transferencia** «Despacho a obra» por
   requerimiento (proyecto, analítica en el movimiento, motivo GRE `04`),
   confirmada y reservada. Si se reserva menos de lo previsto, la
   diferencia pasa a compra y queda nota en el chatter.
3. El faltante va a **un requerimiento de compra** ya aprobado:
   - *Vía almacén central*: se crea además un movimiento central → obra en
     espera, enlazado como `move_dest_ids`; al recibir la OC reserva lo
     recibido.
   - *Directo a obra*: la línea de OC lleva `location_final_id` = obra y la
     recepción entra en la obra. El asistente no mezcla destinos en una
     misma línea de OC.
4. «Hecho» cuando todo lo pedido está en la obra. «Cancelar» anula lo
   pendiente y conserva lo despachado y lo ya pedido en OC.

## Aprobación (OCA `base_tier_validation`)

- «Solicitar aprobación» pasa a *En aprobación* y crea las revisiones de
  las reglas que apliquen (*Ajustes ▸ Técnico ▸ Tier Definition*, modelo
  «Requerimiento de materiales de obra»). Si no aplica ninguna, se aprueba
  directamente.
- Los revisores validan o rechazan desde el formulario (se puede pedir
  comentario) o con el filtro **Necesita mi revisión**. Con la última
  validación pasa a *Aprobado*; un rechazo lo deja *Rechazado* y «Volver a
  borrador» borra las revisiones.
- Durante la revisión solo se editan la ubicación de obra, la fecha
  requerida y la prioridad (las dos primeras, solo Logística).
- Los revisores deben tener al menos el grupo **Aprobador**. El grupo
  **Gerencia de operaciones** es el revisor del nivel por monto.
- Los requerimientos de compra generados nacen aprobados. No instale
  `purchase_request_tier_validation`; si se instala, sus reglas deben
  llevar el dominio `[('construction_request_id', '=', False)]`.

## Datos demo (ficticios, prefijo `[DEMO]`)

Planes analíticos Disciplina/Partida, 5 materiales (cemento, fierro, arena,
ladrillo, clavos), sububicaciones Cementos/Fierros con stock parcial (60
bolsas de cemento), obras «Colegio A» y «Posta médica B», dos reglas de
aprobación (nivel 1 jefe de proyecto; nivel 2 gerencia si el valor supera
S/ 10 000, **umbral inventado**) y un requerimiento de 100 bolsas en
borrador.

## Configuración

- **Inventario ▸ Ajustes ▸ Requerimientos de obra**: origen (existencias del
  almacén central), ubicación padre `OBRAS`, tipo «Despacho a obra» y
  recepción de compras. Al instalar se completan con el primer almacén de
  cada compañía.
- **Proyecto ▸ Ajustes ▸ Obra**: marcar «Es obra» crea `OBRAS/<proyecto>`.
- Grupos (privilegio «Requerimientos de obra»): Solicitante ⊂ Aprobador ⊂
  Logística ⊂ Administrador.

## Dependencias OCA

`purchase_request` (OCA/purchase-workflow 19.0) y `base_tier_validation`
(OCA/tier-validation 19.0, **AGPL-3**; por eso este módulo es LGPL-3).

## Limitaciones conocidas

- En 19.0 un traslado interno (central → obra) no genera asiento ni líneas
  analíticas: la analítica de la línea se guarda en el movimiento solo como
  trazabilidad hasta que se implemente el consumo en obra.

## Pruebas

```bash
./odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_construction_material_request \
  --test-enable --test-tags /al_construction_material_request --stop-after-init
```
