#!/bin/bash
# Batería de pruebas unitarias, módulo a módulo, de la localización peruana.
#
#   docs/validacion/pruebas/run_tests.sh al_account_base al_l10n_pe_ple ...
#
# Variables de entorno:
#   DB      base sobre la que se ejecuta (por defecto ol_pe_v19_qa, un CLON:
#           --test-enable actualiza el módulo y reescribe sus datos XML).
#   ODOO    raíz del servidor Odoo.
#   LOGS    directorio de logs (uno por módulo + RESUMEN.txt).
set -u
ODOO=${ODOO:-/home/och/odoo/ce19}
CFG=${CFG:-$ODOO/cfg/my/pe.cfg}
DB=${DB:-ol_pe_v19_qa}
LOGS=${LOGS:-/tmp/odoo_tests_pe}
PYTHON=${PYTHON:-$ODOO/.venv/bin/python3}

mkdir -p "$LOGS"
: > "$LOGS/RESUMEN.txt"
cd "$ODOO" || exit 1

for m in "$@"; do
  start=$(date +%s)
  timeout 1200 "$PYTHON" odoo-bin -c "$CFG" -d "$DB" --no-http --stop-after-init \
      -u "$m" --test-enable --test-tags "/$m" --log-level=test \
      > "$LOGS/$m.log" 2>&1
  rc=$?
  end=$(date +%s)
  res=$(grep -E "odoo.tests.result:" "$LOGS/$m.log" | tail -1 | sed 's/.*result: //')
  [ -z "$res" ] && res="SIN RESULTADO (rc=$rc)"
  echo "$m | rc=$rc | $((end-start))s | $res" | tee -a "$LOGS/RESUMEN.txt"
done
echo "=== FIN ===" | tee -a "$LOGS/RESUMEN.txt"
