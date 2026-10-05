# ol_licencia_perpetua

Sustituye el servicio de suscripción de Odoo Enterprise en el cliente web
para que la interfaz no muestre el estado de la suscripción ni sus avisos
de expiración.

> **Depende de** `web_enterprise` · **Autor** Extendrix eCommerce Services

---

## Qué hace, técnicamente

Reemplaza el recurso
`web_enterprise/static/src/webclient/home_menu/enterprise_subscription_service.js`
por una versión propia, declarada en `assets` con una directiva
`('replace', …)`. No tiene modelos ni vistas: es una sustitución de un
único archivo del paquete de JavaScript del backend.

## Alcance de uso

El manifiesto lo describe como destinado a **entornos de prueba**. Odoo
Enterprise es software propietario y su acuerdo de licencia regula el uso
del código y la suscripción: **usar este módulo en producción, o para
operar Enterprise sin una suscripción vigente, incumple ese acuerdo**.

Si la empresa tiene contrato vigente y solo quiere evitar los avisos en
entornos internos de desarrollo, esa decisión —y su interpretación del
contrato— corresponde a quien administra la licencia.

## Por qué este módulo no tiene página de descripción

El resto de módulos del repositorio llevan un
`static/description/index.html` con su guía de uso. Este no lo lleva a
propósito: una guía de puesta en marcha de un módulo que anula un control
de licencia no es documentación que convenga tener escrita ni distribuida.
Lo que hace el módulo queda descrito arriba, que es lo que hace falta para
mantenerlo o decidir desinstalarlo.
