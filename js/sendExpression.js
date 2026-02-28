/* ============================================================
   sendExpression.js — Bridge between JS front-end and Python CAS
   ============================================================ */

/**
 * Send a LaTeX expression to the Python CAS engine for evaluation.
 *
 * @param {string} latexStr  — raw LaTeX from MathQuill
 * @returns {Promise<Object>}  — parsed JSON result from casEngine.py
 *   { ok, latex, plain, type, [name], [params], [error] }
 */
async function sendExpression(latexStr) {
    const pyodide = await pyodideReady;

    // Escape the string for safe embedding in Python
    const escaped = latexStr
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/\n/g, '\\n');

    const jsonStr = await pyodide.runPythonAsync(
        `cas_evaluate('${escaped}')`
    );

    return JSON.parse(jsonStr);
}

/**
 * Retrieve the current CAS state (all defined variables & functions).
 * @returns {Promise<Object>}  { variables: {...}, functions: {...} }
 */
async function getCASState() {
    const pyodide = await pyodideReady;
    const jsonStr = await pyodide.runPythonAsync('cas_get_state()');
    return JSON.parse(jsonStr);
}

/**
 * Reset all CAS state.
 * @returns {Promise<Object>}  { ok: true }
 */
async function clearCAS() {
    const pyodide = await pyodideReady;
    const jsonStr = await pyodide.runPythonAsync('cas_clear()');
    return JSON.parse(jsonStr);
}
