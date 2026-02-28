const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newContext().then(c => c.newPage());
    page.on('console', msg => {
        if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
    });
    await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => {
        const el = document.getElementById('engine-status');
        return el && el.textContent.includes('ready');
    }, { timeout: 120000 });
    console.log('Engine ready');

    // Test 1: Inspect what sendExpression does with a frac
    const debug1 = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        // Manually build the Python code like sendExpression does
        const latexStr = String.raw`\frac{1}{2}+\frac{1}{3}`;
        const escaped = latexStr
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/\n/g, '\\n');
        const pyCode = `cas_evaluate('${escaped}')`;
        return { latexStr, escaped, pyCode };
    });
    console.log('Escaping inspection:', JSON.stringify(debug1, null, 2));

    // Test 2: Run the Python code directly
    const debug2 = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        const latexStr = String.raw`\frac{1}{2}+\frac{1}{3}`;
        const escaped = latexStr
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/\n/g, '\\n');
        const pyCode = `cas_evaluate('${escaped}')`;
        try {
            const result = await pyodide.runPythonAsync(pyCode);
            return { pyCode, result };
        } catch (e) {
            return { pyCode, error: e.message.slice(0, 200) };
        }
    });
    console.log('Direct CAS test:', JSON.stringify(debug2, null, 2));

    // Test 3: Use a raw Python string
    const debug3 = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        try {
            const result = await pyodide.runPythonAsync(
                String.raw`cas_evaluate(r'\frac{1}{2}+\frac{1}{3}')`
            );
            return { result };
        } catch (e) {
            return { error: e.message.slice(0, 200) };
        }
    });
    console.log('Raw Python string:', JSON.stringify(debug3, null, 2));

    // Test 4: Test sqrt
    const debug4 = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        try {
            const result = await pyodide.runPythonAsync(
                String.raw`cas_evaluate(r'\sqrt{16}')`
            );
            return { result };
        } catch (e) {
            return { error: e.message.slice(0, 200) };
        }
    });
    console.log('sqrt raw:', JSON.stringify(debug4, null, 2));

    // Test 5: Test f(3) function call
    const debug5 = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        await pyodide.runPythonAsync(String.raw`cas_evaluate(r'f(t) = t^2 + 1')`);
        try {
            const r1 = await pyodide.runPythonAsync(String.raw`cas_evaluate(r'f(3)')`);
            const r2 = await pyodide.runPythonAsync(String.raw`cas_evaluate(r'f\left(3\right)')`);
            return { r1, r2 };
        } catch (e) {
            return { error: e.message.slice(0, 200) };
        }
    });
    console.log('f(3) tests:', JSON.stringify(debug5, null, 2));

    // Test 6: What does MathQuill output for typical expressions?
    const mqOutput = await page.evaluate(() => {
        const MQ = MathQuill.getInterface(2);
        const container = document.createElement('span');
        document.body.appendChild(container);
        const mq = MQ.MathField(container, {
            autoCommands: 'pi theta sqrt sum prod int infty',
            autoOperatorNames: 'sin cos tan ln log exp',
            handlers: { edit: function(){}, enter: function(){} },
        });

        // Set different expressions and get the output
        const tests = {};
        mq.latex('\\frac{1}{2}');
        tests.frac = mq.latex();
        mq.latex('\\sqrt{16}');
        tests.sqrt = mq.latex();
        mq.latex('f(3)');
        tests.funcCall = mq.latex();
        mq.latex('f\\left(3\\right)');
        tests.funcCallExplicit = mq.latex();

        container.remove();
        return tests;
    });
    console.log('MathQuill latex outputs:', JSON.stringify(mqOutput, null, 2));

    await browser.close();
})();
