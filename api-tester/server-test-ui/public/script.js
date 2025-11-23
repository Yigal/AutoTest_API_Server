let endpoints = [];
let currentEndpoint = null;
let serverUrl = 'http://localhost:8011';
let testResults = [];

document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    await loadEndpoints();
    setupEventListeners();
});

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        serverUrl = config.serverUrl;
        document.getElementById('server-status').textContent = 'Connected';
        document.getElementById('server-status').classList.add('connected');
    } catch (error) {
        console.error('Failed to load config:', error);
        document.getElementById('server-status').textContent = 'Connection Failed';
    }
}

async function loadEndpoints() {
    try {
        const response = await fetch('/api/endpoints');
        endpoints = await response.json();
        renderEndpointList();
    } catch (error) {
        console.error('Failed to load endpoints:', error);
    }
}

function renderEndpointList() {
    const list = document.getElementById('endpoint-list');
    list.innerHTML = endpoints.map((ep, index) => `
        <div class="endpoint-item" onclick="selectEndpoint(${index})">
            <div class="endpoint-info">
                <span class="method ${ep.method}">${ep.method}</span>
                <span class="path">${ep.path}</span>
            </div>
            <button class="btn-sm btn-secondary debug-btn" onclick="openDebugger(event, ${index})" title="Debug this endpoint">
                Debug
            </button>
        </div>
    `).join('');
}

window.selectEndpoint = (index) => {
    currentEndpoint = endpoints[index];

    // Update active state in list
    document.querySelectorAll('.endpoint-item').forEach((el, i) => {
        el.classList.toggle('active', i === index);
    });

    renderRequestPanel();
    document.getElementById('send-btn').disabled = false;
};

window.openDebugger = (event, index) => {
    event.stopPropagation(); // Prevent triggering selectEndpoint twice (though selectEndpoint is called below)

    // Select the endpoint
    selectEndpoint(index);

    // Switch to Debugger tab
    document.querySelector('.nav-tab[data-target="debugger-view"]').click();
};

function renderRequestPanel() {
    const container = document.getElementById('request-config');
    const params = currentEndpoint.parameters || [];
    const body = currentEndpoint.body;

    let html = `
        <div class="form-group">
            <label>Description</label>
            <div style="color: var(--text-secondary); font-size: 0.875rem;">
                ${currentEndpoint.description || 'No description available'}
            </div>
        </div>
    `;

    if (params.length > 0) {
        html += `<h3>Parameters</h3>`;
        html += params.map(p => `
            <div class="form-group">
                <label>${p.name} (${p.in})</label>
                <input type="text" class="form-control param-input" 
                       data-name="${p.name}" 
                       data-in="${p.in}"
                       placeholder="${p.type || 'string'}">
            </div>
        `).join('');
    }

    if (body) {
        html += `
            <div class="form-group" id="body-section">
                <label>Request Body (${body.type})</label>
                <textarea class="form-control" id="request-body">{
  "example": "value"
}</textarea>
            </div>`;
    }

    container.innerHTML = html;

    // Body
    const bodyInput = document.getElementById('request-body');
    const requestConfig = document.getElementById('request-config');

    // Remove existing body params section if any
    const existingBodyParams = document.getElementById('body-params-section');
    if (existingBodyParams) existingBodyParams.remove();

    if (currentEndpoint.body) {
        document.getElementById('body-section').style.display = 'block';
        const example = currentEndpoint.body.example || { "example": "value" };
        bodyInput.value = JSON.stringify(example, null, 4);

        // Render Body Form if schema exists
        if (currentEndpoint.body.schema && currentEndpoint.body.schema.length > 0) {
            const bodyParamsSection = document.createElement('div');
            bodyParamsSection.id = 'body-params-section';
            bodyParamsSection.className = 'params-section';
            bodyParamsSection.innerHTML = '<h3>Body Parameters</h3>';

            currentEndpoint.body.schema.forEach(field => {
                const div = document.createElement('div');
                div.className = 'param-group';

                const label = document.createElement('label');
                label.textContent = field.name;
                if (field.required) {
                    const reqSpan = document.createElement('span');
                    reqSpan.className = 'required-mark';
                    reqSpan.textContent = '*';
                    label.appendChild(reqSpan);
                }

                const input = document.createElement('input');
                input.type = field.type === 'int' || field.type === 'float' ? 'number' : 'text';
                input.className = 'form-control param-input body-param-input';
                input.dataset.name = field.name;
                input.dataset.type = field.type;
                input.value = field.default || ''; // Set default value

                input.addEventListener('input', updateBodyFromForm);

                div.appendChild(label);
                div.appendChild(input);
                bodyParamsSection.appendChild(div);
            });

            // Insert before the raw JSON section
            document.getElementById('body-section').before(bodyParamsSection);
        }
    } else {
        document.getElementById('body-section').style.display = 'none';
        bodyInput.value = '';
    }
    updateCurlCommand(); // Update curl command after rendering panel
}

