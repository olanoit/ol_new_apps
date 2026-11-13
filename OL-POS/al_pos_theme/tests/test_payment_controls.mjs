import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { SourceTextModule, SyntheticModule, createContext } from "node:vm";

// Pruebas de los medios de pago de js/payment_screen_patch.js sin Odoo:
// evalúa el módulo completo y sólo sustituye los imports del entorno.
// No efectúa transacciones ni invoca servicios de terminales.
//
//   node --experimental-vm-modules --test OL-POS/al_pos_theme/tests/test_payment_controls.mjs
//
// (desde la raíz del repositorio). No reemplaza las pruebas de Odoo.
class PaymentScreen {}
const context = createContext({});
const imports = {
    "@web/core/utils/patch": { patch: (target, values) => Object.defineProperties(target, Object.getOwnPropertyDescriptors(values)) },
    "@web/core/l10n/translation": { _t: (text, value) => text.replace("%s", value) },
    "@point_of_sale/app/screens/payment_screen/payment_screen": { PaymentScreen },
};
const source = readFileSync(new URL("../static/src/js/payment_screen_patch.js", import.meta.url), "utf8");
const module = new SourceTextModule(source, { context });
await module.link((specifier) => {
    const values = imports[specifier];
    if (!values) throw new Error(`Unexpected dependency: ${specifier}`);
    return new SyntheticModule(Object.keys(values), function () {
        for (const [name, value] of Object.entries(values)) this.setExport(name, value);
    }, { context });
});
await module.evaluate();

const card = { id: 1, name: "Tarjeta" };
const cash = { id: 2, name: "Efectivo" };
function line(uuid, method, status = false, amount = 100) {
    return { uuid, payment_method_id: method, getPaymentStatus: () => status, getAmount: () => amount };
}
function screen(lines) {
    const result = new PaymentScreen();
    result.currentOrder = {
        state: "draft",
        remainingDue: 0,
        // Moneda sin decimales: precisión 1, como `res.currency.isPositive` nativo.
        currency: { isPositive: (amount) => Math.round(amount) > 0 },
        electronicPaymentInProgress: () => result.paymentLines.some((payment) => {
            const status = payment.getPaymentStatus();
            return status && !["done", "reversed"].includes(status);
        }),
    };
    result.pos = { paymentTerminalInProgress: false };
    result.paymentLines = lines;
    result.deleted = [];
    result.added = [];
    result.messages = [];
    result.notification = { add: (message) => result.messages.push(message) };
    result.addNewPaymentLine = async (method) => {
        result.added.push(method.id);
        result.paymentLines.push(line("new-" + result.added.length, method));
        return true;
    };
    result.deletePaymentLine = (uuid) => {
        result.deleted.push(uuid);
        result.paymentLines = result.paymentLines.filter((payment) => payment.uuid !== uuid);
    };
    return result;
}

test("la × quita sólo las líneas sin procesar de ese medio, con el borrado nativo", () => {
    const page = screen([line("card-a", card), line("cash", cash), line("card-b", card, "retry")]);
    page.alptClearMethod(card);
    assert.deepEqual(page.deleted, ["card-a", "card-b"]);
    assert.deepEqual(page.paymentLines.map((payment) => payment.uuid), ["cash"]);
    assert.equal(page.alptCanClearMethod(card), false);
    page.alptClearMethod(card);
    assert.deepEqual(page.deleted, ["card-a", "card-b"]);
});

test("un pago de terminal pendiente se puede quitar antes de procesarlo", () => {
    const page = screen([line("pending", card, "pending")]);
    assert.equal(page.alptCanClearMethod(card), true);
    page.alptClearMethod(card);
    assert.deepEqual(page.deleted, ["pending"]);
});

