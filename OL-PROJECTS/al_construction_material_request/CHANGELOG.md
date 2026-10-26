Historial de cambios — Requerimiento de materiales de obra (AL)
===============================================================

Una entrada por versión publicada, la más reciente arriba; el número es
el `version` de `__manifest__.py` (`N.AAAAMMDD`).

Generado desde `docs/fichas/al_construction_material_request.yml` (sección `novedades`) con
`python3 scripts/gen_changelog.py`: no editar a mano.

## 28.20261024 — 26/10/2026

- CR-16: ajuste «Analítica en la compra para el almacén»: la línea de compra de un requerimiento abastecido desde el almacén central puede llevar la analítica de la obra o del área (apagado por defecto: la compra masiva sigue sin analítica). La línea de compra muestra las partidas de sus requerimientos.

## 27.20261024 — 25/10/2026

- Paquete 1.11, M111-22: el movimiento de una línea indivisible guarda la necesidad (el despacho, la parte que cubre; la entrega pendiente de compra, el resto) y muestra el redondeo. Sin productos indivisibles no cambia nada.
- Paquete 1.11, M111-22: el tipo del despacho y la cantidad que un movimiento entrega a su línea pasan por métodos que los puentes amplían.
- Verificación del 24-oct: «Pedir al almacén» de la línea muestra el almacén (elegir otro lleva la línea a su stock) y la ubicación queda como «Ubicación de origen»; la nota «Salió de…» usa el idioma de quien pide para la unidad y el producto.

## 26.20261024 — 24/10/2026

- Paquete 1.11, M111-20 C: el faltante de una línea que sale de otro almacén se compra con la recepción de ese almacén (un requerimiento de compra por almacén), para que lo recibido reserve la salida a obra en espera.
- Paquete 1.11, M111-20 C: los textos «En central» y «Disponible en central» pasan a «En origen» y «Disponible en origen».
- Paquete 1.11, M111-20 A: el «Solicitante interno» lee, escribe y crea requerimientos, pero no los borra.

## 25.20261024 — 24/10/2026

- Paquete 1.11, M111-19 B: el vale de despacho tiene firmas configurables (obra e interno), «Despachado por» en blanco antes de validar si se elige, y la columna «Despachado antes» opcional.
- Paquete 1.11, M111-19 C y M111-18: el requerimiento interno de quien no tiene jefe lo aprueba un grupo configurable (por defecto, Logística); vacío, se aprueba al solicitarlo.
- Paquete 1.11, M111-20 A: grupo «Solicitante interno» (por defecto, todos los usuarios internos): pide solo requerimientos internos y ve solo los suyos.
- Paquete 1.11, M111-20 C: cada línea toma su almacén de origen de la ruta nativa que abastece su destino; se despacha una transferencia por almacén con el tipo de despacho del almacén. La cabecera resume «Pedir al almacén» y el origen de siempre pasa a ser «Almacén por defecto».
- Paquete 1.11, M111-20 E: el valor estimado solo lo ve el grupo «Ve montos» (Administrador y gerencia de operaciones); el material extra pasa a la columna derecha.
- Paquete 1.11, M111-20 F: el historial dice «Reservado para despacho desde …» al procesar y agrega una nota al validar cada despacho con lo que salió y lo pendiente.

## 24.20261023 — 23/10/2026

- Corrección: procesar un requerimiento en una compañía sin plan analítico «Área» daba error de acceso a Logística. El plan de las áreas se propone solo desde «Completar configuración» de Ajustes.

## 23.20261023 — 23/10/2026

- Paquete 1.11, M111-08: menú Inventario ▸ Operaciones ▸ Traslados ▸ «Productos por despachar» para Inventario: Usuario: los productos de los despachos de requerimientos sin validar, agrupados por requerimiento y transferencia; la fila abre la transferencia y desde las filas marcadas se imprime el vale de despacho.
- Paquete 1.11, M111-10: requerimiento interno de las áreas (Administración, Comercial…): sin obra, con «Área» del plan analítico de las áreas, sale a la ubicación «Consumo interno» del almacén con el tipo «Consumo interno» (CI); el gasto y la compra del faltante llevan la analítica del área. Regla de aprobación del jefe del departamento del solicitante y menú «Requerimientos internos».
- Paquete 1.11, M111-11: la transferencia guarda «Validado por»; el vale de despacho firma con quien la validó o, si aún no se valida, con quien imprime.
- Paquete 1.11, M111-12: los tableros indivisibles se reparten en planchas enteras: se despachan solo planchas enteras libres, se compra el resto del entero y la línea muestra el «Redondeo a plancha entera». La orden de compra manual de un tablero con fracción avisa con la cantidad sugerida.

## 22.20261021 — 21/10/2026

- Paquete 1.11, M111-07: «Vale de despacho» para pegar en el bulto, desde la transferencia con requerimiento (Imprimir) o desde el requerimiento: todo el requerimiento con pedido, despachado antes, en este bulto, pendiente y situación (en compra, OC y fecha de llegada), sin precios ni stock interno.

## 21.20261018 — 18/10/2026

- Los datos de demostración usan nombres sin el prefijo «[DEMO]»; en las bases que ya los tienen se renombran al actualizar.

## 20.20261016 — 16/10/2026

