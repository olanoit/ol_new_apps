# Aplicación de obra (AL)

Documentación funcional: [Aplicación de obra en el celular](../../mkdocs/content/applications/services/project/construction/planning/field_app.md)

Módulo `al_construction_portal` (requerimiento CREVAL v1.0, 4.11): aplicación
web instalable en `/obra/app/` para el capataz, la contrata y la oficina
técnica, que funciona sin señal (cola en IndexedDB y service worker) y habla
con Odoo por los servicios JSON de `/construction/api/v1/` con un token de
portador.

- Ingreso con usuario y clave o con el QR de la obra y un PIN de 4 dígitos
  (`construction.portal.member`, `construction.portal.token`).
- Cada envío lleva un `uuid`; `construction.portal.submission` evita
  duplicados al reintentar.
- Parte diario (`construction.daily.report`), tareo por partida
  (`construction.portal.tareo`, reparte el jornal ejecutado), catálogos del
  portal y kits, requerimiento de obra o interno, recepción y devolución.
