# Servidor MCP para Odoo — Guía del Usuario

> **Versión:** 3.20260825 · **Licencia:** OPL-1 · **Autor:** CRISTÓBAL OCH &lt;olanoit@gmail.com&gt;

Convierte Odoo en un servidor de herramientas listo para IA. Conecta Claude, ChatGPT, Gemini, Cursor, n8n, LangChain y cualquier cliente compatible con MCP a datos en vivo de Odoo — con gobernanza OAuth 2.0, registros de auditoría, herramientas de BI, páginas de portal, trabajos asíncronos y generación de módulos impulsada por IA.

> **Para instrucciones de instalación y conexión, consulta [docs/index.rst](docs/index.rst).**

---

## ¿Qué puedes hacer?

Una vez conectado, tu asistente de IA puede comunicarse con Odoo en lenguaje natural:

```
"Show me all unpaid invoices over 30 days old."
"Create a sales order for PT ABC, 5 units of Laptop Pro at 15 million each."
"What is my total revenue by customer this quarter?"
"Generate a PDF for sales order SO/2026/00201."
"Post an internal note on ticket #45 saying the issue is resolved."
```

La IA asigna automáticamente tu lenguaje natural a los modelos, campos y métodos correctos de Odoo. No necesitas conocer los nombres técnicos de los campos.

---

## Tabla de Contenidos

