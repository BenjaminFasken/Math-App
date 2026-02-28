/**
 * test_browser_playwright.js — Automated browser tests for MathApp
 * Run: node test_browser_playwright.js
 * Requires: dev server running on http://localhost:8000
 */
const { chromium } = require('playwright');

const BASE = 'http://localhost:8000';
let passed = 0, failed = 0;

function log(status, msg) {
    const icon = status === 'PASS' ? '\x1b[32m✓\x1b[0m' : '\x1b[31m✗\x1b[0m';
    if (status === 'PASS') passed++; else failed++;
    console.log(`  ${icon} ${msg}`);
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Collect console errors
    const consoleErrors = [];
    page.on('console', msg => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', err => consoleErrors.push(err.message));

    // ═══════════════════════════════════════════════
    console.log('\n=== 1. Page Load ===');
    // ═══════════════════════════════════════════════
    try {
        const resp = await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 15000 });
        log(resp.status() === 200 ? 'PASS' : 'FAIL', `Page loads: status ${resp.status()}`);
    } catch (e) {
        log('FAIL', `Page load failed: ${e.message}`);
        await browser.close();
        process.exit(1);
    }

    // Wait a moment for scripts to execute
    await page.waitForTimeout(2000);

    // ═══════════════════════════════════════════════
    console.log('\n=== 2. Dependencies ===');
    // ═══════════════════════════════════════════════
    const hasJQuery = await page.evaluate(() => typeof jQuery !== 'undefined');
    log(hasJQuery ? 'PASS' : 'FAIL', 'jQuery loaded');

    const hasMathQuill = await page.evaluate(() => typeof MathQuill !== 'undefined');
    log(hasMathQuill ? 'PASS' : 'FAIL', 'MathQuill loaded');

    const hasPyodideLoader = await page.evaluate(() => typeof loadPyodide !== 'undefined');
    log(hasPyodideLoader ? 'PASS' : 'FAIL', 'Pyodide loader available');

    // ═══════════════════════════════════════════════
    console.log('\n=== 3. MathQuill Field Init ===');
    // ═══════════════════════════════════════════════

    // Check that MathQuill field was created
    const hasMqField = await page.locator('.mq-editable-field').count();
    log(hasMqField > 0 ? 'PASS' : 'FAIL', `MathQuill editable field present (count: ${hasMqField})`);

    // Check row structure
    const hasRow = await page.locator('.math-row').count();
    log(hasRow > 0 ? 'PASS' : 'FAIL', `At least one math row present (count: ${hasRow})`);

    const hasGutter = await page.locator('.row-gutter').count();
    log(hasGutter > 0 ? 'PASS' : 'FAIL', `Row gutter present`);

    const hasInput = await page.locator('.row-input').count();
    log(hasInput > 0 ? 'PASS' : 'FAIL', `Row input wrapper present`);

    const hasResult = await page.locator('.row-result').count();
    log(hasResult > 0 ? 'PASS' : 'FAIL', `Row result area present`);

    // Check MQ textarea (MathQuill's hidden input)
    const hasTextarea = await page.locator('.mq-textarea textarea').count();
    log(hasTextarea > 0 ? 'PASS' : 'FAIL', `MathQuill hidden textarea present (count: ${hasTextarea})`);

    // ═══════════════════════════════════════════════
    console.log('\n=== 4. Typing in MathQuill ===');
    // ═══════════════════════════════════════════════

    // Focus the MathQuill field
    const mqField = page.locator('.mq-editable-field').first();
    await mqField.click();
    await page.waitForTimeout(300);

    // Type a simple expression
    const textarea = page.locator('.mq-textarea textarea').first();
    await textarea.type('2+3', { delay: 50 });
    await page.waitForTimeout(300);

    // Check that something was rendered
    const latex1 = await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const span = document.querySelector('.mq-editable-field');
        const mq = MQ(span);
        return mq ? mq.latex() : null;
    });
    log(latex1 && latex1.includes('2') && latex1.includes('3') ? 'PASS' : 'FAIL',
        `Typed "2+3" → latex: "${latex1}"`);

    // Type more — try a fraction
    await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const span = document.querySelector('.mq-editable-field');
        const mq = MQ(span);
        mq.latex('\\frac{1}{2}');
    });
    await page.waitForTimeout(200);
    const latex2 = await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const span = document.querySelector('.mq-editable-field');
        return MQ(span).latex();
    });
    log(latex2 && latex2.includes('frac') ? 'PASS' : 'FAIL',
        `Set fraction via latex → "${latex2}"`);

    // Test square root via latex
    await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const span = document.querySelector('.mq-editable-field');
        MQ(span).latex('\\sqrt{x}');
    });
    const latex3 = await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const span = document.querySelector('.mq-editable-field');
        return MQ(span).latex();
    });
    log(latex3 && latex3.includes('sqrt') ? 'PASS' : 'FAIL',
        `Set sqrt via latex → "${latex3}"`);

    // ═══════════════════════════════════════════════
    console.log('\n=== 5. Enter Key (Evaluate) ===');
    // ═══════════════════════════════════════════════

    // Set a simple expression and press Enter
    await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const span = document.querySelector('.mq-editable-field');
        MQ(span).latex('2+3');
    });
    await page.waitForTimeout(200);

    const rowCountBefore = await page.locator('.math-row').count();

    // Press Enter on the MathQuill textarea
    await mqField.click();
    await page.waitForTimeout(100);
    await textarea.press('Enter');
    await page.waitForTimeout(500);

    const rowCountAfter = await page.locator('.math-row').count();
    log(rowCountAfter > rowCountBefore ? 'PASS' : 'FAIL',
        `Enter creates new row (before: ${rowCountBefore}, after: ${rowCountAfter})`);

    // ═══════════════════════════════════════════════
    console.log('\n=== 6. Pyodide + CAS Engine ===');
    // ═══════════════════════════════════════════════

    // Wait for Pyodide to load (up to 120 seconds)
    console.log('  ⏳ Waiting for Pyodide to load (up to 120s)...');
    let pyodideLoaded = false;
    try {
        await page.waitForFunction(
            () => {
                const el = document.getElementById('engine-status');
                return el && (el.textContent.includes('ready') || el.textContent.includes('failed'));
            },
            { timeout: 120000 }
        );
        const statusText = await page.locator('#engine-status').textContent();
        pyodideLoaded = statusText.includes('ready');
        log(pyodideLoaded ? 'PASS' : 'FAIL', `Engine status: "${statusText}"`);
    } catch (e) {
        log('FAIL', `Pyodide load timeout: ${e.message}`);
    }

    if (pyodideLoaded) {
        // ═══════════════════════════════════════════════
        console.log('\n=== 7. CAS Evaluation ===');
        // ═══════════════════════════════════════════════

        // Test basic arithmetic
        const cas1 = await page.evaluate(async () => {
            return await sendExpression('2+3');
        });
        log(cas1.ok && (cas1.latex === '5' || cas1.plain === '5') ? 'PASS' : 'FAIL',
            `2+3 = ${JSON.stringify(cas1)}`);

        // Test symbolic
        const cas2 = await page.evaluate(async () => {
            return await sendExpression('x^2 + 1');
        });
        log(cas2.ok && cas2.latex ? 'PASS' : 'FAIL',
            `x^2+1 → ${cas2.latex || cas2.plain || JSON.stringify(cas2)}`);

        // Test variable assignment
        const cas3 = await page.evaluate(async () => {
            return await sendExpression('a = 5');
        });
        log(cas3.ok && cas3.type === 'assignment' ? 'PASS' : 'FAIL',
            `a=5 → type: ${cas3.type}`);

        // Test variable usage
        const cas4 = await page.evaluate(async () => {
            return await sendExpression('a + 1');
        });
        log(cas4.ok && (cas4.latex === '6' || cas4.plain === '6') ? 'PASS' : 'FAIL',
            `a+1 = ${cas4.latex || cas4.plain}`);

        // Test function definition
        const cas5 = await page.evaluate(async () => {
            return await sendExpression('f(t) = t^2 + 1');
        });
        log(cas5.ok && cas5.type === 'function_def' ? 'PASS' : 'FAIL',
            `f(t)=t^2+1 → type: ${cas5.type}`);

        // Test function call
        const cas6 = await page.evaluate(async () => {
            return await sendExpression('f(3)');
        });
        log(cas6.ok && (cas6.latex === '10' || cas6.plain === '10') ? 'PASS' : 'FAIL',
            `f(3) = ${cas6.latex || cas6.plain}`);

        // Test fraction
        const cas7 = await page.evaluate(async () => {
            return await sendExpression('\\frac{1}{2} + \\frac{1}{3}');
        });
        log(cas7.ok ? 'PASS' : 'FAIL',
            `1/2 + 1/3 → ${cas7.latex || cas7.plain || JSON.stringify(cas7)}`);

        // Test sqrt
        const cas8 = await page.evaluate(async () => {
            return await sendExpression('\\sqrt{16}');
        });
        log(cas8.ok && (cas8.latex === '4' || cas8.plain === '4') ? 'PASS' : 'FAIL',
            `sqrt(16) = ${cas8.latex || cas8.plain}`);

        // Test solve command
        const cas9 = await page.evaluate(async () => {
            return await sendExpression('solve\\left(x^2-4,x\\right)');
        });
        log(cas9.ok ? 'PASS' : 'FAIL',
            `solve(x^2-4, x) → ${cas9.latex || cas9.plain || JSON.stringify(cas9)}`);

        // Test diff command
        const cas10 = await page.evaluate(async () => {
            return await sendExpression('diff\\left(x^3,x\\right)');
        });
        log(cas10.ok ? 'PASS' : 'FAIL',
            `diff(x^3, x) → ${cas10.latex || cas10.plain || JSON.stringify(cas10)}`);

        // ═══════════════════════════════════════════════
        console.log('\n=== 8. End-to-End: Type + Evaluate + Result ===');
        // ═══════════════════════════════════════════════

        // Find the last row's MQ field and type into it
        const lastMqField = page.locator('.mq-editable-field').last();
        await lastMqField.click();
        await page.waitForTimeout(200);

        // Set expression via MathQuill API
        await page.evaluate(() => {
            const MQ = MathQuill.getInterface(2);
            const fields = document.querySelectorAll('.mq-editable-field');
            const last = fields[fields.length - 1];
            MQ(last).latex('3 \\cdot 7');
        });
        await page.waitForTimeout(200);

        // Press Enter to evaluate
        const lastTextarea = page.locator('.mq-textarea textarea').last();
        await lastTextarea.press('Enter');

        // Wait for result
        await page.waitForTimeout(3000);

        // Check if result appeared
        const resultStates = await page.evaluate(() => {
            return Array.from(document.querySelectorAll('.row-result'))
                .map(el => ({ state: el.dataset.state, text: el.textContent.trim() }));
        });

        const hasEvalResult = resultStates.some(r => r.state === 'done' || r.state === 'loading');
        log(hasEvalResult ? 'PASS' : 'FAIL',
            `End-to-end evaluation produced result: ${JSON.stringify(resultStates)}`);
    }

    // ═══════════════════════════════════════════════
    console.log('\n=== 9. Console Errors Check ===');
    // ═══════════════════════════════════════════════
    const criticalErrors = consoleErrors.filter(e =>
        !e.includes('favicon') &&
        !e.includes('net::ERR') &&
        !e.includes('404')
    );
    log(criticalErrors.length === 0 ? 'PASS' : 'FAIL',
        `Critical console errors: ${criticalErrors.length}`);
    if (criticalErrors.length > 0) {
        criticalErrors.forEach(e => console.log(`    ⚠ ${e}`));
    }

    // ═══════════════════════════════════════════════
    // Summary
    // ═══════════════════════════════════════════════
    console.log(`\n${'═'.repeat(50)}`);
    console.log(`  \x1b[32m${passed} passed\x1b[0m  |  \x1b[31m${failed} failed\x1b[0m  |  Total: ${passed + failed}`);
    console.log(`${'═'.repeat(50)}\n`);

    await browser.close();
    process.exit(failed > 0 ? 1 : 0);
})();