function updateBodyFromForm() {
    const inputs = document.querySelectorAll('.body-param-input');
    const body = {};

    inputs.forEach(input => {
        const name = input.dataset.name;
        const type = input.dataset.type;
        let value = input.value;

        if (type === 'int' || type === 'Integer') value = parseInt(value) || 0;
        else if (type === 'float' || type === 'Float') value = parseFloat(value) || 0.0;
        else if (type === 'bool' || type === 'Boolean') value = value === 'true';

        body[name] = value;
    });

    const bodyInput = document.getElementById('request-body');
    bodyInput.value = JSON.stringify(body, null, 4);
    updateCurlCommand();
}

function updateCurlCommand() {
    // Placeholder
}


// Debugger State
let traceLog = [];
let currentStep = 0;
let sourceLines = [];
let startLineOffset = 0;

function setupEventListeners() {
    document.getElementById('send-btn').addEventListener('click', sendRequest);

    document.getElementById('copy-curl-btn').addEventListener('click', () => {
        if (currentEndpoint) {
            navigator.clipboard.writeText(currentEndpoint.curl);
            const btn = document.getElementById('copy-curl-btn');
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = originalText, 2000);
        }
    });

    document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            // Re-render response view if content exists
            const content = document.getElementById('response-content').textContent;
            if (content) {
                try {
                    const json = JSON.parse(content);
                    displayResponse(json, e.target.dataset.view === 'pretty');
                } catch {
                    // If not JSON, just keep as is
                }
            }
        });
    });

    // Navigation Tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const targetId = e.target.dataset.target;

            // Update tabs
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');

            // Update views
            document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');

            // Auto-run tests if switching to auto view
            if (targetId === 'auto-view') {
                runAllTests();
            }

            // Fetch source if switching to debugger view
            if (targetId === 'debugger-view' && currentEndpoint) {
                fetchSourceCode();
            }
        });
    });

    // Debugger Controls
    document.getElementById('start-debug-btn').addEventListener('click', startDebug);
    document.getElementById('step-next-btn').addEventListener('click', () => {
        if (currentStep < traceLog.length - 1) {
            currentStep++;
            showTraceStep(currentStep);
        }
    });
    document.getElementById('step-prev-btn').addEventListener('click', () => {
        if (currentStep > 0) {
            currentStep--;
            showTraceStep(currentStep);
        }
    });
}

window.selectEndpoint = (index) => {
    try {
        currentEndpoint = endpoints[index];

        // Update active state in list
        document.querySelectorAll('.endpoint-item').forEach((el, i) => {
            el.classList.toggle('active', i === index);
        });

        renderRequestPanel();
        document.getElementById('send-btn').disabled = false;
    } catch (e) {
        console.error("Error in selectEndpoint:", e);
        alert("Error selecting endpoint: " + e.message);
    }
};

window.openDebugger = (event, index) => {
    try {
        event.stopPropagation(); // Prevent triggering selectEndpoint twice

        // Select the endpoint
        selectEndpoint(index);

        // Switch to Debugger tab
        const tab = document.querySelector('.nav-tab[data-target="debugger-view"]');
        if (tab) {
            // If already active, the click might not trigger the change event logic if we relied on that,
            // but here we rely on 'click' event which should fire.
            // However, to be safe and explicit:
            tab.click();

            // Explicitly fetch source code to ensure it updates even if tab was already active
            fetchSourceCode();
        } else {
            alert("Debugger tab not found!");
        }
    } catch (e) {
        console.error("Error in openDebugger:", e);
        alert("Error opening debugger: " + e.message);
    }
};

