const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newContext().then(c => c.newPage());
    await page.goto('http://localhost:8000', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => {
        const el = document.getElementById('engine-status');
        return el && el.textContent.includes('ready');
    }, { timeout: 120000 });
    console.log('Engine ready');

    // Test parse_latex directly in Pyodide
    const tests = await page.evaluate(async () => {
        const pyodide = await pyodideReady;
        const results = {};

        // Test parse_latex with frac
        try {
            const r = await pyodide.runPythonAsync(`
from sympy.parsing.latex import parse_latex
str(parse_latex(r'\\frac{1}{2}+\\frac{1}{3}'))
`);
            results.parse_latex_frac = r;
        } catch (e) {
            results.parse_latex_frac_err = e.message.slice(0, 300);
        }

        // Test parse_latex with sqrt
        try {
            const r = await pyodide.runPythonAsync(`
from sympy.parsing.latex import parse_latex
str(parse_latex(r'\\sqrt{16}'))
`);
            results.parse_latex_sqrt = r;
        } catch (e) {
            results.parse_latex_sqrt_err = e.message.slice(0, 300);
        }

        // Test if parse_latex is available at all
        try {
            const r = await pyodide.runPythonAsync(`
try:
    from sympy.parsing.latex import parse_latex
    'parse_latex available'
except ImportError as e:
    str(e)
`);
            results.parse_latex_available = r;
        } catch (e) {
            results.parse_latex_available_err = e.message.slice(0, 300);
        }

        // Test _safe_parse_latex step by step
        try {
            const r = await pyodide.runPythonAsync(`
import re
tex = r'\\frac{1}{2}+\\frac{1}{3}'
has_cmd = bool(re.search(r'\\\\[a-zA-Z]', tex))
f'has_cmd={has_cmd}, tex_repr={repr(tex)}'
`);
            results.safe_parse_debug = r;
        } catch (e) {
            results.safe_parse_debug_err = e.message.slice(0, 300);
        }

        // Test _safe_parse_latex directly
        try {
            const r = await pyodide.runPythonAsync(`
result = _safe_parse_latex(r'\\frac{1}{2}+\\frac{1}{3}')
str(result) if result else 'None'
`);
            results.safe_parse_frac = r;
        } catch (e) {
            results.safe_parse_frac_err = e.message.slice(0, 300);
        }

        // Test cas_evaluate with raw frac, but catch actual exception
        try {
            const r = await pyodide.runPythonAsync(`
import traceback
try:
    result = cas_evaluate(r'\\frac{1}{2}+\\frac{1}{3}')
    result
except Exception as e:
    traceback.format_exc()
`);
            results.cas_eval_frac = r;
        } catch (e) {
            results.cas_eval_frac_err = e.message.slice(0, 300);
        }

        // Verify what regex pattern matches
        try {
            const r = await pyodide.runPythonAsync(`
import re
tex = r'\\frac{1}{2}'
m = re.search(r'\\\\[a-zA-Z]', tex)
f'match={m}, tex_chars={[ord(c) for c in tex[:10]]}'
`);
            results.regex_debug = r;
        } catch (e) {
            results.regex_debug_err = e.message.slice(0, 300);
        }

        return results;
    });

    console.log(JSON.stringify(tests, null, 2));
    await browser.close();
})();
