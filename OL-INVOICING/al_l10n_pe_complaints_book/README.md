# Perú - Libro de Reclamaciones (AL)

Guía funcional: [GUIA_FUNCIONAL.md](GUIA_FUNCIONAL.md)

Módulo técnico `al_l10n_pe_complaints_book`. El Libro de Reclamaciones físico y
virtual conforme a las normas vigentes a octubre de 2026. Los requisitos, con
su artículo y norma, están en
[`docs/reclamaciones/REQUISITOS_LEGALES.md`](../../docs/reclamaciones/REQUISITOS_LEGALES.md)
y las normas oficiales en `docs/reclamaciones/oficial/`.

## Qué hace

| Requisito | Norma | Cómo se cumple |
|---|---|---|
| Hoja con el formato del Anexo I | D.S. 101-2022-PCM | Informe «Hoja de reclamación» con las cuatro secciones, las leyendas de reclamo y queja, las dos notas legales literales y el destinatario |
| Numeración correlativa por libro | Reglamento, art. 5 | Secuencia sin huecos `000000001-AAAA` por libro y año, asignada antes de grabar |
| Código de identificación | Art. 8 | Un libro por establecimiento o canal, con código único por compañía |
| Datos sin los cuales la hoja «no se tiene por presentada» | Art. 5 | Nombre, documento, domicilio **o** correo y detalle, obligatorios en el formulario y en el modelo |
| Libro virtual accesible | Art. 4-B; Código, art. 151 | `/libro-reclamaciones` sin registro ni inicio de sesión; enlace con el ícono del libro en el pie de **todas** las páginas |
| Constancia inmediata | Art. 4-B | Correo automático con la hoja en PDF y la fecha y hora; página de constancia con enlace firmado para imprimirla y seguir el estado |
| 15 días hábiles improrrogables | Código, art. 24.1; arts. 6 y 6-B | Lunes a viernes sin los feriados del calendario configurado; alerta antes del vencimiento y actividad al vencer |
| Suspensión por oferta a distancia | Art. 6-A.2.b | Hasta 5 días hábiles; si el consumidor no acepta, el cron reanuda el plazo |
| Solución aceptada | Art. 6-A.3 | «ACUERDO ACEPTADO PARA SOLUCIONAR EL RECLAMO» en la hoja; el reclamo concluye |
| Recalificación queja → reclamo | Art. 6 | Botón con constancia en el historial |
| Respuesta por el medio pedido | Arts. 6 y 6-B | Correo con la hoja completada, o carta (imprimir y dejar constancia) |
| Libro de respaldo y canal telefónico | Arts. 2-A y 4-A | Canal de la hoja y número de la hoja de respaldo |
| Conservación de 2 años | Art. 12 | No se puede borrar una hoja antes de 2 años; los usuarios de atención no borran nunca |
| SIREC | Art. 16; Directiva 004-2014 | Archivo de carga masiva (18 campos separados por `|`) y marca de reportadas |
| Aviso del Anexo II | Art. 9 | Informe A4 imprimible por libro, con «(virtual)» o «(físico)» |

**Protección del formulario sin captcha** (el libro no puede ponerle
obstáculos al consumidor): campo trampa, firma del formulario con un tiempo
mínimo de llenado y un máximo de 5 hojas por conexión y hora.

**Datos personales**: solo los grupos «Atención de reclamos» y «Responsable»
ven las hojas; la IP de origen, solo el responsable. Reglas multicompañía en
libros y hojas.

## Configuración

1. **Libro de reclamaciones ▸ Configuración ▸ Libros**: un libro por
   establecimiento o canal; publique el virtual en sus sitios web.
2. **Ajustes**: calendario con los feriados nacionales (ausencias globales) y,
   si los ingresos superan las 3 000 UIT, «Obligada al SIREC».
3. Imprima el aviso del Anexo II en cada establecimiento físico.

## Pruebas

33 pruebas (unitarias y HTTP) sobre `ol_pe_v19`:

```bash
.venv/bin/python odoo-bin -c cfg/my/pe.cfg -d ol_pe_v19 -u al_l10n_pe_complaints_book \
  --test-enable --test-tags /al_l10n_pe_complaints_book --stop-after-init --workers=0
```

## Pendiente de la norma

El proyecto de reglamento de 2026 (R.M. 244-2026-PCM) aún no está vigente. El
módulo ya cumple lo que propone: acceso sin registro, adjuntos, diseño
adaptable, confirmación de voluntad y número y fecha y hora automáticos.

## Licencia

OPL-1. El historial de versiones está en [`CHANGELOG.md`](CHANGELOG.md).