async function fetchSourceCode() {
    if (!currentEndpoint) return;

    const container = document.querySelector('.code-container pre');
    container.innerHTML = 'Loading source code...';
    container.style.counterReset = 'none'; // Reset counter while loading

    try {
        const response = await fetch('/api/proxy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                method: 'POST',
                url: `${serverUrl}/source`,
                headers: { 'Content-Type': 'application/json' },
                body: {
                    path: currentEndpoint.path,
                    method: currentEndpoint.method
                }
            })
        });

        const result = await response.json();

        if (result.data && result.data.source) {
            startLineOffset = result.data.start_line;
            renderSourceCode(result.data.source);
        } else if (result.error) {
            container.textContent = `Error loading source: ${result.error}`;
        } else {
            container.textContent = 'Source code not available';
        }

    } catch (error) {
        console.error('Failed to fetch source:', error);
        container.textContent = 'Failed to load source code';
    }
}

async function startDebug() {
    if (!currentEndpoint) {
        alert("Please select an endpoint first (from Manual view)");
        return;
    }

    const btn = document.getElementById('start-debug-btn');
    btn.disabled = true;
    btn.textContent = 'Debugging...';

    try {
        // Reuse logic to build request body from Manual view inputs
        // We need to ensure the manual view inputs are accessible or stored
        // For now, let's grab them from the DOM as if we were sending a request

        // Note: This assumes the user has configured the request in the Manual tab
        // A better UX might be to share the config panel, but for now we read from DOM

        let body = {};
        const bodyInput = document.getElementById('request-body');
        if (bodyInput && bodyInput.value) {
            try {
                body = JSON.parse(bodyInput.value);
            } catch (e) {
                alert("Invalid JSON in Manual view body. Please fix it there first.");
                return;
            }
        }

        const response = await fetch('/api/proxy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                method: 'POST', // Debug endpoint is POST
                url: `${serverUrl}/debug`,
                headers: { 'Content-Type': 'application/json' },
                body: {
                    path: currentEndpoint.path,
                    method: currentEndpoint.method,
                    body: body
                }
            })
        });

        const result = await response.json();

        if (result.data && result.data.trace) {
            traceLog = result.data.trace;
            const sourceCode = result.data.source;
            startLineOffset = result.data.start_line;

            renderSourceCode(sourceCode);

            if (traceLog.length > 0) {
                currentStep = 0;
                showTraceStep(0);

                document.getElementById('step-prev-btn').disabled = false;
                document.getElementById('step-next-btn').disabled = false;
            } else {
                alert("No trace captured. Function might be empty or not traced.");
            }
        } else if (result.error) {
            alert(`Debug Error: ${result.error}`);
        } else if (result.data && result.data.error) {
            alert(`Debug Error: ${result.data.error}`);
        }

    } catch (error) {
        console.error(error);
        alert("Failed to start debugger");
    } finally {
        btn.disabled = false;
        btn.textContent = 'Start Debug';
    }
}

function renderSourceCode(code) {
    const container = document.querySelector('.code-container pre');
    container.innerHTML = ''; // Clear

    sourceLines = code.split('\n');

    sourceLines.forEach((line, index) => {
        const lineDiv = document.createElement('div');
        lineDiv.className = 'code-line';
        lineDiv.id = `code-line-${index + startLineOffset}`;
        lineDiv.textContent = line;
        // Adjust line number counter to match actual file line if possible, 
        // but CSS counters start from 1. We might need to set style counter-reset.
        // For simplicity, we just show relative lines or try to match.
        // Let's just use the CSS counter for now, which is 1-based relative to the snippet.
        container.appendChild(lineDiv);
    });

    // Reset counter to start from startLineOffset
    container.style.counterReset = `line ${startLineOffset - 1}`;
}

