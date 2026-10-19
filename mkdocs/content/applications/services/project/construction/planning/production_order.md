---
modulos: [al_construction_planner_production, al_construction_planner_approvals_mrp, al_construction_planner_mrp]
---

# Orden de fabricación del mueble

La orden de fabricación que sale del plan lleva sus accesorios de armado,
pedidos sobre lo proyectado de sus módulos, y compara lo **presupuestado**,
lo **requerido** y lo **consumido** por material. El planificador suma esa
comparación de módulo a obra y por etapa.

## Configuración

1. El puente **Planificación de obra: orden de fabricación del mueble**
   (`al_construction_planner_production`) se instala solo con las
   [aprobaciones en fabricación](approvals.md#orden-de-fabricación).
2. Asigne el grupo **Planificación de obra: jefe de producción**. En cada
   orden, el jefe de producción puede elegir **Pide los accesorios** para que
   otra persona los pida.
3. En **Rutas de aprobación** queda la fila **Accesorios de armado: oficina
   técnica**, con el jefe de proyectos como seguidor.

## Pedir accesorios de armado

1. En la orden de fabricación, haga clic en **Pedir accesorios**. Se abre un
   pedido con lo proyectado en la sub etapa **Armado** para los módulos de la
   orden: por nivel, el accesorio, su **Saldo** (lo planificado menos lo ya
   pedido) y la cantidad propuesta.
2. Ajuste cantidades, cambie un accesorio por otro o agregue líneas. La
   columna **Cambio** marca **Cambio de material** (otro producto o uno que no
   está en el plan) o **Cambio de cantidad** (más que el saldo).
3. Haga clic en **Enviar**:
    - sin cambios, lo pedido se suma a los componentes de la orden y sale del
      almacén con la preparación de componentes;
    - con cambios, escriba el motivo: el pedido va a Oficina Técnica por
      Aprobaciones y, al aprobarse, se suma a la orden. Si se rechaza, vuelve a
      borrador con el motivo.

La orden se puede confirmar sin pedir accesorios: en ese caso avisa en su
historial al jefe de proyectos de la obra y a Logística. Supervisores y
Proyectos no piden accesorios de armado.

## Presupuestado frente a real

La pestaña **Presupuestado frente a real** de la orden muestra por material
lo presupuestado en el plan, lo requerido en sus componentes y, al cerrarla,
lo consumido, en cantidad y en soles. Los montos solo los ve quien tiene el
permiso de montos.

En **Planificación de obra ‣ Informes ‣ Plan ‣ Presupuestado frente a real de
fabricación**, las mismas cifras se reparten por obra, piso, departamento,
ambiente, mueble, módulo, etapa y material. Lo requerido y lo consumido de
una orden se reparten entre sus niveles en proporción a lo presupuestado; un
material que no está en el plan se reparte en partes iguales entre sus
ambientes. Así el piso suma lo mismo que sus órdenes.

!!! info "Ver también"
    - [Aprobaciones del plan y del requerimiento](approvals.md)
    - [Metrado](measurement.md)
