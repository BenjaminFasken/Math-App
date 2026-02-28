/* ============================================================
   loadPyodide.js — Bootstrap Pyodide + SymPy CAS engine
   ============================================================ */

/**
 * Global promise that resolves to the Pyodide instance once loaded.
 * All other modules should `await pyodideReady` before using it.
 */
let pyodideReady;

(function () {
    'use strict';

    const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.27.4/full/';

    /**
     * Initialise Pyodide, install SymPy, and load the CAS engine.
     */
    async function init() {
        const statusEl = document.getElementById('engine-status');

        try {
            // 1. Load Pyodide runtime
            statusEl.textContent = 'Loading Python runtime…';
            statusEl.className = 'status-loading';

            const pyodide = await loadPyodide({
                indexURL: PYODIDE_CDN,
            });

            // 2. Install SymPy (micropip is bundled in Pyodide)
            statusEl.textContent = 'Installing SymPy…';
            await pyodide.loadPackage('sympy');

            // 3. Load our CAS engine Python code
            statusEl.textContent = 'Initialising CAS engine…';
            const response = await fetch('js/casEngine.py');
            const casCode = await response.text();
            await pyodide.runPythonAsync(casCode);

            // 4. Ready!
            statusEl.textContent = 'CAS engine ready';
            statusEl.className = 'status-ready';

            return pyodide;
        } catch (err) {
            console.error('Pyodide init failed:', err);
            statusEl.textContent = 'Engine failed to load';
            statusEl.className = 'status-error';
            throw err;
        }
    }

    // Kick off loading immediately — other modules await this promise.
    pyodideReady = init();
})();
