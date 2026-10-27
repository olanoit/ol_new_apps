OL-HEALTH
=========

**Salud: farmacias y boticas.**

Para qué es esta carpeta
------------------------

Suite para administrar farmacias y boticas sobre Odoo 19, con un núcleo general (sirve en cualquier país) y una capa para Perú (DIGEMID, Observatorio de precios, productos controlados, Ley 32033). Plan e investigación en `docs/farmacia/`.

Qué va aquí
-----------

- Módulos `al_pharmacy_*`: maestro farmacéutico y presentaciones de venta, buenas prácticas de almacenamiento, receta y dispensación, punto de venta.
- Módulos `al_l10n_pe_pharmacy_*`: obligaciones peruanas (controlados, DIGEMID, consulta al Colegio Médico).
- Más adelante, otros rubros de salud (clínica, óptica).

Qué no va aquí
--------------

- El paquete de industria que instala y configura la suite → `OL-INDUSTRIES/al_industry_pharmacy`.
- Funcionalidad de punto de venta que no es de farmacia → `OL-POS/`.

Módulos disponibles
-------------------

Tabla generada desde los manifiestos con `python3 scripts/gen_addons_table.py`
(no editar a mano).

[//]: # (addons)
módulo | versión | licencia | resumen
--- | --- | --- | ---
[al_l10n_pe_pharmacy_controlled](al_l10n_pe_pharmacy_controlled/) | 4.20261027 | OPL-1 | Listas de fiscalización, receta especial con sus datos y vigencia de 3 días, retención con folio, libros de estupefacientes y psicotrópicos y balance trimestral en PDF y Excel.
[al_l10n_pe_pharmacy_digemid](al_l10n_pe_pharmacy_digemid/) | 6.20261027 | OPL-1 | Precios para el Observatorio de DIGEMID, cumplimiento del 30 % de genéricos (Ley 32033), lista de precios por DCI, reacciones adversas para NotiMED e IGV exonerado de medicamentos oncológicos, para VIH y para diabetes.
[al_l10n_pe_pharmacy_edi](al_l10n_pe_pharmacy_edi/) | 3.20261027 | OPL-1 | Código de unidad del comprobante electrónico (catálogo 03 de SUNAT) para la unidad de cada presentación: caja BX, frasco BO; las demás, el de la unidad del producto.
[al_l10n_pe_prescriber_cmp](al_l10n_pe_prescriber_cmp/) | 4.20261027 | OPL-1 | Abre el portal «Conoce a tu médico» del Colegio Médico del Perú para buscar la colegiatura y registra si el médico está hábil, con fecha y responsable.
[al_pharmacy_base](al_pharmacy_base/) | 5.20261027 | OPL-1 | Maestro farmacéutico: principio activo y equivalentes, registro sanitario, condición de venta, presentaciones con precio propio, turnos del químico farmacéutico y libro de ocurrencias.
[al_pharmacy_care](al_pharmacy_care/) | 2.20261027 | OPL-1 | Tratamientos crónicos por paciente: días cubiertos por cada compra (también de equivalentes), recordatorio de recompra con WhatsApp o correo, adherencia (PDC) y aviso en la caja al elegir al cliente.
[al_pharmacy_insurance](al_pharmacy_insurance/) | 3.20261027 | OPL-1 | Convenios con aseguradoras y empresas: cobertura por producto o categoría, copago, topes por venta y por mes, afiliados, cobro de la parte cubierta en la caja y liquidación mensual a la aseguradora.
[al_pharmacy_loyalty](al_pharmacy_loyalty/) | 2.20261027 | OPL-1 | Puntos y vales para los clientes de la botica sin premiar los medicamentos con receta ni los controlados: no suman puntos ni reciben descuentos o regalos.
[al_pharmacy_pos](al_pharmacy_pos/) | 10.20261027 | OPL-1 | Caja de farmacia: venta por caja, blíster o unidad con su precio, alternativas genéricas primero, receta en la caja, control del químico farmacéutico, lotes disponibles por vencimiento y receta y dispensación registradas al vender.
[al_pharmacy_prescription](al_pharmacy_prescription/) | 4.20261027 | OPL-1 | Receta médica con prescriptor y paciente, dispensación parcial y alternativas, retención con folio, alergias del paciente, libro de recetas y etiqueta de dispensación.
[al_pharmacy_replenishment](al_pharmacy_replenishment/) | 2.20261027 | OPL-1 | Registro de la demanda perdida desde la caja (lo que se pide y no hay) y sugerido de compra por local según la venta diaria, los faltantes, el stock y lo que está por llegar, con solicitudes de presupuesto por proveedor o traslado desde el almacén central.
[al_pharmacy_stock](al_pharmacy_stock/) | 4.20261027 | OPL-1 | Recepción con inspección y registro sanitario vigente, lotes en cuarentena o bloqueados que no se venden, vencimientos, bonificaciones de compra, control de temperatura, alertas sanitarias y actas de baja.
[al_pharmacy_website](al_pharmacy_website/) | 3.20261027 | OPL-1 | Tienda en línea de la botica: genéricos primero en la ficha del producto, receta subida antes de pagar y validada por el químico farmacéutico, controlados solo en el local, recojo en tienda y cadena de frío en la hoja de reparto.
[//]: # (end addons)