1. [Primeros Pasos — Darle Contexto a Claude](#1-primeros-pasos--darle-contexto-a-claude)
2. [Referencia de Recursos MCP](#2-referencia-de-recursos-mcp)
3. [Las 34+ Herramientas — Referencia Rápida](#3-las-34-herramientas--referencia-rápida)
4. [Flujos de Trabajo de Negocio](#4-flujos-de-trabajo-de-negocio)
   - [Órdenes de Venta](#41-órdenes-de-venta)
   - [Facturación y Pagos](#42-facturación-y-pagos)
   - [Órdenes de Compra](#43-órdenes-de-compra)
   - [Inventario y Entregas](#44-inventario-y-entregas)
   - [CRM y Pipeline](#45-crm-y-pipeline)
5. [Analítica y Reportes de BI](#5-analítica-y-reportes-de-bi)
6. [Páginas de Portal (Tableros Compartibles)](#6-páginas-de-portal-tableros-compartibles)
7. [Cola de Trabajos Asíncronos (Operaciones Masivas)](#7-cola-de-trabajos-asíncronos-operaciones-masivas)
8. [Generador de Módulos con IA](#8-generador-de-módulos-con-ia)
9. [Chatter y Comunicación](#9-chatter-y-comunicación)
10. [Consejos de Prompting Efectivo](#10-consejos-de-prompting-efectivo)
11. [Solución de Problemas para Usuarios Finales](#11-solución-de-problemas-para-usuarios-finales)

---

## 1. Primeros Pasos — Darle Contexto a Claude

Cuando conectas Claude a Odoo por primera vez, no conoce la configuración de tu compañía. Lo primero que debes decir en cada nueva sesión:

```
Read odoo://context and odoo://catalog so you understand my Odoo instance before we start.
```

Después de leer estos recursos, Claude conoce:
- El nombre de tu compañía, moneda, país y zona horaria
- Qué módulos de Odoo están instalados (Ventas, Contabilidad, Inventario, etc.)
- Todos los modelos de datos disponibles y sus nombres técnicos
- Tu nombre de usuario y tu idioma

**Apertura de sesión recomendada:**
```
Read odoo://context and odoo://catalog. Tell me briefly what modules I have installed
and what you can help me with today.
```

---

## 2. Referencia de Recursos MCP

Los recursos son instantáneas de solo lectura que Claude carga bajo demanda.

| URI del Recurso | Qué contiene | Cuándo usarlo |
|---|---|---|
| `odoo://context` | Información de la compañía, detalles del usuario, módulos instalados, fecha del servidor | Al inicio de cada sesión |
| `odoo://catalog` | Todos los modelos instalados con sus nombres técnicos | Al explorar qué datos existen |
| `odoo://model/{name}` | Definiciones completas de campos de un modelo | Antes de crear o actualizar registros |
| `odoo://chatter/{model}/{id}` | Los últimos 20 mensajes del chatter de un registro | Antes de responder a clientes o revisar el historial |
| `odoo://attachment/{id}` | Metadatos del archivo + vista previa del contenido (archivos de texto < 50 KB) | Al verificar archivos subidos |

**Ejemplos:**
```
Read odoo://model/sale.order — what fields does a Sales Order have?
Read odoo://chatter/helpdesk.ticket/45 — what did the customer say last?
Read odoo://attachment/107 — how many rows are in this CSV?
```

---

## 3. Las 34+ Herramientas — Referencia Rápida

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

### Herramientas de Flujo de Trabajo y Formularios

| Herramienta | Qué hace |
|---|---|
| `odoo_default_get` | Obtiene los valores por defecto de un nuevo registro |
| `odoo_onchange` | Simula los valores calculados al cambiar un campo |
| `odoo_get_views` | Descubre los métodos invocables y los reportes disponibles |
| `odoo_message_post` | Publica un mensaje en el chatter o una nota interna |
| `odoo_create_attachment` | Sube un archivo a Odoo |
| `odoo_print_report` | Obtiene la URL de descarga de un reporte PDF/HTML |

### Herramientas de Analítica

| Herramienta | Qué hace |
|---|---|
| `odoo_count` | Cuenta los registros que coinciden con un dominio |
| `odoo_name_search` | Encuentra registros por su nombre visible (autocompletado) |
| `odoo_read_group` | Agregación GROUP BY (equivalente al GROUP BY de SQL) |

### Herramientas de Reportes de BI

| Herramienta | Qué hace |
|---|---|
| `odoo_pivot` | Tabla dinámica con agrupación por fila/columna/medida |
| `odoo_time_series` | Series de tiempo con relleno de huecos y tendencia |
| `odoo_top_n` | Ranking Top-N con porcentaje de participación |
| `odoo_cohort` | Análisis de retención por cohorte |
| `odoo_funnel` | Conversión de embudo a través de etapas |
| `odoo_export_csv` | Exporta los resultados de una consulta como descarga CSV |
| `odoo_export_xlsx` | Exporta los resultados de una consulta como descarga XLSX |

### Herramientas de Trabajos Asíncronos

| Herramienta | Qué hace |
|---|---|
| `odoo_submit_job` | Envía una operación pesada a la cola en segundo plano |
| `odoo_job_status` | Consulta el estado de un trabajo enviado |
| `odoo_job_list` | Lista los trabajos recientes |
| `odoo_job_cancel` | Cancela un trabajo pendiente |

### Herramientas de Páginas de Portal

| Herramienta | Qué hace |
|---|---|
| `odoo_create_portal_page` | Crea un tablero público compartible |
| `odoo_list_portal_pages` | Lista las páginas de portal existentes |
| `odoo_update_portal_page` | Actualiza la especificación de una página de portal |

### Herramientas del Generador de Módulos *(requiere alcance de administrador)*

| Herramienta | Qué hace |
|---|---|
| `odoo_validate_module_spec` | Valida la especificación de un módulo sin generarlo |
| `odoo_generate_module` | Genera un ZIP instalable a partir de una especificación JSON |
| `odoo_list_generated_modules` | Lista los módulos generados previamente |
| `odoo_install_generated_module` | Instala un módulo generado (con confirmación) |

---

## 4. Flujos de Trabajo de Negocio

### 4.1 Órdenes de Venta

**Crear y confirmar una orden de venta:**
```
Create a confirmed sales order for PT Maju Sejahtera for 2 units of Laptop Pro 15
at 15,000,000 each. Add an internal note that delivery is expected by end of month.
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
Show me all confirmed sales orders this month, sorted by amount descending.
What is the total value of open quotations for customer Acme Corporation?
Print the PDF for sales order SO/2026/00201.
Send a customer-facing message on SO/2026/00201 saying the order is being prepared.
```

---

### 4.2 Facturación y Pagos

**Revisar facturas vencidas:**
```
Show all customer invoices that are more than 30 days overdue.
Include customer name, invoice number, amount, and days overdue.
```

**Publicar (validar) una factura:**
```
Post (validate) invoice INV/2026/00088.
```

**Revisar el estado de pago por cliente:**
```
How much does Acme Corporation still owe us? List all unpaid invoices.
```

**Restablecer a borrador y corregir:**
```
Reset invoice INV/2026/00088 to draft — I need to add a line item.
```

**Reporte de antigüedad de saldos:**
```
Show me accounts receivable aging — total owed grouped by whether it's current,
1-30 days overdue, 31-60 days, or 60+ days overdue.
```

---

### 4.3 Órdenes de Compra

**Crear y aprobar una orden de compra:**
```
Create a purchase order for Supplier ABC for 100 units of Raw Material A at 50,000 each.
Then approve it.
```

**Revisar recepciones pendientes:**
```
Which purchase orders have been confirmed but not yet received?
```

---

### 4.4 Inventario y Entregas

**Revisar niveles de stock:**
```
What is the current stock level for all products in the main warehouse?
Show anything below 10 units first.
```

**Validar una entrega:**
```
Validate delivery order WH/OUT/00055.
```

**Encontrar productos que necesitan reabastecimiento:**
```
Show all products where available quantity is below 5 units.
```

---

### 4.5 CRM y Pipeline

**Revisar el pipeline:**
```
Show all opportunities in the "Proposal" stage worth more than 50 million,
sorted by expected revenue descending.
```

**Avanzar un negocio:**
```
Move opportunity #77 to stage "Won" and post a note saying the contract was signed today.
```

**Resumen del pipeline:**
```
Give me a summary of the sales pipeline: total value and count by stage.
```

---

## 5. Analítica y Reportes de BI

### read_group — Agregación de negocio

```
Total sales by customer this year:

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
Show me a pivot table of invoice amounts: rows = customer, columns = month, values = total invoiced.
```

Claude usa `odoo_pivot` para construir una tabla cruzada a través de dos dimensiones.

### Series de tiempo con tendencia

```
Show monthly sales revenue for the last 12 months with trend direction.
```

Claude usa `odoo_time_series` con relleno automático de huecos para los meses sin datos.

### Ranking Top-N

```
Top 10 products by revenue this quarter with share percentage.
```

Claude usa `odoo_top_n` y devuelve el % del total de cada elemento.

### Retención por cohorte

```
Show me a cohort analysis of new customers acquired in Q1 2026 —
what % are still buying 1 month, 2 months, 3 months later?
```

### Exportar a CSV/XLSX

```
Export all unpaid invoices over 60 days to an Excel file.
```

Claude usa `odoo_export_xlsx` y devuelve una URL de descarga del archivo.

---

## 6. Páginas de Portal (Tableros Compartibles)

Las páginas de portal son URLs públicas respaldadas por datos en vivo de Odoo — no requieren inicio de sesión para verse.

**Crear un tablero de KPIs:**
```
Create a portal page at /mcp-page/sales-dashboard with:
- KPI tile: total confirmed sales orders this month
- KPI tile: total revenue this month
- Bar chart: revenue by salesperson this month
- Table: top 10 customers by revenue
```

**Acceder a la página:**
```
https://your-odoo.com/mcp-page/sales-dashboard
```

Las páginas son responsivas para móviles, se renderizan del lado del servidor y siempre muestran los datos actuales. Pueden incrustarse en herramientas externas usando una URL firmada de `odoo_create_portal_page`.

---

## 7. Cola de Trabajos Asíncronos (Operaciones Masivas)

Para operaciones pesadas que agotarían el tiempo de espera como una solicitud normal, usa la cola asíncrona.

**Enviar una actualización masiva:**
```
Submit a background job to update the pricelist for all active customers
in the "Retail" category to "Retail Price List 2026".
```

Claude usa `odoo_submit_job`, devuelve un `job_id` y puedes consultar el estado:

```
Check the status of job #42.
```

**Exportación masiva:**
```
Submit a background job to export all sales order lines from January 2026 to an XLSX file.
Notify me when it is done.
```

Cuando el trabajo se completa, `odoo_job_status` devuelve una URL de descarga del archivo.

---

## 8. Generador de Módulos con IA

> **Requiere:** token con alcance de administrador + el generador de módulos activado en la Configuración.

El generador de módulos permite que Claude diseñe un módulo completo de Odoo a partir de una descripción —modelos, vistas, reglas de seguridad y menús— y produzca un ZIP instalable.

**Ejemplo de conversación:**
```
You: Design an Odoo module for managing theme park attractions.
     Each attraction has a name, category (ride/show/restaurant),
     capacity, and maintenance status. Include a kanban view and access groups.

Claude: I'll validate the spec first, then generate the ZIP.
        [uses odoo_validate_module_spec → odoo_generate_module]
        Done. Download: /web/content/42?download=1
```

**Instalar el módulo generado:**
```
Install generated module #42. I confirm this is intentional.
```

Claude usa `odoo_install_generated_module` con `confirm: true`.

> **Advertencia:** La instalación reinicia el registro de módulos de Odoo. Úsalo solo en entornos
> que no sean de producción, a menos que estés seguro de que el módulo generado es seguro.

---

## 9. Chatter y Comunicación

Cada registro con un chatter (mail.thread) puede leerse y recibir publicaciones.

**Leer el historial de conversación:**
```
Read the chatter on sales order SO/2026/00201 and summarize what has happened so far.
```

**Responder a un cliente:**
```
On invoice INV/2026/00088, post a customer-facing message:
"Your payment of IDR 25,000,000 is 15 days overdue. Please remit by this Friday."
```

**Nota interna:**
```
On helpdesk ticket #45, post an internal note that the issue was escalated to the dev team.
```

| Subtipo | Visible para | Cuándo usarlo |
|---|---|---|
| `mail.mt_comment` (por defecto) | Cliente + seguidores | Comunicación con el cliente, actualizaciones de estado |
| `mail.mt_note` | Solo usuarios internos | Notas del equipo, pista de auditoría, recordatorios de proceso |

---

## 10. Consejos de Prompting Efectivo

### Siempre empieza con contexto
```
Read odoo://context and odoo://catalog first, then help me with [task].
```

### Sé específico sobre lo que quieres
```
✅ Show all confirmed sales orders from January 2026, sorted by amount descending,
   with customer name, order date, and total amount.

❌ Show me sales data.
```

### Pide a Claude que verifique antes de crear
```
Before creating the invoice, read odoo://model/account.move so you know
the required fields and correct defaults.
```

### Encadena operaciones en un solo prompt
```
Find customer "PT Sentosa", create a quotation for 3 units of Product A at 5,000,000,
add an internal note "requested by sales manager", and confirm the order.
```

### Usa read_group para resúmenes, search_read para detalles
```
✅ For "how much total?" → use odoo_read_group
✅ For "show me the list" → use odoo_search_read
```

---

## 11. Solución de Problemas para Usuarios Finales

**"Claude no conoce mis modelos de Odoo"**

Ejecuta el cargador de contexto al inicio de cada sesión:
```
Read odoo://context and odoo://catalog.
```

**Error "Access Denied" (Acceso Denegado)**

Tu usuario de Odoo no tiene permiso para ese modelo o registro.
Pide a tu administrador que revise tus derechos de acceso en
**Configuración → Usuarios → [tu usuario] → Derechos de Acceso**.

**"Method is blocked" (Método bloqueado)**

El método comienza con `_` (privado) o es un método de escalada de privilegios.
Usa `odoo_get_views(model=...)` para ver qué métodos pueden invocarse de forma segura.

**"Required field missing" (Falta un campo obligatorio) al crear registros**

Pide a Claude:
```
Before creating a [model], use odoo_default_get and odoo_onchange
to check all required fields and defaults first.
```

**"La URL del reporte PDF no funciona"**

Debes haber iniciado sesión en Odoo en tu navegador para acceder a las URLs de los reportes.
La URL no es de acceso público.

**"Rate limit exceeded" (Se excedió el límite de tasa)**

Demasiadas solicitudes por minuto. Haz una pausa breve o pide a tu administrador que
aumente el límite de tasa en **Configuración → Servidor MCP → Límite de tasa por minuto**.
