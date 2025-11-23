const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const config = require('../config.json');

const app = express();
const PORT = config.testerPort || 8010;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const axios = require('axios');

// Endpoint to get the generated endpoints configuration
app.get('/api/endpoints', (req, res) => {
    const endpointsPath = path.join(__dirname, config.endpointsOutputFile || 'config/endpoints.json');

    fs.readFile(endpointsPath, 'utf8', (err, data) => {
        if (err) {
            console.error('Error reading endpoints file:', err);
            return res.status(500).json({ error: 'Failed to load endpoints configuration' });
        }
        try {
            const endpoints = JSON.parse(data);
            res.json(endpoints);
        } catch (parseErr) {
            console.error('Error parsing endpoints JSON:', parseErr);
            res.status(500).json({ error: 'Invalid endpoints configuration format' });
        }
    });
});

// Proxy endpoint to bypass CORS
app.all('/api/proxy', async (req, res) => {
    const { method, url, headers, body } = req.body;

    console.log(`[Proxy] Forwarding ${method} request to ${url}`);
    console.log(`[Proxy] Body:`, JSON.stringify(body));

    try {
        const response = await axios({
            method,
            url,
            headers,
            data: body,
            validateStatus: () => true // Allow any status code
        });

        res.status(response.status).json({
            status: response.status,
            headers: response.headers,
            data: response.data
        });
    } catch (error) {
        console.error('Proxy error:', error.message);
        res.status(500).json({
            error: error.message,
            details: error.response ? error.response.data : null
        });
    }
});

// Endpoint to get server configuration
app.get('/api/config', (req, res) => {
    res.json({
        serverPort: config.serverPort || 8011,
        serverUrl: `http://localhost:${config.serverPort || 8011}`
    });
});

app.listen(PORT, () => {
    console.log(`API Tester UI running at http://localhost:${PORT}`);
});
