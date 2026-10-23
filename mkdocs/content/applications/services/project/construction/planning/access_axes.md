---
modulos: [al_construction_planner]
---

# Grupos de acceso en dos ejes

Los permisos del planificador tienen dos ejes independientes, plan y
ejecución, y tres complementos. En **Ajustes ‣ Usuarios**, cada uno es una
selección de la sección Servicios.

| Eje | Grupo | Permite |
| --- | --- | --- |
| Plan | Consulta | Ver el plan, el árbol, el cronograma y el saldo |
| Plan | Planificador | Recetas, tipologías, niveles, planes en borrador, costos y versiones |
| Plan | Aprueba | Aprobar y cerrar planes |
| Ejecución | Reporta avance | Registrar avance |
| Ejecución | Ejecuta | Asignar contrata y cuadrilla, pedir material, registrar cambios y deductivos, preparar y presentar valorizaciones (incluye Plan: consulta) |
| Ejecución | Valida | Validar o rechazar avances y validar valorizaciones |
| Ejecución | Aprueba | Aprobar valorizaciones, excesos, material extra, cambios y liquidaciones |
| Complemento | Ve montos | Costos, precios, saldos y valorizaciones |
| Complemento | Ingresos | Valorización al cliente y su factura |
| Complemento | Administrador | Configuración; incluye Plan: aprueba, Ejecución: aprueba, Ve montos e Ingresos |

Un usuario puede tener solo plan, solo ejecución o los dos, en cualquier nivel.

## Desde la versión anterior

Al actualizar, cada usuario pasa a los grupos equivalentes y conserva sus
permisos: el **Planificador** anterior a Plan: planificador y Ejecución: valida;
la **jefatura de proyectos** recibe Plan: aprueba y Ejecución: aprueba y conserva
su rol (las rutas de aprobación lo siguen citando); Reporte de avance y Usuario
pasan a Ejecución: reporta avance y Ejecución: ejecuta. Las reglas de validación
que revisaba la jefatura pasan a Plan: aprueba (planes) o Ejecución: aprueba (el
resto).
