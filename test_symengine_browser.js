/**
 * Quick browser test: Does SymEngine load via our local wheel in Pyodide?
 * Run: node test_symengine_browser.js
 * Requires: dev server running on http://localhost:8000
 */
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newContext().then(c => c.newPage());

    // Capture console output
    page.on('console', msg => {
        const type = msg.type();
        if (type === 'error' || type === 'warn') {
            console.log(`  [${type}] ${msg.text()}`);
        }
    });
    page.on('pageerror', err => console.log(`  [pageerror] ${err.message}`));

    console.log('Loading page...');
    await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded', timeout: 15000 });

    // Wait for CAS engine to be ready (status bar says "CAS ready")
    console.log('Waiting for CAS engine...');
    try {
        await page.waitForFunction(
            () => {
                const el = document.getElementById('engine-status');
                return el && el.textContent.includes('CAS ready');
            },
            { timeout: 120000 }
        );
    } catch (e) {
        const status = await page.evaluate(() => {
            const el = document.getElementById('engine-status');
            return el ? el.textContent : '(no element)';
        });
        console.log(`TIMEOUT waiting for CAS ready. Status: "${status}"`);
        await browser.close();
        process.exit(1);
    }

    // Check status bar text
    const statusText = await page.evaluate(() =>
        document.getElementById('engine-status').textContent
    );
    console.log(`\nStatus bar: "${statusText}"`);

    if (statusText.includes('SymEngine')) {
        console.log('\x1b[32m✓ SymEngine loaded successfully in browser!\x1b[0m');
    } else {
        console.log('\x1b[33m⚠ SymEngine NOT detected (SymPy-only mode)\x1b[0m');
    }

    // Test SymEngine import directly
    const engineInfo = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        return JSON.parse(await pyodide.runPythonAsync('cas_engine_info()'));
    });
    console.log('\nEngine info:', JSON.stringify(engineInfo, null, 2));

    // Try a quick computation
    const result = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        return JSON.parse(await pyodide.runPythonAsync("cas_evaluate('expand((x+1)^3)')"));
    });
    console.log('expand((x+1)^3) =', result.latex);

    await browser.close();
    process.exit(0);
})();
