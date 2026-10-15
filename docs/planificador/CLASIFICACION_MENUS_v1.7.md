# Planificación de obra — clasificación de menús y asistentes (paquete 1.7, M17-12)

Cada menú y asistente del planificador se clasifica como **planificar**,
**controlar** u **operar**. Lo que opera se hace en la aplicación de Odoo que
le corresponde: en el planificador queda como **acceso directo** (abre las
vistas nativas del documento, filtradas a la obra) o, si no hay aplicación
nativa, se **justifica como control**. Fuente: los `views/menus.xml` del núcleo
y de los puentes (15/10/2026).

| Menú o asistente | Módulo | Clase | Decisión |
|---|---|---|---|
| Inicio | núcleo | Controlar | Se queda: obras, saldo, avance y pendientes de hoy |
| Obras, Tareas de la obra | núcleo | Planificar | Se queda (proyectos y tareas nativos con los campos de obra) |
| Planes de recursos, Árbol de recursos, Recursos planificados | núcleo | Planificar | Se queda |
| Generar desde la receta, Recetas, Importar recetas y niveles | núcleo | Planificar | Se queda |
| Cronograma de la obra, Etapas del cronograma, Gantt de proyectos | núcleo | Planificar | Se queda |
| Registrar avance, Avances por validar, Avances | núcleo | Controlar | Se queda: el avance validado es el ejecutado de la línea (sin aplicación nativa) |
| Metrados, Cargar medidas, Generar metrados | núcleo | Controlar | Se queda |
| Dependencias de terceros | núcleo | Planificar | Se queda: bloquean etapas del cronograma |
| Asignaciones del plan | núcleo | Controlar | Se queda: qué parte de cada documento nativo cubre cada línea |
| Análisis del plan, Control de saldo | núcleo | Controlar | Se queda |
| Ajustes, Perfiles de vertical, Plantillas, Etapas, Tipos de recurso, Actividades, Tarifas, Reglas analíticas, Reglas de aprobación, Colores del Gantt | núcleo | Configurar | Se queda en Configuración |
| Generar plan, Tipologías, Importar maestro y ETO | mobiliario | Planificar | Se queda |
| Orden de fabricación (asistente) | producción | Planificar | Propone la OF por nivel y etapa de fabricación; la OF se ejecuta en Fabricación |
| Órdenes de fabricación (menú) | producción | Operar | **Acceso directo** a Fabricación (acción nativa `mrp.mrp_production_action`) |
| Compra masiva (asistente) | compras | Planificar | Crea el requerimiento de compra; proveedores, cotizaciones y OC en Compras |
| Requerimientos de compra | compras | Operar | **Acceso directo** al requerimiento de compra (acción nativa de OCA) |
| Requerimiento de obra (asistente) | compras | Planificar | Crea el requerimiento de obra con el saldo del plan |
| Requerimientos de obra | compras | Operar | **Acceso directo** a la aplicación de requerimientos de obra (despacho en Inventario) |
| Abastecimiento de la obra | compras | Planificar | Se queda: necesidad por semana contra stock y compras |
| Precios de compra del producto, Compras por producto | compras | Controlar | Se queda: lee las OC confirmadas |
| Asignar contrata (asistente) | contratas | Planificar | Contrata, tarifa y alcance; suma el alcance a la OC de servicio |
| OC de servicio | contratas | Operar | **Acceso directo** a Compras (las OC de servicio de la obra); se confirman y gestionan en Compras |
| Liquidaciones semanales | contratas | Controlar | Se queda: no hay aplicación nativa; recibe en la OC de servicio y factura en Contabilidad |
| Asignar cuadrilla (asistente) | cuadrillas | Planificar (excepción: se opera aquí) | Arma la cuadrilla por rol; los turnos se publican en Planificación y las horas se registran en Hojas de horas |
| Adicionales y deductivos | ventas | Planificar | Se queda: entran al plan y al contrato |
| Contratos de obra, Hitos por unidad, Plantillas de hitos | ventas | Planificar | Se queda: el contrato y sus hitos de cobro |
| Entregas semanales | ventas | Controlar | Se queda: avance valorizado de la semana (sin aplicación nativa) |
| Preparar valorización, Valorizaciones | ventas | Controlar | Se queda: conformidad del cliente; la factura sale de la OV en Ventas y Contabilidad |
| Cobranza de la obra | ventas | Operar | **Acceso directo** a Contabilidad (facturas de la obra) |
| Cronograma valorizado, Análisis | ventas | Controlar | Se queda |

Ningún menú del planificador crea ni edita OC de material, OF, facturas o
pagos: los asistentes generan el documento de partida (requerimiento de
compra, requerimiento de obra, OF, OC de servicio, turnos) y el planificador
lee su resultado por las asignaciones (pedido, comprado, despachado,
consumido, recibido, horas).