for (const status of ["done", "reversed", "waiting", "waitingCard", "waitingCapture", "waitingCancel", "timeout", "force_done", "unknown"] ) {
    test(`la × rechaza ${status}, también mezclado con líneas del mismo medio`, () => {
        const page = screen([line("editable", card), line("protected", card, status)]);
        assert.equal(page.alptCanClearMethod(card), false);
        page.alptClearMethod(card);
        assert.deepEqual(page.deleted, []);
    });
}

test("la transacción en curso se vuelve a comprobar al hacer clic", () => {
    const page = screen([line("card", card)]);
    assert.equal(page.alptCanClearMethod(card), true);
    page.pos.paymentTerminalInProgress = true;
    page.alptClearMethod(card);
    assert.deepEqual(page.deleted, []);
});

test("en órdenes pagadas o anuladas no se quita nada", () => {
    for (const state of ["paid", "done", "cancel"]) {
        const page = screen([line("card", card)]);
        page.currentOrder.state = state;
        page.alptClearMethod(card);
        assert.deepEqual(page.deleted, []);
    }
});

test("la × nombra el medio para los lectores de pantalla", () => {
    const page = screen([]);
    assert.equal(page.alptClearMethodLabel(card), "Quitar los pagos con Tarjeta");
});

test("el segundo clic quita el medio y el tercero agrega una línea", async () => {
    const page = screen([]);
    await page.alptTogglePaymentMethod(cash);
    assert.equal(page.paymentLines.length, 1);
    await page.alptTogglePaymentMethod(cash);
    assert.equal(page.paymentLines.length, 0);
    assert.deepEqual(page.added, [cash.id]);
    await page.alptTogglePaymentMethod(cash);
    assert.equal(page.paymentLines.length, 1);
    assert.deepEqual(page.added, [cash.id, cash.id]);
});

test("el clic repetido quita las líneas en cero sin agregar otra", async () => {
    const page = screen([line("cash-full", cash), line("cash-zero-a", cash, false, 0), line("cash-zero-b", cash, false, 0)]);
    await page.alptTogglePaymentMethod(cash);
    assert.equal(page.paymentLines.length, 0);
    assert.deepEqual(page.deleted, ["cash-full", "cash-zero-a", "cash-zero-b"]);
    assert.deepEqual(page.added, []);
});

test("alternar un medio conserva el pago dividido con otros medios", async () => {
    const page = screen([line("cash", cash, false, 40), line("card", card, false, 60)]);
    await page.alptTogglePaymentMethod(cash);
    assert.deepEqual(page.paymentLines.map((payment) => payment.uuid), ["card"]);
    assert.equal(page.paymentLines[0].getAmount(), 60);
    assert.deepEqual(page.added, []);
});

for (const status of ["done", "reversed", "waiting", "waitingCard", "waitingCapture", "waitingCancel", "timeout", "force_done", "unknown"]) {
    test(`el clic no quita ni duplica un pago ${status}`, async () => {
        const page = screen([line("protected", card, status)]);
        await page.alptTogglePaymentMethod(card);
        assert.deepEqual(page.deleted, []);
        assert.deepEqual(page.added, []);
        assert.equal(page.messages.length, 1);
    });
}

test("una transacción en curso bloquea el clic antes de cambiar el estado", async () => {
    const page = screen([line("pending", card, "pending")]);
    page.pos.paymentTerminalInProgress = true;
    await page.alptTogglePaymentMethod(card);
    assert.deepEqual(page.deleted, []);
    assert.deepEqual(page.added, []);
});

test("los clics rápidos no duplican líneas mientras el core las crea", async () => {
    const page = screen([]);
    let finish;
    let calls = 0;
    page.addNewPaymentLine = () => {
        calls++;
        return new Promise((resolve) => { finish = resolve; });
    };
    const first = page.alptTogglePaymentMethod(cash);
    await page.alptTogglePaymentMethod(cash);
    assert.equal(calls, 1);
    finish(true);
    await first;
    assert.equal(page.alptPaymentMethodBusy, false);
});