function showTraceStep(index) {
    const step = traceLog[index];

    // Update Counter
    document.getElementById('step-counter').textContent = `Step ${index + 1} / ${traceLog.length}`;

    // Highlight Line
    document.querySelectorAll('.code-line').forEach(el => el.classList.remove('active-line'));
    const activeLine = document.getElementById(`code-line-${step.line}`);
    if (activeLine) {
        activeLine.classList.add('active-line');
        activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Update Variables
    const varsBody = document.getElementById('vars-body');
    varsBody.innerHTML = '';

    if (step.locals) {
        for (const [name, value] of Object.entries(step.locals)) {
            let displayValue = value;
            if (typeof value === 'object' && value !== null) {
                displayValue = `<pre style="margin: 0; white-space: pre-wrap;">${JSON.stringify(value, null, 2)}</pre>`;
            } else if (typeof value === 'string') {
                displayValue = `"${value}"`;
            }

            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="vertical-align: top; font-family: var(--font-mono); color: var(--accent-color);">${name}</td>
                <td style="font-family: var(--font-mono);">${displayValue}</td>
            `;
            varsBody.appendChild(row);
        }
    }

    // Update Buttons
    document.getElementById('step-prev-btn').disabled = index === 0;
    document.getElementById('step-next-btn').disabled = index === traceLog.length - 1;
}

async function runAllTests() {
    const tbody = document.getElementById('results-body');
    const statsDiv = document.getElementById('runner-stats');

    tbody.innerHTML = '';
    statsDiv.style.display = 'flex';
    testResults = []; // Clear previous results

    let stats = { total: endpoints.length, passed: 0, failed: 0 };
    updateStats(stats);

    for (let i = 0; i < endpoints.length; i++) {
        const ep = endpoints[i];
        const startTime = performance.now();
        let status = 'Pending';
        let statusCode = '-';
        let isSuccess = false;
        let responseData = null;

        try {
            // Construct URL with default values
            let url = `${serverUrl}${ep.path}`;
            const queryParams = new URLSearchParams();

            if (ep.parameters) {
                ep.parameters.forEach(p => {
                    if (p.in === 'path') {
                        url = url.replace(`{${p.name}}`, '1'); // Default ID
                    } else if (p.in === 'query') {
                        queryParams.append(p.name, 'test'); // Default query
                    }
                });
            }

            if (queryParams.toString()) {
                url += `?${queryParams.toString()}`;
            }

            // Construct Body
            let body = {};
            if (ep.body) {
                body = ep.body.example || { "example": "test" };
            }

            const response = await fetch('/api/proxy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    method: ep.method,
                    url: url,
                    headers: { 'Content-Type': 'application/json' },
                    body: body
                })
            });

            const result = await response.json();
            statusCode = result.status || response.status;
            isSuccess = statusCode >= 200 && statusCode < 300;
            responseData = result.data || result.error;

        } catch (error) {
            statusCode = 'Error';
            isSuccess = false;
            responseData = error.message;
        }

        const endTime = performance.now();
        const duration = Math.round(endTime - startTime);

        // Store Result
        testResults.push({
            endpoint: ep,
            status: statusCode,
            time: duration,
            success: isSuccess,
            response: responseData
        });

        // Update Stats
        if (isSuccess) stats.passed++; else stats.failed++;
        updateStats(stats);

        // Add Row
        const rowId = `test-row-${i}`;
        const detailsId = `test-details-${i}`;

        const row = document.createElement('tr');
        row.id = rowId;
        row.className = 'test-row';
        row.onclick = () => toggleTestDetails(i);
        row.innerHTML = `
            <td><span class="method ${ep.method}">${ep.method}</span></td>
            <td style="font-family: var(--font-mono);">${ep.path}</td>
            <td><span class="status-badge-cell ${isSuccess ? 'status-success' : 'status-error'}">${statusCode}</span></td>
            <td>${duration}ms</td>
            <td>
                <span style="margin-right: 0.5rem;">${isSuccess ? 'Pass' : 'Fail'}</span>
                <span class="expand-icon">▼</span>
            </td>
        `;
        tbody.appendChild(row);

        // Add Details Row
        const detailsRow = document.createElement('tr');
        detailsRow.id = detailsId;
        detailsRow.className = 'test-details-row';
        detailsRow.style.display = 'none';

        const responseContent = typeof responseData === 'object'
            ? syntaxHighlight(JSON.stringify(responseData, null, 2))
            : responseData;

        detailsRow.innerHTML = `
            <td colspan="5">
                <div class="details-content">
                    <div class="response-meta" style="margin-bottom: 0.5rem; padding: 0;">
                        <span class="meta-item">Status: <span style="color: ${isSuccess ? 'var(--success)' : 'var(--error)'}">${statusCode}</span></span>
                        <span class="meta-item">Time: <span>${duration}ms</span></span>
                    </div>
                    <pre>${responseContent}</pre>
                </div>
            </td>
        `;
        tbody.appendChild(detailsRow);
    }
}

window.toggleTestDetails = (index) => {
    const detailsRow = document.getElementById(`test-details-${index}`);
    const row = document.getElementById(`test-row-${index}`);
    const icon = row.querySelector('.expand-icon');

    if (detailsRow.style.display === 'none') {
        detailsRow.style.display = 'table-row';
        row.classList.add('expanded');
        icon.style.transform = 'rotate(180deg)';
    } else {
        detailsRow.style.display = 'none';
        row.classList.remove('expanded');
        icon.style.transform = 'rotate(0deg)';
    }
};

function updateStats(stats) {
    document.getElementById('stat-total').textContent = stats.total;
    document.getElementById('stat-passed').textContent = stats.passed;
    document.getElementById('stat-failed').textContent = stats.failed;
}

async function sendRequest() {
    if (!currentEndpoint) return;

    const btn = document.getElementById('send-btn');
    btn.disabled = true;
    btn.textContent = 'Sending...';

    const startTime = performance.now();

    try {
        // Build URL
        let url = `${serverUrl}${currentEndpoint.path}`;

        // Handle Path Params
        const inputs = document.querySelectorAll('.param-input');
        const queryParams = new URLSearchParams();

        inputs.forEach(input => {
            const name = input.dataset.name;
            const value = input.value;
            const type = input.dataset.in;

            if (value) {
                if (type === 'path') {
                    url = url.replace(`{${name}}`, value);
                } else if (type === 'query') {
                    queryParams.append(name, value);
                }
            }
        });

        if (queryParams.toString()) {
            url += `?${queryParams.toString()}`;
        }

        // Prepare Options
        const options = {
            method: currentEndpoint.method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        let requestBody = null;
        const bodyInput = document.getElementById('request-body'); // Changed from request-body-input
        if (bodyInput) {
            try {
                requestBody = JSON.parse(bodyInput.value);
            } catch (e) {
                alert('Invalid JSON in request body');
                btn.disabled = false;
                btn.textContent = 'Send Request';
                return;
            }
        }

        // Use Proxy to avoid CORS
        const proxyResponse = await fetch('/api/proxy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                method: currentEndpoint.method,
                url: url,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: requestBody
            })
        });

        const result = await proxyResponse.json();
        const endTime = performance.now();

        // Update Meta
        document.getElementById('status-code').textContent = result.status || proxyResponse.status;
        document.getElementById('status-code').style.color = (result.status >= 200 && result.status < 300) ? 'var(--success)' : 'var(--error)';
        document.getElementById('response-time').textContent = `${Math.round(endTime - startTime)}ms`;

        // Handle Content
        if (result.data) {
            if (typeof result.data === 'object') {
                displayResponse(result.data, true);
            } else {
                document.getElementById('response-content').textContent = result.data;
            }
        } else if (result.error) {
            document.getElementById('response-content').textContent = `Proxy Error: ${result.error}`;
        }

    } catch (error) {
        document.getElementById('response-content').textContent = `Error: ${error.message}`;
        document.getElementById('status-code').textContent = 'Error';
        document.getElementById('status-code').style.color = 'var(--error)';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Send Request';
    }
}

function displayResponse(data, pretty) {
    const container = document.getElementById('response-content');
    if (pretty) {
        container.innerHTML = syntaxHighlight(JSON.stringify(data, null, 2));
    } else {
        container.textContent = JSON.stringify(data);
    }
}

function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}
