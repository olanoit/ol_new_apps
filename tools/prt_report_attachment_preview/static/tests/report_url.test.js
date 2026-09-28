import {describe, expect, test} from "@odoo/hoot";
import {makeMockEnv, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {user} from "@web/core/user";
import {_getReportUrl} from "@prt_report_attachment_preview/js/tools.esm";

describe.current.tags("headless");

function contextOf(url) {
    return JSON.parse(new URL(url).searchParams.get("context"));
}

test("html fallback takes the user context from @web/core/user", async () => {
    // Odoo 19 has no "user" service: env.services.user used to be undefined
    // here and the HTML fallback threw a TypeError.
    const env = await makeMockEnv();
    patchWithCleanup(user, {
        get context() {
            return {lang: "es_PE", tz: "America/Lima"};
        },
    });
    const url = _getReportUrl(
        {report_name: "base.report_irmodulereference", context: {active_ids: [3, 4]}},
        "html",
        env
    );
    expect(new URL(url).pathname).toBe("/report/html/base.report_irmodulereference/3,4");
    expect(contextOf(url).lang).toBe("es_PE");
});

test("pdf keeps the action context, like the core download", async () => {
    const env = await makeMockEnv();
    const url = _getReportUrl(
        {report_name: "base.report_irmodulereference", context: {active_ids: [3], my_key: 1}},
        "pdf",
        env
    );
    expect(contextOf(url).my_key).toBe(1);
});
