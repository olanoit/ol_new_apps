"""Capturas de al_construction_planner_spreadsheet (v1.5, fase 21): la hoja
de trabajo de una obra con las pestañas del maestro y el menú Archivo ▸
Enviar al planificador, que abre «Importar maestro y ETO». Comprueba de paso
que la hoja carga sin errores de JavaScript con el parche del módulo."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capturar import Captura  # noqa: E402

M = 'al_construction_planner_spreadsheet'


def rpc(c, model, method, args, kwargs=None):
    return c.page.evaluate("""async ([model, method, args, kwargs]) => {
        const res = await fetch('/web/dataset/call_kw', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {
                model, method, args, kwargs}})});
        const data = await res.json();
        if (data.error) { throw new Error(JSON.stringify(data.error.data.message)); }
        return data.result;
    }""", [model, method, args, kwargs or {}])


with Captura(M) as c:
    errors = []
    c.page.on('pageerror', lambda exc: errors.append(str(exc)))
    sites = rpc(c, 'project.project', 'search_read',
                [[('is_construction_site', '=', True), ('name', 'ilike', 'DEMO')], ['id', 'name']],
                {'limit': 1, 'order': 'id'})
    if not sites:
        sites = rpc(c, 'project.project', 'search_read',
                    [[('is_construction_site', '=', True)], ['id', 'name']], {'limit': 1})
    site = sites[0]
    print('Obra:', site['name'])
    action = rpc(c, 'project.project', 'action_construction_open_spreadsheet', [[site['id']]])
    c.page.evaluate("""(action) => odoo.__WOWL_DEBUG__.root.env.services.action.doAction(action)""",
                    action)
    c.page.wait_for_selector('.o-spreadsheet', timeout=30000)
    c.esperar(2500)
    tabs = c.page.locator('.o-sheet-name').all_inner_texts()
    print('Pestañas:', tabs)
    assert 'ARBOL' in tabs and 'REFERENCIAS' in tabs, tabs
    c.foto('01-hoja-de-trabajo')
    c.page.get_by_text('REFERENCIAS', exact=True).first.click()
    c.esperar(2500)
    c.foto('02-referencias')
    c.page.get_by_text('ARBOL', exact=True).first.click()
    c.esperar(800)
    c.page.locator('.o-topbar-menu', has_text='Archivo').first.click()
    c.esperar(800)
    item = c.page.locator('.o-menu-item', has_text='Enviar al planificador')
    assert item.count(), 'falta el menú Enviar al planificador'
    c.foto('03-menu-enviar')
    item.first.click()
    c.page.wait_for_selector('.modal-content', timeout=20000)
    c.esperar(1500)
    title = c.page.locator('.modal-title').first.inner_text()
    print('Diálogo:', title)
    assert 'Importar maestro' in title, title
    c.foto('04-importar', selector='.modal-content')
    print('Errores JS:', errors)
    assert not errors, errors
    print('OK')
