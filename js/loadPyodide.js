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

            // 3. Install SymEngine from the local pre-built wasm wheel.
            //    Falls back gracefully to SymPy-only if unavailable.
            statusEl.textContent = 'Installing SymEngine…';
            try {
                await pyodide.loadPackage('micropip');
                const wheelURL = new URL(
                    'lib/symengine-0.14.1-cp312-cp312-pyodide_2024_0_wasm32.whl',
                    window.location.href
                ).href;
                await pyodide.runPythonAsync(`
import micropip
await micropip.install('${wheelURL}')
`);
            } catch (e) {
                console.warn('SymEngine wheel install failed (falling back to SymPy):', e);
            }

            // 5. Load our CAS engine Python code
            statusEl.textContent = 'Initialising CAS engine…';
            const response = await fetch('js/casEngine.py');
            const casCode = await response.text();
            await pyodide.runPythonAsync(casCode);

            // 6. Query back-end info for status bar
            const engineInfo = JSON.parse(await pyodide.runPythonAsync('cas_engine_info()'));
            const seLabel = engineInfo.symengine_available
                ? ` + SymEngine ${engineInfo.symengine_version}`
                : '';
            statusEl.textContent = `CAS ready (SymPy ${engineInfo.sympy_version}${seLabel})`;
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
