#!/bin/bash
# uso: run_qa.sh <fase> [rollback]  — ejecuta fase_<fase>.py en odoo shell sobre ce20_db_ol
#   rollback: no deja registros (para depurar el script).
D=$(cd "$(dirname "$0")" && pwd)
F=$1; [ -f "$D/fase_$F.py" ] || { echo "no existe $D/fase_$F.py"; exit 2; }
export QA_FASE=$F QA_DIR=$D; [ "$2" = rollback ] && export QA_ROLLBACK=1
mkdir -p "$D/resultados"
cd /home/och/odoo/ce20
cat "$D/_qa.py" "$D/fase_$F.py" "$D/_fin.py" | timeout 1500 ./.venv/bin/python odoo-bin shell \
  -c cfg/ol_odoo.cfg -d ce20_db_ol --no-http --log-level=warn > "$D/resultados/$F.log" 2>&1
echo "rc=$?"; grep -E "^(RESUMEN|COMMIT|ROLLBACK)" "$D/resultados/$F.log"; grep -cE "^  FALLA" "$D/resultados/$F.log" | sed 's/^/fallas=/'