test("un error del core libera el bloqueo para reintentar", async () => {
    const page = screen([]);
    page.addNewPaymentLine = async () => { throw new Error("Native failure"); };
    await assert.rejects(page.alptTogglePaymentMethod(cash), /Native failure/);
    assert.equal(page.alptPaymentMethodBusy, false);
});

test("el teclado alterna la tarjeta y deja la × con su propio manejo", async () => {
    const page = screen([]);
    const target = {};
    let prevented = 0;
    let stopped = 0;
    const event = { target, currentTarget: target, key: "Enter", preventDefault: () => prevented++, stopPropagation: () => stopped++ };
    await page.alptPaymentMethodKeydown(event, cash);
    assert.equal(page.paymentLines.length, 1);
    await page.alptPaymentMethodKeydown({ ...event, key: " " }, cash);
    assert.equal(page.paymentLines.length, 0);
    await page.alptPaymentMethodKeydown({ ...event, target: {} }, cash);
    assert.equal(page.paymentLines.length, 0);
    assert.equal(prevented, 2);
    assert.equal(stopped, 2);
});


test("con un cobro procesado y saldo pendiente agrega una línea y conserva el cobro", async () => {
    const processed = line("processed", card, "done", 60);
    const page = screen([processed, line("cash", cash, false, 10)]);
    page.currentOrder.remainingDue = 30;
    await page.alptTogglePaymentMethod(card);
    assert.deepEqual(page.added, [card.id]);
    assert.deepEqual(page.deleted, []);
    assert.deepEqual(page.messages, []);
    assert.equal(page.paymentLines[0], processed);
    assert.equal(processed.getAmount(), 60);
    assert.equal(processed.getPaymentStatus(), "done");
    assert.deepEqual(page.paymentLines.map((payment) => payment.uuid), ["processed", "cash", "new-1"]);
});

for (const due of [0, 0.4, -5]) {
    test(`con un cobro procesado y sin saldo (${due}) no agrega ni quita`, async () => {
        const page = screen([line("processed", card, "done")]);
        page.currentOrder.remainingDue = due;
        await page.alptTogglePaymentMethod(card);
        assert.deepEqual(page.added, []);
        assert.deepEqual(page.deleted, []);
        assert.equal(page.messages.length, 1);
    });
}

test("con la orden fuera de borrador no agrega líneas tras un cobro", async () => {
    for (const state of ["paid", "done", "cancel"]) {
        const page = screen([line("processed", card, "done")]);
        page.currentOrder.state = state;
        page.currentOrder.remainingDue = 50;
        await page.alptTogglePaymentMethod(card);
        assert.deepEqual(page.added, []);
        assert.deepEqual(page.deleted, []);
    }
});

test("una transacción en curso impide agregar tras un cobro procesado", async () => {
    const terminalBusy = screen([line("processed", card, "done")]);
    terminalBusy.currentOrder.remainingDue = 50;
    terminalBusy.pos.paymentTerminalInProgress = true;
    await terminalBusy.alptTogglePaymentMethod(card);
    assert.deepEqual(terminalBusy.added, []);

    const otherMethodWaiting = screen([line("processed", card, "done"), line("cash-terminal", cash, "waitingCard")]);
    otherMethodWaiting.currentOrder.remainingDue = 50;
    await otherMethodWaiting.alptTogglePaymentMethod(card);
    assert.deepEqual(otherMethodWaiting.added, []);
    assert.deepEqual(otherMethodWaiting.deleted, []);
});

for (const status of [false, "pending", "retry", "waiting", "waitingCard", "reversed", "force_done", "unknown"]) {
    test(`líneas cobradas mezcladas con ${status || "sin procesar"} no agregan ni quitan`, async () => {
        const page = screen([line("processed", card, "done"), line("other", card, status)]);
        page.currentOrder.remainingDue = 50;
        await page.alptTogglePaymentMethod(card);
        assert.deepEqual(page.added, []);
        assert.deepEqual(page.deleted, []);
        assert.equal(page.messages.length, 1);
    });
}

