# Servidor MCP para Odoo — Guía del usuario

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

> **Versión:** 8.20261009 · **Licencia:** OPL-1 · **Autor:** CRISTÓBAL OCH &lt;olanoit@gmail.com&gt;

Convierte Odoo en un servidor de herramientas listo para IA. Conecta Claude, ChatGPT, Gemini, Cursor, n8n, LangChain y cualquier cliente compatible con MCP a datos en vivo de Odoo — con gobernanza OAuth 2.0, registros de auditoría, herramientas de BI, páginas de portal, trabajos asíncronos y generación de módulos impulsada por IA.

> **Para las instrucciones de instalación y conexión, consulta [doc/index.rst](doc/index.rst).**

---

## ¿Qué puedes hacer?

Una vez conectado, tu asistente de IA puede comunicarse con Odoo en lenguaje natural:

```
"Muéstrame todas las facturas impagas con más de 30 días de antigüedad."
"Crea una orden de venta para Comercial Andina S.A.C., 5 unidades de Laptop Pro a S/ 4,500 cada una."
"¿Cuáles son mis ingresos totales por cliente en este trimestre?"
"Genera el PDF de la orden de venta SO/2026/00201."
"Publica una nota interna en el ticket #45 indicando que el problema está resuelto."
```

La IA asigna automáticamente tu lenguaje natural a los modelos, campos y métodos correctos de Odoo. No necesitas conocer los nombres técnicos de los campos.

---

## Tabla de contenidos

