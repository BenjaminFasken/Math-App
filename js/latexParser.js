/* ============================================================
   latexParser.js — LaTeX pre-processing helpers (JS side)
   ============================================================
   Light-weight transformations applied *before* sending LaTeX
   to the Python CAS, making MathQuill's output more digestible.
   ============================================================ */

const LatexParser = (() => {
    'use strict';

    /**
     * Normalise MathQuill LaTeX output for the CAS engine.
     * @param {string} tex  — raw LaTeX from MathQuill
     * @returns {string}      — cleaned LaTeX
     */
    function normalise(tex) {
        let s = tex.trim();

        // MathQuill wraps things in \left( … \right)
        s = s.replace(/\\left/g, '');
        s = s.replace(/\\right/g, '');

        // MathQuill uses \cdot for multiplication
        s = s.replace(/\\cdot/g, ' \\cdot ');

        // Normalise whitespace
        s = s.replace(/\s+/g, ' ');

        return s;
    }

    /**
     * Detect whether the expression is an assignment (var or func).
     * Returns { type, name, params?, body } or null.
     */
    function detectAssignment(tex) {
        const plain = tex.replace(/\\operatorname\{([^}]+)\}/g, '$1')
                         .replace(/\\left|\\right/g, '')
                         .replace(/\s+/g, ' ')
                         .trim();

        // Function assignment:  f(x, y) = ...
        const funcMatch = plain.match(/^([a-zA-Z_]\w*)\s*\(([^)]+)\)\s*=\s*(.+)$/);
        if (funcMatch) {
            return {
                type: 'function_def',
                name: funcMatch[1],
                params: funcMatch[2].split(',').map(p => p.trim()),
                body: funcMatch[3],
            };
        }

        // Variable assignment:  x = ...
        const varMatch = plain.match(/^([a-zA-Z_]\w*)\s*=\s*(.+)$/);
        if (varMatch && !['e', 'i', 'pi'].includes(varMatch[1])) {
            return {
                type: 'assignment',
                name: varMatch[1],
                body: varMatch[2],
            };
        }

        return null;
    }

    /**
     * Detect whether the expression is a CAS command (solve, diff, etc.).
     */
    function detectCommand(tex) {
        const plain = tex.replace(/\\([a-zA-Z]+)/g, '$1').trim();
        const m = plain.match(/^(solve|factor|expand|simplify|diff|integrate|limit|series|subs)\s*\(/i);
        if (m) return m[1].toLowerCase();

        // N(...) for numerical evaluation
        if (/^N\s*\(/.test(plain)) return 'numerical';
        return null;
    }

    return { normalise, detectAssignment, detectCommand };
})();
