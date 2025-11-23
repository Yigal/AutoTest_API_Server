const { spawn, exec } = require('child_process');
const kill = require('kill-port');
const path = require('path');
const config = require('../config.json');
const fs = require('fs');

const TESTER_PORT = config.testerPort || 8010;
const SERVER_PORT = config.serverPort || 8011;

async function start() {
    console.log('Starting API Tester Environment...');

    // 1. Kill existing processes
    if (config.autoKillPorts) {
        console.log('Cleaning up ports...');
        try {
            await kill(TESTER_PORT, 'tcp');
            await kill(SERVER_PORT, 'tcp');
            console.log('Ports cleaned successfully.');
        } catch (e) {
            console.log('Ports were already free or could not be killed:', e.message);
        }
    }

    // 2. Generate Endpoints
    if (config.autoGenerateEndpoints) {
        console.log('Generating endpoints configuration...');
        await new Promise((resolve, reject) => {
            const generator = spawn('python3', ['../backend/generate_endpoints.py'], {
                cwd: path.join(__dirname, '..')
            });

            generator.stdout.on('data', (data) => {
                console.log(`[Generator]: ${data}`);
            });

            generator.stderr.on('data', (data) => {
                console.error(`[Generator Error]: ${data}`);
            });

            generator.on('close', (code) => {
                if (code === 0) {
                    console.log('Endpoints generated successfully.');
                    resolve();
                } else {
                    console.error(`Generator process exited with code ${code}`);
                    reject(new Error('Endpoint generation failed'));
                }
            });
        });
    }

    // 3. Start Python Server
    console.log(`Starting Python Server on port ${SERVER_PORT}...`);

    // We use the debug_wrapper.py to run the user's server with debugger endpoints injected
    // The wrapper reads config.json to find the actual pythonServerFile
    const wrapperFile = path.join(__dirname, '../backend/debug_wrapper.py');

    const pythonServer = spawn('python3', [wrapperFile], {
        cwd: path.join(__dirname, '..'),
        env: { ...process.env, PORT: SERVER_PORT.toString() }
    });

    pythonServer.stdout.on('data', (data) => {
        console.log(`[Python Server]: ${data}`);
    });

    pythonServer.stderr.on('data', (data) => {
        console.error(`[Python Server Error]: ${data}`);
    });

    // 4. Start Node.js Server
    console.log(`Starting API Tester UI on port ${TESTER_PORT}...`);
    const nodeServer = spawn('node', ['server.js']);

    nodeServer.stdout.on('data', (data) => {
        console.log(`[UI Server]: ${data}`);
    });

    nodeServer.stderr.on('data', (data) => {
        console.error(`[UI Server Error]: ${data}`);
    });

    // Handle exit
    process.on('SIGINT', () => {
        console.log('Stopping servers...');
        pythonServer.kill();
        nodeServer.kill();
        process.exit();
    });
}

start().catch(err => {
    console.error('Startup failed:', err);
});
