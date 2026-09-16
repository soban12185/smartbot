/* ===================================================
   SmartBot – main.js (Production SaaS)
   =================================================== */

document.addEventListener('DOMContentLoaded', () => {

    // ── DOM refs ──────────────────────────────────────
    const chatForm        = document.getElementById('chat-form');
    const chatInput       = document.getElementById('chat-input');
    const sendBtn         = document.getElementById('send-btn');
    const chatArea        = document.getElementById('chat-area');
    const messagesContainer = document.getElementById('messages-container');
    const welcomeState    = document.getElementById('welcome-state');
    const historyList     = document.getElementById('history-list');

    // Search
    const searchForm    = document.getElementById('search-form');
    const searchInput   = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');

    // PDF
    const pdfForm       = document.getElementById('pdf-form');
    const pdfDropZone   = document.getElementById('drop-zone');
    const pdfFileInput  = document.getElementById('pdf-file-input');
    const pdfSubmitBtn  = document.getElementById('pdf-submit-btn');

    // Services
    const servicesForm      = document.getElementById('services-form');
    const serviceLocation   = document.getElementById('service-location');
    const serviceCategory   = document.getElementById('service-category');
    const serviceRequirements = document.getElementById('service-requirements');
    const serviceSearchBtn  = document.getElementById('service-search-btn');
    const servicesResults   = document.getElementById('services-results');

    // Auth
    const btnLogin  = document.getElementById('btn-login');
    const btnSignup = document.getElementById('btn-signup');
    const loginForm   = document.getElementById('login-form');
    const signupForm  = document.getElementById('signup-form');
    const goSignup    = document.getElementById('go-signup');
    const goLogin     = document.getElementById('go-login');

    // Event Planner
    const eventForm       = document.getElementById('event-form');
    const eventResults    = document.getElementById('event-results');

    // Mobile sidebar
    const sidebar        = document.getElementById('sidebar');
    const menuToggle     = document.getElementById('menu-toggle');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    // State
    let isProcessing = false;
    let sessionId = localStorage.getItem('sb_session') || generateId();
    localStorage.setItem('sb_session', sessionId);
    let currentChatId = null;

    // ─────────────────────────────────────────────────
    //  INIT
    // ─────────────────────────────────────────────────
    loadHistory();
    setupNavigation();
    setupChat();
    setupSearch();
    setupPDF();
    setupServices();
    setupProductResearch();
    setupAuth();
    setupMobile();
    setupEventPlanner();

    // ─────────────────────────────────────────────────
    //  NAVIGATION  (sidebar tabs)
    // ─────────────────────────────────────────────────
    function setupNavigation() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                switchView(mode);
                if (window.innerWidth <= 768) closeSidebar();
            });
        });
    }

    function switchView(mode) {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const target = document.getElementById(`view-${mode}`);
        if (target) target.classList.add('active');
    }

    // ─────────────────────────────────────────────────
    //  CHAT
    // ─────────────────────────────────────────────────
    function setupChat() {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 180) + 'px';
            sendBtn.disabled = chatInput.value.trim() === '';
        });

        chatInput.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendBtn.disabled) chatForm.requestSubmit();
            }
        });

        chatForm.addEventListener('submit', handleChatSubmit);

        document.querySelectorAll('.chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const prompt = chip.dataset.prompt || chip.textContent.trim();
                chatInput.value = prompt;
                chatInput.dispatchEvent(new Event('input'));
                chatForm.requestSubmit();
            });
        });
    }

    async function handleChatSubmit(e) {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message || isProcessing) return;

        if (welcomeState) welcomeState.style.display = 'none';

        chatInput.value = '';
        chatInput.style.height = 'auto';
        sendBtn.disabled = true;

        appendUserMessage(message);

        const typingEl = appendTypingIndicator();
        isProcessing = true;

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: message, session_id: sessionId })
            });

            const data = await res.json();
            typingEl.remove();

            if (!res.ok) {
                const userName = localStorage.getItem('sb_user') || 'there';
                const errText = `Hello **${userName}**, I'm sorry — I encountered an error. Please try again.`;
                appendBotMessage(errText);
                saveHistory(message, errText);
            } else if (data.type === 'product_research') {
                appendProductResearchMessage(data);
                saveHistory(message, data.response || 'Product research results');
            } else {
                appendBotMessage(data.response, data.run_id);
                saveHistory(message, data.response);
            }

        } catch (err) {
            typingEl.remove();
            const userName = localStorage.getItem('sb_user') || 'there';
            const errText = `Hello **${userName}**, I'm sorry — I encountered an error. Please try again.`;
            appendBotMessage(errText);
            saveHistory(message, errText);
        } finally {
            isProcessing = false;
        }
    }

    // ── Message renderers ──────────────────────────
    function appendUserMessage(text) {
        const row = document.createElement('div');
        row.className = 'msg-row user';
        row.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
        messagesContainer.appendChild(row);
        scrollToBottom();
    }

    function appendBotMessage(text, runId) {
        const row = document.createElement('div');
        row.className = 'msg-row bot';
        const runIdAttr = runId ? `data-run-id="${escapeHtml(runId)}"` : '';
        row.innerHTML = `
            <div class="bot-logo" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="msg-body">
                <div class="msg-text">${formatMarkdown(text)}</div>
                <div class="msg-actions" ${runIdAttr}>
                    <button class="msg-action-btn" title="Copy" onclick="copyText(this, ${JSON.stringify(text)})">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                    <button class="msg-action-btn feedback-btn" title="Helpful" onclick="submitFeedback(this, 1)">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.3a2 2 0 0 0 2-1.7l1.4-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                    </button>
                    <button class="msg-action-btn feedback-btn" title="Not helpful" onclick="submitFeedback(this, 0)">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.7a2 2 0 0 0-2 1.7l-1.4 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h2.3A2 2 0 0 1 21.4 4v7a2 2 0 0 1-2 2H17"/></svg>
                    </button>
                </div>
            </div>
        `;
        messagesContainer.appendChild(row);
        scrollToBottom();
    }

    function appendProductResearchMessage(data) {
        const row = document.createElement('div');
        row.className = 'msg-row bot';

        let html = `
            <div class="bot-logo" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="msg-body">
                <div class="msg-text">${formatMarkdown(data.response || '')}</div>
        `;

        const products = data.products || [];
        const recommendation = data.recommendation || {};
        const localStores = data.local_stores || [];

        if (Object.keys(recommendation).length > 0) {
            html += `<div class="product-results-inline">`;
            const recLabels = {
                best_overall: '🏆 Best Overall',
                best_budget: '💰 Best Budget',
                best_performance: '⚡ Best Performance',
                best_value: '✅ Best Value',
            };
            for (const [key, label] of Object.entries(recLabels)) {
                const rec = recommendation[key];
                if (!rec || !rec.product) continue;
                const p = rec.product;
                html += `<div class="product-card-inline featured">`;
                html += `<div class="product-card-header"><span class="product-badge">${label}</span>`;
                if (p.rating) html += `<span class="product-rating">⭐ ${p.rating}</span>`;
                html += `</div>`;
                html += `<div class="product-card-name">${escapeHtml(p.name)}</div>`;
                if (p.price != null) html += `<div class="product-card-price">₹${Number(p.price).toLocaleString()}</div>`;
                if (p.store_name) html += `<div class="product-card-store">${escapeHtml(p.store_name)}</div>`;
                if (p.source_confidence) {
                    const confLabels = { high: 'Trusted', medium: 'Standard', low: 'Verify' };
                    html += `<div style="font-size:10px;color:var(--text-dim);margin:2px 0;">${confLabels[p.source_confidence] || ''}</div>`;
                }
                if (p.url) html += `<a href="${escapeHtml(p.url)}" target="_blank" class="product-link">View →</a>`;
                html += `</div>`;
            }
            html += `</div>`;
        }

        if (products.length > 0) {
            html += `<div class="product-results-inline">`;
            for (const p of products.slice(0, 6)) {
                html += `<div class="product-card-inline">`;
                html += `<div class="product-card-name">${escapeHtml(p.name)}</div>`;
                if (p.price != null) html += `<div class="product-card-price">₹${Number(p.price).toLocaleString()}</div>`;
                if (p.store_name) html += `<div class="product-card-store">${escapeHtml(p.store_name)}</div>`;
                if (p.url) html += `<a href="${escapeHtml(p.url)}" target="_blank" class="product-link">View →</a>`;
                html += `</div>`;
            }
            html += `</div>`;
        }

        html += `
                <div class="msg-actions">
                    <button class="msg-action-btn" title="Copy" onclick="copyText(this, ${JSON.stringify(data.response || '')})">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                </div>
            </div>
        `;

        row.innerHTML = html;
        messagesContainer.appendChild(row);
        scrollToBottom();
    }

    function appendTypingIndicator() {
        const row = document.createElement('div');
        row.className = 'typing-row';
        row.innerHTML = `
            <div class="bot-logo" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        messagesContainer.appendChild(row);
        scrollToBottom();
        return row;
    }

    function scrollToBottom() {
        chatArea.scrollTo({ top: chatArea.scrollHeight, behavior: 'smooth' });
    }

    // ─────────────────────────────────────────────────
    //  WEB SEARCH
    // ─────────────────────────────────────────────────
    function setupSearch() {
        if (!searchForm) return;
        searchForm.addEventListener('submit', async e => {
            e.preventDefault();
            const q = searchInput.value.trim();
            if (!q) return;

            searchResults.innerHTML = `<div class="loader-text">Searching the web...</div>`;

            try {
                const res  = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: q })
                });
                const data = await res.json();

                if (data.results && data.results.length) {
                    searchResults.innerHTML = data.results.map(r => `
                        <div class="result-card">
                            <a href="${r.link || '#'}" target="_blank" class="result-card-title">${r.title || 'Untitled'}</a>
                            <div class="result-card-url">${r.link || ''}</div>
                            <p class="result-card-snippet">${r.snippet || ''}</p>
                        </div>
                    `).join('');
                } else {
                    searchResults.innerHTML = `<div class="loader-text">No results found for "${escapeHtml(q)}".</div>`;
                }
            } catch {
                searchResults.innerHTML = `<div class="loader-text">Search failed. Please try again.</div>`;
            }
        });
    }

    // ─────────────────────────────────────────────────
    //  PDF UPLOAD & CONVERSATIONAL Q&A
    // ─────────────────────────────────────────────────
    function setupPDF() {
        if (!pdfDropZone) return;

        const pdfUploadState = document.getElementById('pdf-upload-state');
        const pdfChatState = document.getElementById('pdf-chat-state');
        const pdfChatForm = document.getElementById('pdf-chat-form');
        const pdfChatInput = document.getElementById('pdf-chat-input');
        const pdfSendBtn = document.getElementById('pdf-send-btn');
        const pdfChatArea = document.getElementById('pdf-chat-area');
        const pdfMessagesContainer = document.getElementById('pdf-messages-container');
        const pdfWelcome = document.getElementById('pdf-welcome');
        const pdfDocName = document.getElementById('pdf-doc-name');
        const pdfDocPages = document.getElementById('pdf-doc-pages');
        const pdfRemoveBtn = document.getElementById('pdf-remove-btn');
        const pdfSuggestions = document.getElementById('pdf-suggestions');

        let currentDocId = null;
        let isPdfProcessing = false;

        // Click to open file picker
        pdfDropZone.addEventListener('click', () => pdfFileInput.click());

        // File selected
        pdfFileInput.addEventListener('change', () => {
            if (pdfFileInput.files[0]) {
                pdfDropZone.querySelector('.drop-title').textContent = pdfFileInput.files[0].name;
                pdfSubmitBtn.disabled = false;
            }
        });

        // Drag & drop
        pdfDropZone.addEventListener('dragover', e => { e.preventDefault(); pdfDropZone.classList.add('dragover'); });
        pdfDropZone.addEventListener('dragleave', () => pdfDropZone.classList.remove('dragover'));
        pdfDropZone.addEventListener('drop', e => {
            e.preventDefault();
            pdfDropZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type === 'application/pdf') {
                const dt = new DataTransfer();
                dt.items.add(file);
                pdfFileInput.files = dt.files;
                pdfDropZone.querySelector('.drop-title').textContent = file.name;
                pdfSubmitBtn.disabled = false;
            }
        });

        // Upload form submit
        pdfForm.addEventListener('submit', async e => {
            e.preventDefault();
            if (!pdfFileInput.files[0]) return;

            pdfSubmitBtn.disabled = true;
            pdfSubmitBtn.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('file', pdfFileInput.files[0]);

            try {
                const res = await fetch('/api/pdf/summary', { method: 'POST', body: formData });
                const data = await res.json();
                if (!res.ok || data.error) {
                    pdfSubmitBtn.disabled = false;
                    pdfSubmitBtn.textContent = 'Analyze Document';
                    pdfDropZone.querySelector('.drop-title').textContent = data.error || 'Failed to analyze PDF.';
                    return;
                }

                currentDocId = data.doc_id;
                const s = data.summary;

                // Update document header
                pdfDocName.textContent = data.filename;
                pdfDocPages.textContent = `${s.total_pages} page${s.total_pages !== 1 ? 's' : ''} · Ready`;

                // Switch to chat view
                pdfUploadState.style.display = 'none';
                pdfChatState.style.display = 'flex';

            } catch {
                pdfSubmitBtn.disabled = false;
                pdfSubmitBtn.textContent = 'Analyze Document';
                pdfDropZone.querySelector('.drop-title').textContent = 'Failed to analyze PDF. Please try again.';
            }
        });

        // Remove document
        pdfRemoveBtn?.addEventListener('click', () => {
            currentDocId = null;
            pdfChatState.style.display = 'none';
            pdfUploadState.style.display = '';
            pdfMessagesContainer.innerHTML = '';
            pdfWelcome.style.display = '';
            pdfFileInput.value = '';
            pdfSubmitBtn.disabled = true;
            pdfSubmitBtn.textContent = 'Analyze Document';
            pdfDropZone.querySelector('.drop-title').textContent = 'Drop your PDF here or click to upload';
        });

        // Suggestion chips
        pdfSuggestions?.addEventListener('click', e => {
            const chip = e.target.closest('.pdf-suggestion-chip');
            if (!chip) return;
            const question = chip.dataset.question;
            if (question && pdfChatInput) {
                pdfChatInput.value = question;
                pdfChatInput.dispatchEvent(new Event('input'));
                pdfChatForm.requestSubmit();
            }
        });

        // Auto-grow textarea
        pdfChatInput?.addEventListener('input', () => {
            pdfChatInput.style.height = 'auto';
            pdfChatInput.style.height = Math.min(pdfChatInput.scrollHeight, 120) + 'px';
            pdfSendBtn.disabled = pdfChatInput.value.trim() === '';
        });

        // Enter to send, Shift+Enter for newline
        pdfChatInput?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!pdfSendBtn.disabled) pdfChatForm.requestSubmit();
            }
        });

        // Chat form submit
        pdfChatForm?.addEventListener('submit', async e => {
            e.preventDefault();
            const question = pdfChatInput.value.trim();
            if (!question || !currentDocId || isPdfProcessing) return;

            // Hide welcome, show messages
            pdfWelcome.style.display = 'none';
            pdfChatArea.style.paddingBottom = '120px';

            // Render user message
            appendPdfUserMessage(question);

            // Clear input
            pdfChatInput.value = '';
            pdfChatInput.style.height = 'auto';
            pdfSendBtn.disabled = true;

            // Show loading
            const loadingEl = appendPdfLoading();
            isPdfProcessing = true;

            try {
                const r = await fetch('/api/pdf/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: question, doc_id: currentDocId })
                });
                const d = await r.json();
                loadingEl.remove();

                if (d.error) {
                    appendPdfError(d.error, question);
                } else {
                    appendPdfBotMessage(d.answer, d);
                }
            } catch {
                loadingEl.remove();
                appendPdfError('Failed to search document. Please try again.', question);
            } finally {
                isPdfProcessing = false;
            }
        });
    }

    function appendPdfUserMessage(text) {
        const container = document.getElementById('pdf-messages-container');
        const row = document.createElement('div');
        row.className = 'pdf-msg-row user';
        row.innerHTML = `<div class="pdf-msg-bubble">${escapeHtml(text)}</div>`;
        container.appendChild(row);
        scrollPdfToBottom();
    }

    function appendPdfBotMessage(answer, metadata) {
        const container = document.getElementById('pdf-messages-container');
        const row = document.createElement('div');
        row.className = 'pdf-msg-row bot';

        let sourceHtml = '';
        if (metadata.confidence && metadata.best_page) {
            const methodLabel = metadata.method === 'semantic' ? 'AI Semantic' : 'Keyword';
            sourceHtml = `
                <div class="pdf-msg-source">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/></svg>
                    <span>Page ${metadata.best_page} · ${metadata.confidence}% match · ${methodLabel}</span>
                </div>`;
        }

        row.innerHTML = `
            <div class="pdf-msg-avatar" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="pdf-msg-body">
                <div class="pdf-msg-text">${escapeHtml(answer).replace(/\n\n/g, '<br><br>')}</div>
                ${sourceHtml}
            </div>
        `;
        container.appendChild(row);
        scrollPdfToBottom();
    }

    function appendPdfLoading() {
        const container = document.getElementById('pdf-messages-container');
        const row = document.createElement('div');
        row.className = 'pdf-msg-loading';
        row.innerHTML = `
            <div class="pdf-msg-avatar" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="pdf-loading-content">
                <div class="pdf-loading-dots">
                    <div class="pdf-loading-dot"></div>
                    <div class="pdf-loading-dot"></div>
                    <div class="pdf-loading-dot"></div>
                </div>
                <div class="pdf-loading-text">Searching the document...</div>
            </div>
        `;
        container.appendChild(row);
        scrollPdfToBottom();
        return row;
    }

    function appendPdfError(message, retryQuestion) {
        const container = document.getElementById('pdf-messages-container');
        const row = document.createElement('div');
        row.className = 'pdf-msg-error';
        row.innerHTML = `
            <div class="pdf-msg-avatar" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
            </div>
            <div class="pdf-error-content">
                <div class="pdf-error-text">${escapeHtml(message)}</div>
                <button class="pdf-retry-btn">Try Again</button>
            </div>
        `;
        container.appendChild(row);
        scrollPdfToBottom();

        row.querySelector('.pdf-retry-btn')?.addEventListener('click', () => {
            row.remove();
            if (retryQuestion) {
                const pdfChatInput = document.getElementById('pdf-chat-input');
                if (pdfChatInput) {
                    pdfChatInput.value = retryQuestion;
                    pdfChatInput.dispatchEvent(new Event('input'));
                    document.getElementById('pdf-chat-form')?.requestSubmit();
                }
            }
        });
    }

    function scrollPdfToBottom() {
        const area = document.getElementById('pdf-chat-area');
        if (area) area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' });
    }

    // ─────────────────────────────────────────────────
    //  SERVICES
    // ─────────────────────────────────────────────────
    function setupServices() {
        if (!servicesForm) return;

        servicesForm.addEventListener('submit', async e => {
            e.preventDefault();
            await searchServices();
        });
    }

    async function searchServices() {
        const location = (serviceLocation?.value || '').trim();
        const category = (serviceCategory?.value || '').trim();
        const requirements = (serviceRequirements?.value || '').trim();

        if (!location) {
            servicesResults.innerHTML = `<div class="loader-text">Please enter a location.</div>`;
            return;
        }
        if (!category) {
            servicesResults.innerHTML = `<div class="loader-text">Please select a service category.</div>`;
            return;
        }

        serviceSearchBtn.disabled = true;
        servicesResults.innerHTML = `<div class="loader-text">Searching for ${escapeHtml(category)} services in ${escapeHtml(location)}...</div>`;

        try {
            const res = await fetch('/api/services/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    location: location,
                    service_category: category,
                    special_requirements: requirements,
                }),
            });
            const data = await res.json();

            if (!res.ok || data.error) {
                servicesResults.innerHTML = `<div class="loader-text">${escapeHtml(data.error || 'Search failed. Please try again.')}</div>`;
                return;
            }

            if (!data.results || data.results.length === 0) {
                servicesResults.innerHTML = `<div class="loader-text">No matching services found in ${escapeHtml(location)} for your requirements.</div>`;
                return;
            }

            renderServiceResults(data);
        } catch (err) {
            servicesResults.innerHTML = `<div class="loader-text">Service search is temporarily unavailable. Please try again.</div>`;
        } finally {
            serviceSearchBtn.disabled = false;
        }
    }

    function renderServiceResults(data) {
        const { results, count, location, timestamp } = data;
        const loc = location || (data.query && data.query.location) || '';

        let html = `<div class="service-results-header" style="font-size:14px;color:var(--text-secondary);margin-bottom:12px;">
            <strong>${count} matching service${count !== 1 ? 's' : ''}</strong> found near ${escapeHtml(loc)}
        </div>`;

        results.forEach(s => {
            const ratingHtml = s.rating
                ? `<span class="star">★</span> ${s.rating}`
                : '';
            const addressRow = s.address
                ? `<div class="meta-row"><span class="meta-icon">📍</span><span>${escapeHtml(s.address)}</span></div>`
                : '';
            const phoneRow = s.phone
                ? `<div class="meta-row"><span class="meta-icon">📞</span><span>${escapeHtml(s.phone)}</span></div>`
                : '';
            const descRow = s.description
                ? `<div class="meta-row service-card-desc"><span>${escapeHtml(s.description)}</span></div>`
                : '';

            let actionsHtml = '';
            if (s.website) actionsHtml += `<a href="${escapeHtml(s.website)}" target="_blank" rel="noopener" class="secondary">🌐 Website</a>`;
            if (s.phone) actionsHtml += `<a href="tel:${escapeHtml(s.phone)}" class="secondary">📞 Call</a>`;
            if (s.source_url && s.source_url !== s.website) actionsHtml += `<a href="${escapeHtml(s.source_url)}" target="_blank" rel="noopener" class="secondary">🔗 View Source</a>`;

            html += `
            <div class="service-card">
                <div class="service-card-header">
                    <div class="service-card-name">${escapeHtml(s.name)}</div>
                    <div class="service-card-rating">${ratingHtml}</div>
                </div>
                <div class="service-card-meta">
                    ${addressRow}
                    ${phoneRow}
                    ${descRow}
                </div>
                <div class="service-card-actions">${actionsHtml}</div>
            </div>`;
        });

        if (timestamp) {
            html += `<div class="service-timestamp">Web results fetched at ${escapeHtml(timestamp)}</div>`;
        }

        servicesResults.innerHTML = html;
    }

    // ─────────────────────────────────────────────────
    //  PRODUCT RESEARCH
    // ─────────────────────────────────────────────────
    function setupProductResearch() {
        const productsForm = document.getElementById('products-form');
        const productsInput = document.getElementById('products-input');
        const productsResults = document.getElementById('products-results');
        if (!productsForm) return;

        productsForm.addEventListener('submit', async e => {
            e.preventDefault();
            const q = productsInput.value.trim();
            if (!q) return;

            productsResults.innerHTML = `<div class="loader-text">Researching products... This may take a moment.</div>`;

            try {
                const res = await fetch('/api/products/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: q })
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    productsResults.innerHTML = `<div class="loader-text">${escapeHtml(data.error || 'Product search failed.')}</div>`;
                    return;
                }

                renderProductResults(data, productsResults);
            } catch {
                productsResults.innerHTML = `<div class="loader-text">Product search failed. Please try again.</div>`;
            }
        });
    }

    function renderProductResults(data, container) {
        const products = data.products || [];
        const localStores = data.local_stores || [];
        const recommendation = data.recommendation || {};
        const request = data.request || {};

        let html = '';

        const budgetMax = request.budget_max;
        const brand = request.brand;
        const category = request.category || request.product_query;
        html += `<div class="product-summary">`;
        html += `<strong>Searching for:</strong> ${escapeHtml(category)}`;
        if (brand) html += ` | <strong>Brand:</strong> ${escapeHtml(brand)}`;
        if (budgetMax) html += ` | <strong>Budget:</strong> Under ₹${budgetMax.toLocaleString()}`;
        if (request.required_features && request.required_features.length) {
            html += ` | <strong>Features:</strong> ${escapeHtml(request.required_features.join(', '))}`;
        }
        html += `</div>`;

        if (products.length === 0 && localStores.length === 0) {
            html += `<div class="loader-text">I couldn't find any ${escapeHtml(category)}s matching your criteria from the available sources.</div>`;
            html += `<div class="loader-text" style="margin-top:8px;font-size:13px;color:var(--text-dim);">`;
            html += `<strong>Suggestions:</strong><br>`;
            html += `- Try searching for '${escapeHtml(brand ? brand + ' ' : '')}${escapeHtml(category)}' with different features<br>`;
            html += `- Broaden your budget range<br>`;
            if (brand) html += `- Check the official ${escapeHtml(brand)} website for the latest models`;
            html += `</div>`;
            container.innerHTML = html;
            return;
        }

        const recLabels = {
            best_overall: '🏆 Best Overall',
            best_budget: '💰 Best Budget',
            best_performance: '⚡ Best Performance',
            best_value: '✅ Best Value',
        };

        for (const [key, label] of Object.entries(recLabels)) {
            const rec = recommendation[key];
            if (!rec || !rec.product) continue;
            const p = rec.product;
            html += `<div class="product-card featured">`;
            html += `<div class="product-card-header">`;
            html += `<span class="product-badge">${label}</span>`;
            if (p.rating) html += `<span class="product-rating">⭐ ${p.rating}</span>`;
            html += `</div>`;
            html += `<div class="product-card-name">${escapeHtml(p.name)}</div>`;
            if (p.price != null) {
                html += `<div class="product-card-price">₹${Number(p.price).toLocaleString()}</div>`;
            }
            if (p.store_name) html += `<div class="product-card-store">${escapeHtml(p.store_name)}</div>`;
            if (p.source_confidence) {
                const confColors = { high: 'var(--success)', medium: 'var(--warning)', low: 'var(--text-dim)' };
                const confLabels = { high: 'Trusted source', medium: 'Standard source', low: 'Verify independently' };
                html += `<div style="font-size:11px;color:${confColors[p.source_confidence] || 'var(--text-dim)'};margin:4px 0;">`;
                html += `${confLabels[p.source_confidence] || p.source_confidence}`;
                html += `</div>`;
            }
            if (p.specifications && Object.keys(p.specifications).length) {
                html += `<div class="product-specs">`;
                for (const [k, v] of Object.entries(p.specifications)) {
                    html += `<span class="spec-tag">${escapeHtml(k)}: ${escapeHtml(v)}</span>`;
                }
                html += `</div>`;
            }
            if (rec.reasons && rec.reasons.length) {
                html += `<div class="product-reasons">`;
                for (const reason of rec.reasons) {
                    html += `<div class="reason-item">✓ ${escapeHtml(reason)}</div>`;
                }
                html += `</div>`;
            }
            if (p.url) html += `<a href="${escapeHtml(p.url)}" target="_blank" class="product-link">View Product →</a>`;
            html += `</div>`;
        }

        if (products.length > 0) {
            html += `<div class="product-section-title">All Products Found (${products.length})</div>`;
            html += `<div class="product-grid">`;
            for (const p of products.slice(0, 12)) {
                html += renderProductCard(p);
            }
            html += `</div>`;
        }

        if (localStores.length > 0) {
            html += `<div class="product-section-title">Local Stores</div>`;
            html += `<div class="local-stores-note">Local availability could not be verified. Contact the store before visiting.</div>`;
            html += `<div class="product-grid">`;
            for (const s of localStores.slice(0, 6)) {
                html += `<div class="product-card local">`;
                html += `<div class="product-card-name">${escapeHtml(s.name)}</div>`;
                if (s.location) html += `<div class="product-card-store">${escapeHtml(s.location)}</div>`;
                if (s.phone) html += `<div class="product-card-store">${escapeHtml(s.phone)}</div>`;
                if (s.url) html += `<a href="${escapeHtml(s.url)}" target="_blank" class="product-link">View Store →</a>`;
                html += `</div>`;
            }
            html += `</div>`;
        }

        container.innerHTML = html;
    }

    function renderProductCard(p) {
        let html = `<div class="product-card">`;
        html += `<div class="product-card-header">`;
        if (p.source_type === 'local') html += `<span class="product-source local">Local</span>`;
        else html += `<span class="product-source online">Online</span>`;
        if (p.rating) html += `<span class="product-rating">⭐ ${p.rating}</span>`;
        html += `</div>`;
        html += `<div class="product-card-name">${escapeHtml(p.name)}</div>`;
        if (p.price != null) {
            html += `<div class="product-card-price">₹${Number(p.price).toLocaleString()}`;
            if (p.original_price && p.original_price > p.price) {
                html += ` <span class="product-original-price">₹${Number(p.original_price).toLocaleString()}</span>`;
            }
            html += `</div>`;
        }
        if (p.store_name) html += `<div class="product-card-store">${escapeHtml(p.store_name)}</div>`;
        if (p.source_confidence) {
            const confColors = { high: 'var(--success)', medium: 'var(--warning)', low: 'var(--text-dim)' };
            const confLabels = { high: 'Trusted', medium: 'Standard', low: 'Verify' };
            html += `<div style="font-size:10px;color:${confColors[p.source_confidence] || 'var(--text-dim)'};margin:2px 0;">`;
            html += `${confLabels[p.source_confidence] || p.source_confidence}`;
            html += `</div>`;
        }
        if (p.specifications && Object.keys(p.specifications).length) {
            html += `<div class="product-specs">`;
            for (const [k, v] of Object.entries(p.specifications)) {
                html += `<span class="spec-tag">${escapeHtml(k)}: ${escapeHtml(v)}</span>`;
            }
            html += `</div>`;
        }
        if (p.url) html += `<a href="${escapeHtml(p.url)}" target="_blank" class="product-link">View →</a>`;
        html += `</div>`;
        return html;
    }

    // ─────────────────────────────────────────────────
    //  EVENT PLANNER
    // ─────────────────────────────────────────────────
    function setupEventPlanner() {
        if (!eventForm) return;
        eventForm.addEventListener('submit', async e => {
            e.preventDefault();
            if (!eventResults) return;

            const submitBtn = document.getElementById('event-submit-btn');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Planning...';
            eventResults.innerHTML = `<div class="loader-text">Planning your event...</div>`;

            const payload = {
                event_type: document.getElementById('event-type').value,
                date: document.getElementById('event-date').value,
                location: document.getElementById('event-city').value,
                exactlocation: document.getElementById('event-address').value,
                guest_count: parseInt(document.getElementById('event-guests').value) || 0,
                total_budget: parseFloat(document.getElementById('event-budget').value) || 0,
                special_requirements: document.getElementById('event-notes').value,
                use_dummy: document.getElementById('event-dummy-mode')?.checked || false
            };

            try {
                const res = await fetch('/api/event/plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (!res.ok || data.error) {
                    eventResults.innerHTML = `
                        <div class="result-card">
                            <span class="result-card-title">AI Event Planner</span>
                            <p class="result-card-snippet">${escapeHtml(data.error || 'Failed to generate plan.')}</p>
                        </div>`;
                } else {
                    eventResults.innerHTML = `
                        <div class="result-card">
                            <span class="result-card-title">Your Event Plan</span>
                            <p style="color:var(--accent);font-size:14px;margin-bottom:8px;">Estimated Cost Per Person: ₹${data.per_person ? data.per_person.toFixed(0) : 'N/A'}</p>
                            <p class="result-card-snippet" style="white-space:pre-wrap;">${formatMarkdown(data.response)}</p>
                        </div>`;
                }
            } catch {
                eventResults.innerHTML = `<div class="loader-text">Something went wrong. Please try again.</div>`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Generate Plan';
            }
        });
    }

    // ─────────────────────────────────────────────────
    //  AUTH MODALS
    // ─────────────────────────────────────────────────
    function showToast(msg, duration = 3000) {
        const t = document.getElementById('toast');
        if (!t) return;
        t.textContent = msg;
        t.classList.add('show');
        setTimeout(() => t.classList.remove('show'), duration);
    }

    function setLoggedInUser(name) {
        localStorage.setItem('sb_user', name);
        const nameEl = document.getElementById('sidebar-user-name');
        const planEl = document.getElementById('sidebar-user-plan');
        const avatarEl = document.querySelector('.user-avatar');
        if (nameEl) nameEl.textContent = name;
        if (planEl) planEl.textContent = 'Free plan';
        if (avatarEl) avatarEl.textContent = name.charAt(0).toUpperCase();

        document.getElementById('auth-logged-out').style.display = 'none';
        document.getElementById('auth-logged-in').style.display = 'flex';
        document.getElementById('topbar-username').textContent = name;

        document.getElementById('mobile-auth-logged-out').style.display = 'none';
        document.getElementById('mobile-auth-logged-in').style.display = 'flex';
        document.getElementById('mobile-topbar-username').textContent = name;
    }

    function clearLoggedInUser() {
        localStorage.removeItem('sb_user');
        localStorage.removeItem('sb_session');
        Object.keys(localStorage).forEach(key => {
            if (key === 'sb_history') localStorage.removeItem(key);
        });
        sessionId = generateId();
        localStorage.setItem('sb_session', sessionId);
        if (chatArea) chatArea.innerHTML = '';
        if (welcomeState) welcomeState.style.display = '';
        const nameEl = document.getElementById('sidebar-user-name');
        const planEl = document.getElementById('sidebar-user-plan');
        const avatarEl = document.querySelector('.user-avatar');
        if (nameEl) nameEl.textContent = 'SmartBot';
        if (planEl) planEl.textContent = 'Guest';
        if (avatarEl) avatarEl.textContent = 'S';

        document.getElementById('auth-logged-out').style.display = '';
        document.getElementById('auth-logged-in').style.display = 'none';
        document.getElementById('topbar-username').textContent = '';

        document.getElementById('mobile-auth-logged-out').style.display = '';
        document.getElementById('mobile-auth-logged-in').style.display = 'none';
        document.getElementById('mobile-topbar-username').textContent = '';
    }

    function getStoredUsers() {
        return JSON.parse(localStorage.getItem('sb_users') || '{}');
    }

    function setupAuth() {
        const existing = localStorage.getItem('sb_user');
        if (existing) setLoggedInUser(existing);

        btnLogin?.addEventListener('click',  () => {
            document.getElementById('login-error').className = 'auth-error';
            document.getElementById('login-error').textContent = '';
            openModal('modal-login');
        });
        document.getElementById('mobile-btn-login')?.addEventListener('click', () => {
            document.getElementById('login-error').className = 'auth-error';
            document.getElementById('login-error').textContent = '';
            openModal('modal-login');
        });
        btnSignup?.addEventListener('click', () => {
            document.getElementById('signup-error').className = 'auth-error';
            document.getElementById('signup-error').textContent = '';
            openModal('modal-signup');
        });
        document.getElementById('mobile-btn-signup')?.addEventListener('click', () => {
            document.getElementById('signup-error').className = 'auth-error';
            document.getElementById('signup-error').textContent = '';
            openModal('modal-signup');
        });

        document.getElementById('btn-logout')?.addEventListener('click', () => {
            clearLoggedInUser();
            showToast('Logged out successfully');
        });
        document.getElementById('mobile-btn-logout')?.addEventListener('click', () => {
            clearLoggedInUser();
            showToast('Logged out successfully');
        });

        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => closeModal(btn.dataset.close));
        });

        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', e => {
                if (e.target === overlay) closeModal(overlay.id);
            });
        });

        goSignup?.addEventListener('click', e => {
            e.preventDefault();
            closeModal('modal-login');
            openModal('modal-signup');
        });
        goLogin?.addEventListener('click', e => {
            e.preventDefault();
            closeModal('modal-signup');
            openModal('modal-login');
        });

        loginForm?.addEventListener('submit', e => {
            e.preventDefault();
            const errEl = document.getElementById('login-error');
            const email = document.getElementById('login-email').value.trim();
            const password = document.getElementById('login-password').value;
            const users = getStoredUsers();

            if (!users[email]) {
                errEl.className = 'auth-error error';
                errEl.textContent = 'No account found with this email.';
                return;
            }
            if (users[email].password !== password) {
                errEl.className = 'auth-error error';
                errEl.textContent = 'Incorrect password. Please try again.';
                return;
            }

            errEl.className = 'auth-error';
            closeModal('modal-login');
            setLoggedInUser(users[email].name);
            showToast('Welcome back, ' + users[email].name + '!');
            document.getElementById('login-form').reset();
        });

        signupForm?.addEventListener('submit', e => {
            e.preventDefault();
            const errEl = document.getElementById('signup-error');
            const name = document.getElementById('signup-name').value.trim();
            const email = document.getElementById('signup-email').value.trim().toLowerCase();
            const password = document.getElementById('signup-password').value;
            const users = getStoredUsers();

            if (users[email]) {
                errEl.className = 'auth-error error';
                errEl.textContent = 'An account with this email already exists.';
                return;
            }

            users[email] = { name, password };
            localStorage.setItem('sb_users', JSON.stringify(users));

            errEl.className = 'auth-error success';
            errEl.textContent = 'Account created! Please log in.';
            signupForm.reset();

            setTimeout(() => {
                closeModal('modal-signup');
                openModal('modal-login');
                document.getElementById('login-email').value = email;
                errEl.className = 'auth-error';
            }, 1200);
        });

        document.getElementById('user-card-btn')?.addEventListener('click', () => {
            const user = localStorage.getItem('sb_user');
            if (user) {
                clearLoggedInUser();
                showToast('Logged out successfully');
            }
        });
    }

    function openModal(id)  { document.getElementById(id)?.classList.add('open'); }
    function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }

    // ─────────────────────────────────────────────────
    //  MOBILE SIDEBAR
    // ─────────────────────────────────────────────────
    function setupMobile() {
        menuToggle?.addEventListener('click', () => {
            sidebar.classList.add('open');
            sidebarOverlay.classList.add('open');
            sidebarOverlay.setAttribute('aria-hidden', 'false');
        });
        sidebarOverlay?.addEventListener('click', closeSidebar);
    }

    function closeSidebar() {
        sidebar?.classList.remove('open');
        sidebarOverlay?.classList.remove('open');
        sidebarOverlay?.setAttribute('aria-hidden', 'true');
    }

    // ─────────────────────────────────────────────────
    //  CHAT HISTORY  (localStorage)
    // ─────────────────────────────────────────────────
    function loadHistory() {
        const history = getHistory();
        renderHistory(history);
    }

    function getHistory() {
        return JSON.parse(localStorage.getItem('sb_history') || '[]');
    }

    function saveHistory(message, response) {
        const history = getHistory();

        if (currentChatId) {
            const entry = history.find(h => h.id === currentChatId);
            if (entry) {
                entry.messages = entry.messages || [];
                entry.messages.push({ role: 'user', text: message });
                entry.messages.push({ role: 'bot', text: response });
                entry.title = entry.messages[0].text.length > 32 ? entry.messages[0].text.slice(0, 32) + '...' : entry.messages[0].text;
                localStorage.setItem('sb_history', JSON.stringify(history.slice(0, 50)));
                renderHistory(history);
                return;
            }
        }

        const title = message.length > 32 ? message.slice(0, 32) + '...' : message;
        const entry = { id: Date.now(), title, ts: new Date().toISOString(), messages: [{ role: 'user', text: message }, { role: 'bot', text: response }] };
        currentChatId = entry.id;
        history.unshift(entry);
        localStorage.setItem('sb_history', JSON.stringify(history.slice(0, 50)));
        renderHistory(history);
    }

    function renderHistory(history) {
        if (!historyList) return;
        historyList.innerHTML = history.map(item => `
            <div class="history-item" data-id="${item.id}" data-title="${escapeHtml(item.title)}" title="${escapeHtml(item.title)}" role="listitem">
                <span class="history-item-text">${escapeHtml(item.title)}</span>
                <button class="history-delete-btn" data-id="${item.id}" title="Delete" aria-label="Delete chat">&times;</button>
            </div>
        `).join('') || '<div style="padding:8px 12px;font-size:13px;color:var(--text-dim)">No chats yet</div>';

        historyList.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.history-delete-btn')) return;
                switchView('chat');
                if (window.innerWidth <= 768) closeSidebar();
                const chatId = parseInt(el.dataset.id);
                loadChatById(chatId);
            });
        });

        historyList.querySelectorAll('.history-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const chatId = parseInt(btn.dataset.id);
                deleteChatById(chatId);
            });
        });
    }

    function loadChatById(chatId) {
        const history = getHistory();
        const entry = history.find(h => h.id === chatId);
        if (!entry) return;

        currentChatId = chatId;
        messagesContainer.innerHTML = '';
        if (welcomeState) welcomeState.style.display = 'none';

        if (entry.messages && entry.messages.length) {
            entry.messages.forEach(msg => {
                if (msg.role === 'user') {
                    appendUserMessage(msg.text);
                } else {
                    appendBotMessage(msg.text);
                }
            });
        } else {
            appendUserMessage(entry.title);
            appendBotMessage('This is an older conversation. Messages were not saved. Please type a new question.');
        }
    }

    function deleteChatById(chatId) {
        const history = getHistory();
        const updated = history.filter(h => h.id !== chatId);
        localStorage.setItem('sb_history', JSON.stringify(updated));
        renderHistory(updated);

        messagesContainer.innerHTML = '';
        if (welcomeState) welcomeState.style.display = '';
    }

    // ─────────────────────────────────────────────────
    //  NEW CHAT
    // ─────────────────────────────────────────────────
    window.startNewChat = function () {
        messagesContainer.innerHTML = '';
        if (welcomeState) welcomeState.style.display = '';
        chatInput.value = '';
        chatInput.style.height = 'auto';
        sendBtn.disabled = true;
        currentChatId = null;
        sessionId = generateId();
        localStorage.setItem('sb_session', sessionId);
        switchView('chat');
        chatInput.focus();
        if (window.innerWidth <= 768) closeSidebar();
    };

    // ─────────────────────────────────────────────────
    //  COPY TEXT HELPER
    // ─────────────────────────────────────────────────
    window.copyText = async function (btn, text) {
        try {
            await navigator.clipboard.writeText(text);
            btn.title = 'Copied!';
            setTimeout(() => { btn.title = 'Copy'; }, 2000);
        } catch {}
    };

    // ─────────────────────────────────────────────────
    //  USER FEEDBACK
    // ─────────────────────────────────────────────────
    window.submitFeedback = async function (btn, score) {
        const actionsDiv = btn.closest('.msg-actions');
        if (!actionsDiv) return;

        const runId = actionsDiv.dataset.runId;
        if (!runId) {
            btn.title = 'No run ID';
            setTimeout(() => { btn.title = score === 1 ? 'Helpful' : 'Not helpful'; }, 2000);
            return;
        }

        try {
            const res = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ run_id: runId, score: score })
            });

            if (res.ok) {
                btn.title = 'Thanks!';
                btn.style.color = 'var(--success)';
                const feedbackBtns = actionsDiv.querySelectorAll('.feedback-btn');
                feedbackBtns.forEach(b => { b.disabled = true; b.style.opacity = '0.5'; });
            } else {
                btn.title = 'Failed to submit';
            }
        } catch {
            btn.title = 'Failed to submit';
        }

        setTimeout(() => { btn.title = score === 1 ? 'Helpful' : 'Not helpful'; }, 2000);
    };

    // ─────────────────────────────────────────────────
    //  UTILITIES
    // ─────────────────────────────────────────────────
    function escapeHtml(str) {
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function formatMarkdown(text) {
        return text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`(.+?)`/g, '<code style="background:var(--bg-input);padding:2px 6px;border-radius:4px;font-family:monospace">$1</code>')
            .replace(/\n/g, '<br>');
    }

    function generateId() {
        return 'sess_' + Math.random().toString(36).slice(2, 11);
    }
});
