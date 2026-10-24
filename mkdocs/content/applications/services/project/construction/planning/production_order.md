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

## Estación de cada etapa

Con la cadena de plantas en **Configuración ‣ Etapas** (columna **Planta**),
el importador arma una lista de fabricación por etapa. Para que sus órdenes
pasen por una estación y generen órdenes de trabajo:

1. En **Configuración ‣ Etapas**, elija en la etapa su **Estación de la
   etapa** y, si quiere medir la carga, sus **Minutos por unidad** (puede ser
   0). Las dos son de la compañía activa.
2. Al importar el maestro, cada lista por etapa que no tiene operaciones
   recibe una con el nombre de la etapa, esa estación y ese tiempo. Una lista
   con operaciones puestas a mano conserva las suyas; una etapa sin estación
   deja la lista sin operaciones.
3. Para obras importadas antes, use **Completar operaciones** en la obra.

Las cantidades de cada lista suman las de los módulos ya redondeadas como el
plan, así que la orden no sale **Excede lo presupuestado** por céntimos.

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

## Tableros en planchas enteras

El almacén entrega tableros solo en planchas enteras, aunque el sistema
matriz pida fracción. La orden de corte guarda la **necesidad** en fracción
(la de la optimización o la de la lista de materiales) y pide planchas
enteras.

### Configurar

1. En **Ajustes ‣ Fabricación ‣ Planchas y retazos**, active **Pedir tableros
   en planchas enteras** y, si se quiere, una **Tolerancia de redondeo** (con
   0.1, una necesidad de 3.08 pide 3).
2. En **Inventario ‣ Configuración ‣ Unidades de medida**, marque **Plancha
   entera** en las unidades «Plancha L×A m»; su área sale del factor en m².
   Un producto puede forzar la regla con **Plancha indivisible** (Sí o No) en
   su pestaña de inventario.
3. Para retazos: en cada tablero, **Crear producto retazo** (una variante por
   banda R25, R50, R75 y R99, con lote); marque **Pool de retazos** en las
   ubicaciones donde se guardan y elija la **Ubicación de retazos** de cada
   planta (almacén). Con **Exigir «Declarar sobrantes»**, la orden no se
   termina sin declarar los tableros entregados.
4. En el mismo bloque se elige dónde actúa el redondeo (**Aplicar en el
   despacho a producción**, **en el requerimiento de obra** y **en compras**),
   la **Tolerancia del cuadre** (0.5 % por defecto), si se puede corregir
   **Piezas (m²)** al declarar, el **Formato del lote del retazo** (claves
   `{codigo}`, `{banda}`, `{largo}`, `{ancho}`, `{numero}`, `{obra}` y
   `{orden}`) y si se exige la casilla del despiece al cubrir con retazo.

### Confirmar la orden

Al confirmar, cada tablero se redondea por producto en toda la orden: con
7.2 de necesidad se piden 8, y si el mismo tablero está en dos líneas (3.14 y
0.5) se suman (4) y la diferencia va a la línea con más necesidad. El
despacho a producción nace en planchas enteras, reserva solo planchas enteras
(con 7.6 libres reserva 7) y no se valida con fracción. Un aviso arriba de la
orden resume necesidad, a entregar y redondeo; en los componentes se ven
**Necesidad**, **Redondeo** y **Cubierto con retazo**.

El control de exceso y **Presupuestado frente a real** comparan la necesidad:
el redondeo va en su propia columna y no cuenta como exceso, ni para el aviso
de consumo al terminar.

### Cubrir con retazo

En el despacho a producción, el almacenero pulsa **Cubrir con retazo** en la
línea del tablero. El asistente muestra la fracción a cubrir (necesidad 7.2 →
0.2 plancha, 1.04 m²) y los retazos libres del mismo tablero que alcanzan, del
más chico al más grande. Al marcar uno y confirmar que las piezas entran
(despiece), la plancha baja a 7 y el retazo se agrega reservado con su lote.
**Quitar retazo** lo deshace mientras el despacho no esté hecho. Si el retazo
cubre todo el tablero (necesidad 0.16 con un R25), la plancha queda en 0 sin
cancelarse y **Quitar retazo** la vuelve a pedir. El retazo no cuenta como
material sin presupuesto en la comparación, y cambiar la cantidad de la orden
no lo multiplica.

### Declarar sobrantes

Después del corte, producción pulsa **Declarar sobrantes**. Por tablero se ve
lo entregado (planchas y retazos, en m²) y las piezas; se escriben las
**Planchas sin tocar** y los retazos (largo, ancho y cantidad). Odoo calcula
área, % de plancha y banda; hasta 10 % es merma y sobre 99 %, plancha sin
tocar. La merma es lo que queda del cuadre y no puede ser negativa más allá
de la tolerancia (0.5 % de lo entregado por defecto). Mientras no se cargue el
despiece, **Piezas (m²)** se puede corregir y el historial registra quién lo
cambió y de cuánto a cuánto. Un tablero aún sin entregar sale marcado **Sin
entregar**: no se declara ahora y el asistente lo vuelve a mostrar cuando
llegue. El jefe de producción con **Fabricación: Usuario** declara sin otros
permisos. Al confirmar:

- las planchas sin tocar vuelven al stock con una devolución del despacho;
- cada retazo entra con su lote (`3101508-R50-1830x1200-0001`) a la
  ubicación de retazos, como subproducto de la orden;
- el retazo vale área × costo de la plancha ÷ área de la plancha y no entra
  al reparto de las piezas; con el [costeo de piezas por
  medida](../../../../inventory_and_mrp/mrp/piece_costing.md), su costo se
  descuenta del tablero del que sale;
- la pestaña **Sobrantes del corte** guarda el cuadre por tablero.

!!! info "Ver también"
    - [Aprobaciones del plan y del requerimiento](approvals.md)
    - [Metrado](measurement.md)
