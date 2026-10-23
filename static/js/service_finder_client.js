/* ===================================================
   SmartBot - Service Finder client helpers
   Pure functions shared by the browser and Node tests.
   =================================================== */
(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.SmartBotServiceFinder = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    function buildServicePayload(location, category, requirements) {
        return {
            location: String(location || "").trim(),
            service_category: String(category || "").trim(),
            special_requirements: String(requirements || "").trim(),
        };
    }

    function isStaleResponse(requestId, currentRequestId) {
        return requestId !== currentRequestId;
    }

    function classifyServiceResponse(response, data) {
        const ok = !!(response && response.ok);
        const status = response && response.status;

        if (!ok) {
            const message = (data && (data.error || data.message))
                || (status ? `Service search failed (HTTP ${status}). Please try again.`
                           : "Service search is temporarily unavailable. Please try again.");
            return { state: "error", message: String(message), data: data || null };
        }

        if (!data || typeof data !== "object") {
            return {
                state: "error",
                message: "Service search returned an invalid response. Please try again.",
                data: null,
            };
        }

        if (data.success === false) {
            return {
                state: "error",
                message: String(data.error || data.message
                    || "Service search is temporarily unavailable. Please try again."),
                data,
            };
        }

        const results = Array.isArray(data.results) ? data.results : [];
        if (results.length === 0) {
            return {
                state: "empty",
                message: String(data.message
                    || "No matching services were found for this search."),
                data,
            };
        }

        return { state: "success", message: "", data };
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function safeUrl(value) {
        const raw = String(value || "").trim();
        if (!raw) return "";
        try {
            const parsed = new URL(raw, "https://invalid.local");
            if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return "";
            return raw;
        } catch {
            return "";
        }
    }

    function relevanceLabel(value) {
        if (value === "exact") return "Requested area";
        if (value === "nearby") return "Nearby area";
        if (value === "city") return "City-wide";
        return "";
    }

    function renderServiceResultsHtml(data) {
        const results = Array.isArray(data && data.results) ? data.results : [];
        const count = Number.isFinite(data && data.count) ? data.count : results.length;
        const loc = (data && data.query && data.query.location)
            || (data && data.location)
            || "";

        let html = `<div class="service-results-header" style="font-size:14px;color:var(--text-secondary);margin-bottom:12px;">
            <strong>${count} matching service${count !== 1 ? "s" : ""}</strong> found near ${escapeHtml(loc)}
        </div>`;

        results.forEach(service => {
            const ratingHtml = service.rating
                ? `<span class="star">&#9733;</span> ${escapeHtml(service.rating)}`
                : "";
            const addressRow = service.address
                ? `<div class="meta-row"><span class="meta-icon">&#128205;</span><span>${escapeHtml(service.address)}</span></div>`
                : "";
            const phoneRow = service.phone
                ? `<div class="meta-row"><span class="meta-icon">&#128222;</span><span>${escapeHtml(service.phone)}</span></div>`
                : "";
            const descRow = service.description
                ? `<div class="meta-row service-card-desc"><span>${escapeHtml(service.description)}</span></div>`
                : "";
            const relevance = relevanceLabel(service.location_relevance);
            const relevanceRow = relevance
                ? `<div class="meta-row"><span class="meta-icon">&#128506;</span><span>${escapeHtml(relevance)}</span></div>`
                : "";

            const website = safeUrl(service.website);
            const sourceUrl = safeUrl(service.source_url);
            const phone = String(service.phone || "").trim();

            let actionsHtml = "";
            if (website) actionsHtml += `<a href="${escapeHtml(website)}" target="_blank" rel="noopener" class="secondary">&#127760; Website</a>`;
            if (phone) actionsHtml += `<a href="tel:${escapeHtml(phone)}" class="secondary">&#128222; Call</a>`;
            if (sourceUrl && sourceUrl !== website) actionsHtml += `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener" class="secondary">&#128279; View Source</a>`;

            html += `
            <div class="service-card">
                <div class="service-card-header">
                    <div class="service-card-name">${escapeHtml(service.name)}</div>
                    <div class="service-card-rating">${ratingHtml}</div>
                </div>
                <div class="service-card-meta">
                    ${relevanceRow}
                    ${addressRow}
                    ${phoneRow}
                    ${descRow}
                </div>
                <div class="service-card-actions">${actionsHtml}</div>
            </div>`;
        });

        if (data && data.timestamp) {
            html += `<div class="service-timestamp">Web results fetched at ${escapeHtml(data.timestamp)}</div>`;
        }

        return html;
    }

    return {
        buildServicePayload,
        classifyServiceResponse,
        isStaleResponse,
        renderServiceResultsHtml,
        escapeHtml,
        safeUrl,
    };
});
