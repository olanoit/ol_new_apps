# Un contable sin el grupo de letras no puede escribir en facturas

**Detectado:** 15/08/2026, base `ol_pe_v19`. **Módulo:** `al_l10n_pe_account_letter`.
**Estado: corregido** el 15/08/2026 (`al_l10n_pe_account_letter` v2.20260815).

---

## Síntoma

Cualquier escritura sobre una factura hecha por un usuario contable que no pertenezca a los grupos
de gestión de letras falla:

```
odoo.exceptions.AccessError: No puede acceder a los registros 'Gestión de letras' (l10n_pe.letter).
Esta operación está permitida para los siguientes grupos:
    - Gestión de letras/Admin
    - Gestión de letras/User
```

Se manifiesta en tres tests de `al_l10n_pe_invoice` (`TestInvoiceReport`) y en cualquier flujo que
revierta o modifique una factura. En los tests del RCE hubo que sortearlo con `sudo()`.

---

## Causa

`al_l10n_pe_account_letter` añade a `account.move` un Many2many hacia `l10n_pe.letter`:

```python
l10n_pe_letter_ids = fields.Many2many('l10n_pe.letter', 'account_move_letter_rel',
                                      'move_id', 'letter_id', string='Letras')
```

Al escribir en la factura, el ORM comprueba el acceso de lectura sobre el modelo relacionado. Y el
`ir.model.access.csv` del módulo solo concede permisos a sus dos grupos propios:

| Regla | Grupo |
|---|---|
| `access_l10n_pe_letter_admin` | `app_group_admin` (Gestión de letras/Admin) |
| `access_l10n_pe_letter_user` | `app_group_user` (Gestión de letras/User) |

No hay ninguna regla para `account.group_account_user`, que es el grupo del contable corriente.
El resultado es que **instalar el módulo de letras restringe quién puede editar facturas**, cosa
que no es lo que el módulo pretende hacer.

---

## Alcance

- No es una regresión de los cambios de tipo de cambio ni del RCE: el módulo de letras no se ha
  tocado, y la traza no pasa por ninguno de ellos.
- Afecta a **producción**, no solo a los tests: un contable sin el grupo de letras no puede
  publicar ni revertir facturas en una base con el módulo instalado.

## Corrección aplicada

Tres reglas de **solo lectura** para `account.group_account_user`, añadidas al
`ir.model.access.csv` del módulo:

| Modelo | Permisos |
|---|---|
| `l10n_pe.letter` | leer |
| `l10n_pe.letter.line` | leer |
| `l10n_pe.letter.invoice.line` | leer |

El contable puede ver las letras asociadas a una factura —y por tanto escribir en ella— pero no
crearlas, modificarlas ni borrarlas: eso sigue reservado a los grupos de gestión de letras.

Se eligió esta vía frente a la alternativa de hacer que el grupo de letras implique al contable,
porque no cambia quién gestiona letras: solo desbloquea la escritura en facturas, que es el
efecto colateral que no se pretendía.

**Verificado:** los tres tests de `al_l10n_pe_invoice` que fallaban pasan, y los 23 de
`al_l10n_pe_account_letter` siguen en verde.
