# TPV - Vendedor por orden (AL)

Módulo `al_pos_vendedor` para Odoo 19. Permite asignar un **vendedor**
(empleado de `hr.employee`) a cada orden del Punto de Venta, restringiendo la
selección a una lista de vendedores autorizados por punto de venta.

## Funcionalidades

- **Vendedores autorizados por TPV**: ajuste "Vendedores autorizados"
  (`authorized_seller`) y lista blanca `seller_ids` en la configuración del
  punto de venta. Los vendedores configurados aparecen en el selector del POS
  aunque no pertenezcan a los grupos de acceso de `pos_hr`
  (`_employee_domain` extendido).
- **Selector en la pantalla de pago**: botón "Vendedor" junto al de cliente que
  abre un diálogo con búsqueda en vivo, tarjetas con avatar (iniciales + color
  determinista), banner del vendedor actual y acción de quitar selección.
- **Apertura automática al validar**: si falta el vendedor, el selector se abre
  solo; únicamente si el cajero lo cierra sin elegir se muestra la advertencia
  "Vendedor requerido" y se cancela la validación.
- **Vendedor predeterminado por sesión**: estrella (★) en cada tarjeta para
  fijar/quitar el predeterminado; toda orden nueva lo hereda. Se guarda en
  `localStorage` con clave `alv_default_seller_<session_id>` acotada a la
  sesión POS abierta.
- **Vendedor en el ticket y en reportes**: el recibo muestra
  `Vendedor: <nombre>` y `report.pos.order` agrega `seller_id` para agrupar y
  filtrar el análisis de ventas por vendedor.

## Configuración

1. Ir a *Punto de Venta → Configuración* y abrir el punto de venta deseado.
2. Activar **"Vendedores autorizados"** y seleccionar los empleados permitidos.
3. Guardar y recargar la sesión del POS.

## Dependencias

`point_of_sale`, `hr`, `pos_hr`.

## Licencia

OPL-1.
