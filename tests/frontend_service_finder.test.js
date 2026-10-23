const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const client = require(path.join(__dirname, "..", "static", "js", "service_finder_client.js"));

test("buildServicePayload trims optional requirements", () => {
    assert.deepEqual(
        client.buildServicePayload("  chennai t nagar ", " Event Planner ", ""),
        {
            location: "chennai t nagar",
            service_category: "Event Planner",
            special_requirements: "",
        }
    );
});

test("valid results response is classified as success", () => {
    const outcome = client.classifyServiceResponse({ ok: true, status: 200 }, {
        success: true,
        count: 1,
        query: { location: "T Nagar, Chennai" },
        results: [{ name: "Real Events", source_url: "https://real.example/" }],
    });
    assert.equal(outcome.state, "success");
    assert.equal(outcome.data.results.length, 1);
});

test("provider failure is an error, not an empty result", () => {
    const outcome = client.classifyServiceResponse({ ok: true, status: 200 }, {
        success: false,
        error: "Service search timed out. Please try again.",
        error_code: "provider_timeout",
        count: 0,
        results: [],
    });
    assert.equal(outcome.state, "error");
    assert.match(outcome.message, /timed out/i);
});

test("HTTP failure is an error even if the body is empty", () => {
    const outcome = client.classifyServiceResponse({ ok: false, status: 502 }, null);
    assert.equal(outcome.state, "error");
    assert.match(outcome.message, /HTTP 502/);
});

test("genuine empty result uses the backend message", () => {
    const outcome = client.classifyServiceResponse({ ok: true, status: 200 }, {
        success: true,
        count: 0,
        results: [],
        message: "Web results were found, but none matched Event Planner closely enough.",
    });
    assert.equal(outcome.state, "empty");
    assert.match(outcome.message, /none matched/i);
});

test("rendered cards escape content and allow only http(s) links", () => {
    const html = client.renderServiceResultsHtml({
        count: 1,
        query: { location: "T Nagar, Chennai" },
        timestamp: "10:00:00",
        results: [{
            name: "<script>alert(1)</script> Events",
            description: "Event planning <b>in T Nagar</b>",
            website: "javascript:alert(1)",
            source_url: "https://real.example/",
            phone: "044-23456789",
            location_relevance: "exact",
        }],
    });

    assert.match(html, /&lt;script&gt;/);
    assert.doesNotMatch(html, /<script>/);
    assert.doesNotMatch(html, /javascript:/);
    assert.match(html, /https:\/\/real\.example\//);
    assert.match(html, /Requested area/);
});

test("stale response detection compares request ids", () => {
    assert.equal(client.isStaleResponse(1, 2), true);
    assert.equal(client.isStaleResponse(2, 2), false);
});
