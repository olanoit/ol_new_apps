# Guía funcional — <Nombre del módulo>

> Módulo técnico `<modulo>` · versión `<N.AAAAMMDD>` · área `<OL-ÁREA>`.
> Para consultores funcionales: qué resuelve, la norma que lo respalda y el
> proceso completo con un ejemplo que cuadra. Enlaces verificados el
> <DD/MM/AAAA> con `docs/validacion/verificar_enlaces.py`.

## 1. Para qué sirve

Problema de negocio en 3–5 líneas, quién lo usa (contador, tesorería,
RR. HH., almacén…) y qué hace el módulo en una frase. Qué queda fuera del
alcance.

## 2. Marco normativo y conceptual

- Norma o criterio que obliga o explica el proceso (ley, decreto, resolución
  SUNAT, NIIF, PCGE), con su enlace oficial **verificado**.
- Conceptos clave explicados en lenguaje de negocio (definición corta y por
  qué importa).
- Tabla de términos si ayuda (término · significado · dónde aparece en Odoo).

## 3. Proceso de inicio a fin

Diagrama (Mermaid `flowchart TD`) del flujo completo y, debajo, cada paso:

| # | Paso | Dónde en Odoo (menú ▸ …) | Quién | Resultado (documento, asiento, estado) |
|---|---|---|---|---|

Incluir los caminos alternativos: anulación, corrección, error del servicio
externo, cierre de periodo.

## 4. Ejemplo completo

Caso realista con datos concretos (empresa, fechas, importes, moneda). Para
cada paso: lo que se registra y el resultado.

- Asientos con cuentas del PCGE: tabla `Cuenta · Descripción · Debe · Haber`
  que **cuadre** (sumas iguales) y totales verificables.
- Si hay cálculos (intereses, prorrata, tributos), mostrar la fórmula y el
  número.
- Las cifras deben coincidir con lo que hace el módulo (tests, datos de
  demostración o ficha).

## 5. Configuración inicial

Lista ordenada de lo que hay que configurar antes del primer uso (ajustes,
cuentas, diarios, secuencias, permisos), con la ruta de menú.

## 6. Reportes y libros relacionados

Qué reportes, libros PLE/SIRE o archivos SUNAT alimenta o usa, y cómo se
revisan.

## 7. Casos especiales y errores frecuentes

| Situación | Qué pasa | Qué hacer |
|---|---|---|

## 8. Preguntas frecuentes del consultor

Preguntas que haría un cliente o un consultor, con respuesta directa.

## 9. Referencias

Lista de enlaces oficiales (SUNAT, El Peruano, gob.pe, MEF, IFRS, Odoo…)
usados en la guía, **todos verificados** (fecha). Sin enlaces rotos ni
bloqueados: si una fuente oficial bloquea la verificación, usar otra fuente
oficial equivalente que sí responda.