1. [Primeros pasos — darle contexto a Claude](#1-primeros-pasos--darle-contexto-a-claude)
2. [Referencia de recursos MCP](#2-referencia-de-recursos-mcp)
3. [Las 34+ herramientas — referencia rápida](#3-las-34-herramientas--referencia-rápida)
4. [Flujos de trabajo de negocio](#4-flujos-de-trabajo-de-negocio)
   - [Órdenes de venta](#41-órdenes-de-venta)
   - [Facturación y pagos](#42-facturación-y-pagos)
   - [Órdenes de compra](#43-órdenes-de-compra)
   - [Inventario y entregas](#44-inventario-y-entregas)
   - [CRM y pipeline](#45-crm-y-pipeline)
5. [Analítica y reportes de BI](#5-analítica-y-reportes-de-bi)
6. [Páginas de portal (tableros compartibles)](#6-páginas-de-portal-tableros-compartibles)
7. [Cola de trabajos asíncronos (operaciones masivas)](#7-cola-de-trabajos-asíncronos-operaciones-masivas)
8. [Generador de módulos con IA](#8-generador-de-módulos-con-ia)
9. [Chatter y comunicación](#9-chatter-y-comunicación)
10. [Consejos para escribir buenos prompts](#10-consejos-para-escribir-buenos-prompts)
11. [Solución de problemas para usuarios finales](#11-solución-de-problemas-para-usuarios-finales)

---

## 1. Primeros pasos — darle contexto a Claude

Cuando conectas Claude a Odoo por primera vez, no conoce la configuración de tu compañía. Lo primero que debes decir en cada nueva sesión:

```
Lee odoo://context y odoo://catalog para que entiendas mi instancia de Odoo antes de empezar.
```

Después de leer estos recursos, Claude conoce:
- El nombre de tu compañía, moneda, país y zona horaria
- Qué módulos de Odoo están instalados (Ventas, Contabilidad, Inventario, etc.)
- Todos los modelos de datos disponibles y sus nombres técnicos
- Tu nombre de usuario y tu idioma

**Apertura de sesión recomendada:**
```
Lee odoo://context y odoo://catalog. Dime brevemente qué módulos tengo instalados
y en qué puedes ayudarme hoy.
```

---

## 2. Referencia de recursos MCP

Los recursos son instantáneas de solo lectura que Claude carga bajo demanda.

| URI del recurso | Qué contiene | Cuándo usarlo |
|---|---|---|
| `odoo://context` | Información de la compañía, datos del usuario, módulos instalados, fecha del servidor | Al inicio de cada sesión |
| `odoo://catalog` | Todos los modelos instalados con sus nombres técnicos | Al explorar qué datos existen |
| `odoo://model/{name}` | Definiciones completas de los campos de un modelo | Antes de crear o actualizar registros |
| `odoo://chatter/{model}/{id}` | Los últimos 20 mensajes del chatter de un registro | Antes de responder a clientes o revisar el historial |
| `odoo://attachment/{id}` | Metadatos del archivo + vista previa del contenido (archivos de texto < 50 KB) | Al verificar archivos subidos |

**Ejemplos:**
```
Lee odoo://model/sale.order — ¿qué campos tiene una orden de venta?
Lee odoo://chatter/helpdesk.ticket/45 — ¿qué dijo el cliente por última vez?
Lee odoo://attachment/107 — ¿cuántas filas tiene este CSV?
```

---

## 3. Las 34+ herramientas — referencia rápida

### Herramientas CRUD

| Herramienta | Qué hace |
|---|---|
| `odoo_get_models` | Lista todos los modelos instalados de Odoo |
| `odoo_fields_get` | Obtiene las definiciones de campos de un modelo |
| `odoo_search_read` | Busca y lee registros (la herramienta más usada) |
| `odoo_create` | Crea un nuevo registro |
| `odoo_write` | Actualiza uno o más registros |
| `odoo_unlink` | Elimina registros de forma permanente |
| `odoo_call_method` | Llama a cualquier método `action_*` o `button_*` |

### Herramientas de flujo de trabajo y formularios

| Herramienta | Qué hace |
|---|---|
| `odoo_default_get` | Obtiene los valores por defecto de un nuevo registro |
| `odoo_onchange` | Simula los valores calculados al cambiar un campo |
| `odoo_get_views` | Descubre los métodos invocables y los reportes disponibles |
| `odoo_message_post` | Publica un mensaje en el chatter o una nota interna |
| `odoo_create_attachment` | Sube un archivo a Odoo |
| `odoo_print_report` | Obtiene la URL de descarga de un reporte PDF/HTML |

### Herramientas de analítica

| Herramienta | Qué hace |
|---|---|
| `odoo_count` | Cuenta los registros que coinciden con un dominio |
| `odoo_name_search` | Encuentra registros por su nombre visible (autocompletado) |
| `odoo_read_group` | Agregación GROUP BY (equivalente al GROUP BY de SQL) |

### Herramientas de reportes de BI

| Herramienta | Qué hace |
|---|---|
| `odoo_pivot` | Tabla dinámica con agrupación por fila/columna/medida |
| `odoo_time_series` | Series de tiempo con relleno de huecos y tendencia |
| `odoo_top_n` | Ranking Top-N con porcentaje de participación |
| `odoo_cohort` | Análisis de retención por cohorte |
| `odoo_funnel` | Conversión de embudo a través de etapas |
| `odoo_export_csv` | Exporta los resultados de una consulta como descarga CSV |
| `odoo_export_xlsx` | Exporta los resultados de una consulta como descarga XLSX |

### Herramientas de trabajos asíncronos

| Herramienta | Qué hace |
|---|---|
| `odoo_submit_job` | Envía una operación pesada a la cola en segundo plano |
| `odoo_job_status` | Consulta el estado de un trabajo enviado |
| `odoo_job_list` | Lista los trabajos recientes |
| `odoo_job_cancel` | Cancela un trabajo pendiente |

### Herramientas de páginas de portal

| Herramienta | Qué hace |
|---|---|
| `odoo_create_portal_page` | Crea un tablero público compartible |
| `odoo_list_portal_pages` | Lista las páginas de portal existentes |
| `odoo_update_portal_page` | Actualiza la especificación de una página de portal |

### Herramientas del generador de módulos *(requiere alcance de administrador)*

| Herramienta | Qué hace |
|---|---|
| `odoo_validate_module_spec` | Valida la especificación de un módulo sin generarlo |
| `odoo_generate_module` | Genera un ZIP instalable a partir de una especificación JSON |
| `odoo_list_generated_modules` | Lista los módulos generados previamente |
| `odoo_install_generated_module` | Instala un módulo generado (con confirmación) |

---

## 4. Flujos de trabajo de negocio

### 4.1 Órdenes de venta

**Crear y confirmar una orden de venta:**
```
Crea una orden de venta confirmada para Distribuidora del Sur S.A.C. por 2 unidades de
Laptop Pro 15 a S/ 4,500 cada una. Agrega una nota interna indicando que la entrega
se espera para fin de mes.
```

Claude hará automáticamente lo siguiente:
1. Encuentra el ID del contacto mediante `odoo_name_search`
2. Encuentra el ID del producto mediante `odoo_name_search`
3. Obtiene los valores por defecto mediante `odoo_default_get` y los valores específicos del cliente mediante `odoo_onchange`
4. Crea la orden de venta + la línea de la orden
5. La confirma con `action_confirm`
6. Publica la nota interna

**Otros prompts útiles:**
```
Muéstrame todas las órdenes de venta confirmadas de este mes, ordenadas por monto de mayor a menor.
¿Cuál es el valor total de las cotizaciones abiertas del cliente Comercial Andina S.A.C.?
Imprime el PDF de la orden de venta SO/2026/00201.
Envía un mensaje visible para el cliente en SO/2026/00201 indicando que el pedido se está preparando.
```

---

### 4.2 Facturación y pagos

**Revisar facturas vencidas:**
```
Muestra todas las facturas de clientes con más de 30 días de vencidas.
Incluye el nombre del cliente, el número de factura, el monto y los días de atraso.
```

**Publicar (validar) una factura:**
```
Publica (valida) la factura F001-00000088.
```

**Revisar el estado de pago por cliente:**
```
¿Cuánto nos debe todavía Comercial Andina S.A.C.? Lista todas sus facturas impagas.
```

**Restablecer a borrador y corregir:**
```
Restablece la factura F001-00000088 a borrador — necesito agregar una línea.
```

**Reporte de antigüedad de saldos:**
```
Muéstrame la antigüedad de las cuentas por cobrar — el total adeudado agrupado en
por vencer, 1-30 días vencido, 31-60 días o más de 60 días vencido.
```

---

### 4.3 Órdenes de compra

**Crear y aprobar una orden de compra:**
```
Crea una orden de compra al Proveedor ABC por 100 unidades de Materia prima A a S/ 15 cada una.
Luego apruébala.
```

**Revisar recepciones pendientes:**
```
¿Qué órdenes de compra están confirmadas pero todavía no se han recibido?
```

---

### 4.4 Inventario y entregas

**Revisar niveles de stock:**
```
¿Cuál es el stock actual de todos los productos en el almacén principal?
Muestra primero los que tengan menos de 10 unidades.
```

**Validar una entrega:**
```
Valida la orden de entrega WH/OUT/00055.
```

**Encontrar productos que necesitan reabastecimiento:**
```
Muestra todos los productos cuya cantidad disponible sea menor a 5 unidades.
```

---

### 4.5 CRM y pipeline

**Revisar el pipeline:**
```
Muestra todas las oportunidades en la etapa "Propuesta" por más de S/ 50,000,
ordenadas por ingreso esperado de mayor a menor.
```

**Avanzar un negocio:**
```
Mueve la oportunidad #77 a la etapa "Ganado" y publica una nota indicando que el contrato se firmó hoy.
```

**Resumen del pipeline:**
```
Dame un resumen del pipeline de ventas: valor total y cantidad por etapa.
```

---

## 5. Analítica y reportes de BI

### read_group — agregación de negocio

```
Ventas totales por cliente en este año:

odoo_read_group(
  model="sale.order",
  domain=[["state","=","sale"], ["date_order",">=","2026-01-01"]],
  groupby=["partner_id"],
  fields=["amount_total:sum", "id:count"],
  orderby="amount_total desc",
  limit=10
)
```

### Tabla dinámica

```
Muéstrame una tabla dinámica de los montos facturados: filas = cliente, columnas = mes, valores = total facturado.
```

Claude usa `odoo_pivot` para construir una tabla cruzada a través de dos dimensiones.

### Series de tiempo con tendencia

```
Muestra los ingresos por ventas mensuales de los últimos 12 meses con la dirección de la tendencia.
```

Claude usa `odoo_time_series` con relleno automático de huecos para los meses sin datos.

### Ranking Top-N

```
Los 10 productos con más ingresos de este trimestre, con su porcentaje de participación.
```

Claude usa `odoo_top_n` y devuelve el % del total de cada elemento.

### Retención por cohorte

```
Muéstrame un análisis de cohortes de los clientes nuevos captados en el primer trimestre de 2026 —
¿qué % sigue comprando 1, 2 y 3 meses después?
```

### Exportar a CSV/XLSX

```
Exporta a un archivo Excel todas las facturas impagas con más de 60 días.
```

Claude usa `odoo_export_xlsx` y devuelve una URL de descarga del archivo.

---

## 6. Páginas de portal (tableros compartibles)

Las páginas de portal son URLs públicas respaldadas por datos en vivo de Odoo — no requieren inicio de sesión para verse.

**Crear un tablero de KPIs:**
```
Crea una página de portal en /mcp-page/sales-dashboard con:
- Tarjeta KPI: total de órdenes de venta confirmadas este mes
- Tarjeta KPI: ingresos totales de este mes
- Gráfico de barras: ingresos por vendedor este mes
- Tabla: los 10 clientes con más ingresos
```

**Acceder a la página:**
```
https://your-odoo.com/mcp-page/sales-dashboard
```

Las páginas se adaptan a móviles, se renderizan del lado del servidor y siempre muestran los datos actuales. Pueden incrustarse en herramientas externas usando una URL firmada de `odoo_create_portal_page`.

---

## 7. Cola de trabajos asíncronos (operaciones masivas)

Para operaciones pesadas que agotarían el tiempo de espera de una solicitud normal, usa la cola asíncrona.

**Enviar una actualización masiva:**
```
Envía un trabajo en segundo plano para cambiar la lista de precios de todos los clientes
activos de la categoría "Minorista" a "Lista de precios minorista 2026".
```

Claude usa `odoo_submit_job`, devuelve un `job_id` y puedes consultar el estado:

```
Revisa el estado del trabajo #42.
```

**Exportación masiva:**
```
Envía un trabajo en segundo plano para exportar a un archivo XLSX todas las líneas de
órdenes de venta de enero de 2026. Avísame cuando termine.
```

Cuando el trabajo se completa, `odoo_job_status` devuelve una URL de descarga del archivo.

---

## 8. Generador de módulos con IA

> **Requiere:** token con alcance de administrador + el generador de módulos activado en los Ajustes.

El generador de módulos permite que Claude diseñe un módulo completo de Odoo a partir de una descripción —modelos, vistas, reglas de seguridad y menús— y produzca un ZIP instalable.

**Ejemplo de conversación:**
```
Tú: Diseña un módulo de Odoo para gestionar las atracciones de un parque temático.
    Cada atracción tiene nombre, categoría (juego/espectáculo/restaurante),
    capacidad y estado de mantenimiento. Incluye una vista kanban y grupos de acceso.

Claude: Primero validaré la especificación y luego generaré el ZIP.
        [usa odoo_validate_module_spec → odoo_generate_module]
        Listo. Descarga: /web/content/42?download=1
```

**Instalar el módulo generado:**
```
Instala el módulo generado #42. Confirmo que es intencional.
```

Claude usa `odoo_install_generated_module` con `confirm: true`.

> **Advertencia:** la instalación reinicia el registro de módulos de Odoo. Úsalo solo en entornos
> que no sean de producción, a menos que estés seguro de que el módulo generado es seguro.

---

## 9. Chatter y comunicación

Todo registro con chatter (mail.thread) puede leerse y recibir publicaciones.

**Leer el historial de conversación:**
```
Lee el chatter de la orden de venta SO/2026/00201 y resume lo que ha pasado hasta ahora.
```

**Responder a un cliente:**
```
En la factura F001-00000088, publica un mensaje visible para el cliente:
"Su pago de S/ 8,500.00 tiene 15 días de atraso. Por favor, realice el abono antes de este viernes."
```

**Nota interna:**
```
En el ticket de soporte #45, publica una nota interna indicando que el problema se escaló al equipo de desarrollo.
```

| Subtipo | Visible para | Cuándo usarlo |
|---|---|---|
| `mail.mt_comment` (por defecto) | Cliente + seguidores | Comunicación con el cliente, actualizaciones de estado |
| `mail.mt_note` | Solo usuarios internos | Notas del equipo, pista de auditoría, recordatorios de proceso |

---

## 10. Consejos para escribir buenos prompts

### Empieza siempre con contexto
```
Lee primero odoo://context y odoo://catalog y luego ayúdame con [tarea].
```

### Sé específico sobre lo que quieres
```
✅ Muestra todas las órdenes de venta confirmadas de enero de 2026, ordenadas por monto
   de mayor a menor, con el nombre del cliente, la fecha de la orden y el monto total.

❌ Muéstrame datos de ventas.
```

### Pide a Claude que verifique antes de crear
```
Antes de crear la factura, lee odoo://model/account.move para que conozcas
los campos obligatorios y los valores por defecto correctos.
```

### Encadena operaciones en un solo prompt
```
Busca el cliente "Inversiones Pacífico S.A.C.", crea una cotización por 3 unidades del Producto A
a S/ 1,500, agrega la nota interna "solicitado por el gerente de ventas" y confirma la orden.
```

### Usa read_group para resúmenes y search_read para detalles
```
✅ Para "¿cuánto en total?" → usa odoo_read_group
✅ Para "muéstrame la lista" → usa odoo_search_read
```

---

## 11. Solución de problemas para usuarios finales

**«Claude no conoce mis modelos de Odoo»**

Ejecuta el cargador de contexto al inicio de cada sesión:
```
Lee odoo://context y odoo://catalog.
```

**Error "Access Denied" (acceso denegado)**

Tu usuario de Odoo no tiene permiso para ese modelo o registro.
Pide a tu administrador que revise tus derechos de acceso en
**Ajustes → Usuarios → [tu usuario] → Derechos de acceso**.

**"Method is blocked" (método bloqueado)**

El método comienza con `_` (privado) o es un método de escalada de privilegios.
Usa `odoo_get_views(model=...)` para ver qué métodos pueden invocarse de forma segura.

**"Required field missing" (falta un campo obligatorio) al crear registros**

Pide a Claude:
```
Antes de crear un [modelo], usa odoo_default_get y odoo_onchange
para revisar primero todos los campos obligatorios y los valores por defecto.
```

**«La URL del reporte PDF no funciona»**

Debes haber iniciado sesión en Odoo en tu navegador para acceder a las URLs de los reportes.
La URL no es de acceso público.

**"Rate limit exceeded" (se excedió el límite de tasa)**

Demasiadas solicitudes por minuto. Haz una pausa breve o pide a tu administrador que
aumente el límite de tasa en **Ajustes → Servidor MCP → Límite de tasa por minuto**.