test("los cobros procesados sobreviven a clics repetidos tras cobrar el saldo", async () => {
    const processed = line("processed", card, "done", 60);
    const page = screen([processed]);
    page.currentOrder.remainingDue = 40;
    let finish;
    const nativeAdd = page.addNewPaymentLine;
    page.addNewPaymentLine = (method) => new Promise((resolve) => {
        finish = () => resolve(nativeAdd(method));
    });
    const first = page.alptTogglePaymentMethod(card);
    await page.alptTogglePaymentMethod(card);
    finish();
    await first;
    assert.deepEqual(page.added, [card.id]);
    await page.alptTogglePaymentMethod(card);
    assert.deepEqual(page.added, [card.id]);
    assert.deepEqual(page.deleted, []);
    assert.equal(page.paymentLines[0], processed);
    assert.equal(page.paymentLines.length, 2);
});

// --- Montos rápidos de efectivo ------------------------------------------------
// Los arreglos vienen de otro contexto de vm: se copian para compararlos.
const quickValues = (page) => Array.from(page.alptQuickAmounts, (quick) => quick.value);
function cashScreen({ due, bills, others = [], refund = false, method = { id: 9, is_cash_count: true } }) {
    const page = screen([]);
    const current = line("cash-line", method, false, 0);
    current.payment_method_id = method;
    page.selectedPaymentLine = current;
    page.isRefundOrder = refund;
    page.currentOrder.totalDue = due;
    page.currentOrder.payment_ids = [current, ...others];
    page.currentOrder.currency.round = (amount) => Math.round(amount * 100) / 100;
    page.pos.models = { "pos.bill": { getAll: () => bills.map((value) => ({ value })) } };
    page.env = { utils: { formatCurrency: (amount) => `S/ ${amount.toFixed(2)}` } };
    return page;
}

test("montos rápidos: exacto y redondeos a los billetes de la caja", () => {
    const page = cashScreen({ due: 37.5, bills: [0.1, 0.5, 1, 5, 10, 20, 50, 100, 200] });
    assert.deepEqual(quickValues(page), [37.5, 40, 50, 100]);
    assert.equal(page.alptQuickAmounts[0].label, "Exacto");
    assert.equal(page.alptQuickAmounts[1].label, "S/ 40.00");
});

test("montos rápidos: descuentan lo ya pagado con otros medios", () => {
    const card = line("card", { id: 1 }, "done", 20);
    const page = cashScreen({ due: 57.5, bills: [10, 20, 50, 100], others: [card] });
    assert.deepEqual(quickValues(page), [37.5, 40, 50, 100]);
});

test("montos rápidos: nada sin billetes, sin saldo, en devoluciones o sin efectivo", () => {
    assert.equal(cashScreen({ due: 37.5, bills: [] }).alptQuickAmounts.length, 0);
    assert.equal(cashScreen({ due: 0, bills: [10, 20] }).alptQuickAmounts.length, 0);
    assert.equal(cashScreen({ due: 37.5, bills: [10, 20], refund: true }).alptQuickAmounts.length, 0);
    const card = { id: 1, is_cash_count: false };
    assert.equal(cashScreen({ due: 37.5, bills: [10, 20], method: card }).alptQuickAmounts.length, 0);
});

test("montos rápidos: un monto que ya es billete no repite el exacto", () => {
    const page = cashScreen({ due: 50, bills: [10, 20, 50, 100] });
    assert.deepEqual(quickValues(page), [50, 60, 100]);
});

test("montos rápidos: se aplican por el mismo camino que el teclado", () => {
    const page = cashScreen({ due: 37.5, bills: [10, 50] });
    const calls = [];
    page.numberBuffer = { set: (value) => calls.push(["set", value]) };
    page.updateSelectedPaymentline = () => calls.push(["update"]);
    page.alptSetQuickAmount(40);
    assert.deepEqual(calls, [["set", "40"], ["update"]]);
});
