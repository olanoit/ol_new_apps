# Aplicaciones - Ficha completa del módulo (AL)

Módulo `al_base_module_info` para Odoo 19.

En **Aplicaciones**, Odoo sanea la descripción de cada módulo y descarta sus
estilos, así que la ficha (`static/description/index.html`) se ve sin diseño.
Este módulo lleva a la tarjeta del kanban un acceso a la ficha completa:

- El botón **Más información** de la tarjeta pasa a ser **Ver la ficha completa
  del módulo** cuando el módulo tiene ficha, y la abre en una pestaña nueva.
- El menú de la tarjeta suma la misma opción; «Más información» sigue llevando
  a la web del autor.
- Los módulos sin ficha, incluidos los de Odoo, no cambian.

Una ficha cuenta como tal cuando la ha preparado
`docs/validacion/fichas_modulos.py`, que deja la marca `al-ficha-link`. Al crear
un módulo nuevo, correr ese script para que su tarjeta ofrezca la ficha.

Solo depende de `base`. No requiere configuración.
