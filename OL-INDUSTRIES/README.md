OL-INDUSTRIES
=============

**Paquetes por industria.**

Para qué es esta carpeta
------------------------

Paquetes de industria al estilo de los de Odoo (por ejemplo «Pharmacy»,
`pharmacy_retail`): cada uno instala las aplicaciones de Odoo y los módulos de
la suite que usa un rubro y deja la base configurada para empezar a trabajar:
categorías de producto y de caja, etiquetas, opciones de inventario, datos de
demostración y la actividad económica principal (CIIU) de la compañía. Los que
planifican obras también aplican el perfil de vertical del planificador.

Qué va aquí
-----------

- `al_industry_base`: lo común (localización peruana de la suite y el registro
  de cada industria en **Ajustes ▸ Usuarios y compañías ▸ Industrias**, con el
  botón «Aplicar a la compañía activa» para las demás compañías).
- Un `al_industry_<rubro>` por industria, con `application: True`. Casi todo es
  dato (XML); solo lleva Python lo que el rubro necesita y Odoo no trae (p. ej.
  los datos DIGEMID del producto en farmacia).

Qué no va aquí
--------------

- Funcionalidad reutilizable por varios rubros → su área (`OL-POS/`,
  `OL-PROJECTS/`…); el paquete solo la instala y configura.
- Personalizaciones de un cliente concreto.

Industrias
----------

industria | módulo | CIIU | instala
--- | --- | --- | ---
Farmacia y botica | `al_industry_pharmacy` | 4772 | TPV con boleta/factura y tema propio, lotes con vencimiento (FEFO), fidelización, kárdex, libro de reclamaciones
Constructora | `al_industry_construction` | 4100 | Planificador por partidas con compras, contratas, cuadrillas, presupuesto, valorización, aprobaciones, marcación y planilla de construcción civil
Mobiliario a medida | `al_industry_furniture` | 3100 | Planificador con todos los puentes (perfil mobiliario): tipologías, fabricación, metrado, despacho e instalación
Bodega y minimarket | `al_industry_retail` | 4711 | TPV con boleta/factura y tema propio, Yape/Plin, cliente por RUC/DNI, vendedor, kárdex, libro de reclamaciones
Restaurante | `al_industry_restaurant` | 5610 | TPV de restaurante (mesas, comandas, propinas) con boleta/factura, tema propio, Yape/Plin, libro de reclamaciones
Tienda en línea | `al_industry_ecommerce` | 4791 | Tienda web con checkout peruano, Culqi, Niubiz e Izipay, kárdex, libro de reclamaciones virtual

Para añadir una industria: copie el paquete más parecido, registre su
`al.industry` en `data/al_industry_data.xml` (con su `<function>` en
`noupdate`), su ficha en `docs/fichas/` y su página en
`mkdocs/content/industries/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_industry_base](al_industry_base/) | 2.20261027 | OPL-1 | Lo que comparten los paquetes de industria: la localización peruana de la suite y el registro de cada industria, con su actividad CIIU, aplicable por compañía.
[al_industry_construction](al_industry_construction/) | 3.20261027 | LGPL-3 | Constructora lista para planificar y ejecutar obras: plan de recursos por partidas, requerimientos de obra, compras, contratas, cuadrillas, presupuesto, valorización, aprobaciones y planilla de construcción civil.
[al_industry_ecommerce](al_industry_ecommerce/) | 3.20261027 | OPL-1 | Tienda en línea lista para vender: catálogo web, checkout con RUC o DNI y ubigeo, pagos con Culqi, Niubiz o Izipay, boleta y factura electrónica y libro de reclamaciones virtual.
[al_industry_furniture](al_industry_furniture/) | 3.20261027 | LGPL-3 | Fábrica de muebles a medida para obras: tipologías con módulos y piezas, lista de materiales, órdenes de fabricación, metrado, despacho e instalación por torre, piso y departamento.
[al_industry_pharmacy](al_industry_pharmacy/) | 13.20261027 | OPL-1 | Farmacia o botica lista para vender: caja con boleta y factura electrónica, lotes con vencimiento y salida FEFO, datos DIGEMID del producto y libro de reclamaciones.
[al_industry_restaurant](al_industry_restaurant/) | 4.20261027 | OPL-1 | Restaurante listo para atender: salón con mesas, comandas a cocina, división de cuentas y propinas, boleta y factura electrónica desde la caja, cobro con Yape y Plin y libro de reclamaciones.
[al_industry_retail](al_industry_retail/) | 4.20261027 | OPL-1 | Bodega o minimarket listo para vender: caja con boleta y factura electrónica, cobro con Yape y Plin, cliente por RUC o DNI, vendedor por venta, kárdex SUNAT y libro de reclamaciones.
[//]: # (end addons)