- El despacho lleva un movimiento por línea: el mismo producto pedido para dos niveles ya no se junta y lo validado llega a cada línea (antes caía entero en la primera y el requerimiento no pasaba a Hecho).
- La línea muestra «Por despachar» hasta que el almacén valida la transferencia.

## 19.20261016 — 16/10/2026

- Destino por línea: el despacho y la transferencia en espera de la compra salen en una transferencia por destino (base del material de producción a la preproducción de la planta).

## 17.20261013 — 15/10/2026

- El despacho a obra de un requerimiento lo valida solo el almacén (grupo Logística), aunque quien lo pidió tenga acceso a Inventario (v1.6, M16-10).

## 16.20261013 — 15/10/2026

- Material extra (v1.6, M16-05): casilla «Material extra» con su motivo (merma, error de medida, cambio del cliente o reposición), obligatorio para enviar el requerimiento, y filtro «Material extra» en la lista.

## 15.20261013 — 14/10/2026

- Compra masiva consolidada (v1.6, M16-01): nueva pantalla Compras ▸ Pedidos ▸ Compra masiva con las líneas aprobadas de todas las obras por producto; la orden suma exacto (corrige el asistente de OCA, que dejaba fuera la última solicitud), cada solicitud y su requerimiento muestran como comprado solo su parte, y el origen nombra todas las solicitudes con su obra.
- La compra consolidada entra a stock general, sin analítica de las obras; la entrega directa en obra conserva su destino.

## 14.20261013 — 13/10/2026

- Ícono propio de la app «Requerimientos de obra» con el estilo de Odoo 19: icon.svg de 50×50 con formas planas y la paleta de Odoo, e icon.png de 100×100 sin fondo.

## 13.20261013 — 13/10/2026

- Código de obra en la obra: nombra su ubicación y es el código de su cuenta analítica. Con «El nombre del proyecto empieza con el código de obra» (Ajustes) se toma de la primera palabra del nombre.
- Alta de obra: al crear o marcar una obra se crea su cuenta analítica (plan de proyectos) con el código y el nombre de la obra, y se reutiliza la ubicación de la obra si ya existe bajo la ubicación padre.

## 12.20261012 — 12/10/2026

- Menú «Requerimientos» con Requerimientos y Materiales pedidos, como Compras ▸ Pedidos, en vez de dos acciones sueltas en el primer nivel.

## 11.20261012 — 12/10/2026

- Los datos de demostración (existencias de cemento y fierro) ya no impiden actualizar el módulo en una base con demo: se cargan una sola vez y no se reescriben en cada actualización.

## 10.20261011 — 11/10/2026

- El vale de requerimiento de obra usa el formato común de los documentos de la suite (el del comprobante A4, módulo al_report_base): recuadro R.U.C./tipo/número con el estado, tablas con borde redondeado, materiales con el valor estimado al pie, aprobaciones, firmas y pie con la numeración de páginas.

## 9.20261009 — 09/10/2026

- Ícono propio en el menú principal (casco de obra sobre una lista de verificación), con el estilo del de la app Perú (fondo de color y trazo blanco), para no confundirlo con la app oficial de Compras; en Aplicaciones sigue el ícono nativo.

## 8.20261008 — 08/10/2026

- El requerimiento de obra de la transferencia pasa a su grupo en la página Logística PE.

## 7.20261008 — 08/10/2026

- Etiquetas en español: los campos sin etiqueta propia (Activo, Nombre, Compañía, contadores…) y los heredados de Odoo (Creado por, Mensajes, Actividades…) ya no se muestran en inglés.

## 6.20261008 — 08/10/2026

- Ajustes por compañía con el ícono de Odoo «valores por compañía» (company_dependent).

## 5.20261008 — 08/10/2026

- Ícono nativo de la app de Odoo a la que pertenece (sin imágenes propias ni el logo de la Marca Perú).
- Multicompañía según la guía de Odoo 19: _check_company_auto y check_company en las relaciones; Odoo impide mezclar registros de compañías distintas.
- La compañía es de solo lectura en los formularios y listas: se toma de la compañía activa.

## 01/10/2026

- El reparto entre stock y compra sigue el algoritmo de la regla nativa «tomar de stock; si no hay, activar otra regla»: cálculo en la unidad del producto y el resto en la unidad de la línea, de modo que lo despachado más lo comprado siempre da lo pedido.
- Lo recibido en obra se calcula como en Compras: conversión con redondeo al medio y las devoluciones de la obra al almacén restan.
- Las transferencias del requerimiento comparten una referencia de inventario, como las de una orden de compra.

## 3.20261001 — 01/10/2026

- Corregido el error al agregar un material en un requerimiento nuevo (Expected singleton: uom.uom()).

## 2.20260930 — 30/09/2026

- Primera versión: requerimiento de obra, aprobación por niveles, división stock o compra por línea, compra vía almacén central o directo a obra, y cierre y cancelación automáticos.
- Ajustes propios de la app y menú de reglas de aprobación.
- Materiales como tarjetas en el celular; calendario por fecha requerida y vista de actividades.
- Mensajes del chatter legibles, también los del requerimiento de compra al confirmar la orden de compra.
- Vale de requerimiento de obra en PDF (botón «Imprimir vale»).
- Interfaz completamente en español, incluidos los campos de actividades, seguidores y aprobación.
