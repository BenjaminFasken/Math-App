/* ============================================================
   rowManager.js — Create / manage notebook rows (cells)
   ============================================================ */

const RowManager = (() => {
    'use strict';

    const MQ = MathQuill.getInterface(2);
    let rowCounter = 0;

    /**
     * Create a new row element and append it (or insert after a reference row).
     * @param {HTMLElement} container  — the #notebook element
     * @param {HTMLElement} [afterRow] — insert after this row (null → append)
     * @returns {{ el: HTMLElement, mq: MathField, id: number }}
     */
    function createRow(container, afterRow = null) {
        rowCounter++;
        const id = rowCounter;

        // Row wrapper
        const row = document.createElement('div');
        row.className = 'math-row';
        row.dataset.rowId = id;
        row.dataset.mode = 'math';  // 'math' | 'text'

        // Gutter (line number)
        const gutter = document.createElement('div');
        gutter.className = 'row-gutter';
        gutter.textContent = id;

        // Input container
        const inputWrap = document.createElement('div');
        inputWrap.className = 'row-input';

        // MathQuill editable field
        const mqSpan = document.createElement('span');
        mqSpan.className = 'mq-field';
        inputWrap.appendChild(mqSpan);

        // Text-mode toggle button
        const textToggle = document.createElement('button');
        textToggle.className = 'btn-text-toggle';
        textToggle.textContent = 'T';
        textToggle.title = 'Switch to text mode';
        inputWrap.appendChild(textToggle);

        // Separator (shows = or :=)
        const sep = document.createElement('div');
        sep.className = 'row-separator';
        sep.textContent = '';

        // Result area
        const result = document.createElement('div');
        result.className = 'row-result';
        result.dataset.state = 'empty'; // empty | loading | done | error

        // Controls (context menu button)
        const controls = document.createElement('div');
        controls.className = 'row-controls';

        const menuBtn = document.createElement('button');
        menuBtn.className = 'btn-icon btn-menu';
        menuBtn.innerHTML = '&#8942;'; // ⋮
        menuBtn.title = 'Row options';
        controls.appendChild(menuBtn);

        // Context menu
        const ctxMenu = document.createElement('div');
        ctxMenu.className = 'context-menu';
        ctxMenu.innerHTML = `
            <button class="context-menu-item" data-action="move-up">⬆ Move up</button>
            <button class="context-menu-item" data-action="insert-above">Insert above</button>
            <button class="context-menu-item" data-action="insert-below">Insert below</button>
            <button class="context-menu-item danger" data-action="delete">✕ Delete row</button>
        `;
        controls.appendChild(ctxMenu);

        // Assemble
        row.appendChild(gutter);
        row.appendChild(inputWrap);
        row.appendChild(sep);
        row.appendChild(result);
        row.appendChild(controls);

        // Insert into DOM
        if (afterRow && afterRow.nextSibling) {
            container.insertBefore(row, afterRow.nextSibling);
        } else {
            container.appendChild(row);
        }

        // Initialise MathQuill
        // NOTE: autoCommands must NOT include names that are built-in operator
        // names in MathQuill (sin, cos, tan, etc.) — those belong only in
        // autoOperatorNames.  Including them in autoCommands causes MathQuill
        // to throw "is a built-in operator name" and the field never initialises.
        const mathField = MQ.MathField(mqSpan, {
            spaceBehavesLikeTab: false,
            supSubsRequireOperand: true,
            autoCommands: 'pi theta alpha beta gamma delta epsilon sigma omega phi psi lambda mu nu rho tau chi zeta eta iota kappa xi sqrt sum prod int infty',
            autoOperatorNames: 'solve factor expand simplify diff integrate limit series subs sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh ln log exp abs floor ceil gcd lcm mod det lim',
            handlers: {
                edit: function () {},
                enter: function () {},
            },
        });

        return { el: row, mq: mathField, id };
    }

    /**
     * Convert a math row to text mode.
     */
    function switchToTextMode(rowEl) {
        if (rowEl.dataset.mode === 'text') return;
        rowEl.dataset.mode = 'text';

        const inputWrap = rowEl.querySelector('.row-input');
        const mqField = inputWrap.querySelector('.mq-field');
        const textToggle = inputWrap.querySelector('.btn-text-toggle');

        // Hide MathQuill, show textarea
        mqField.style.display = 'none';
        textToggle.style.display = 'none';

        const textarea = document.createElement('textarea');
        textarea.className = 'row-text-input';
        textarea.placeholder = 'Type text note…';
        textarea.rows = 1;
        inputWrap.appendChild(textarea);
        textarea.focus();

        // Auto-resize
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });

        // Hide result/separator for text rows
        rowEl.querySelector('.row-separator').textContent = '';
        rowEl.querySelector('.row-result').textContent = '';
    }

    /**
     * Convert a text row back to math mode.
     */
    function switchToMathMode(rowEl, mqField) {
        if (rowEl.dataset.mode === 'math') return;
        rowEl.dataset.mode = 'math';

        const inputWrap = rowEl.querySelector('.row-input');
        const mqSpan = inputWrap.querySelector('.mq-field');
        const textarea = inputWrap.querySelector('.row-text-input');
        const textToggle = inputWrap.querySelector('.btn-text-toggle');

        if (textarea) textarea.remove();
        mqSpan.style.display = '';
        if (textToggle) textToggle.style.display = '';

        mqField.focus();
    }

    /**
     * Delete a row element and return the previous row (or null).
     */
    function deleteRow(rowEl) {
        const prev = rowEl.previousElementSibling;
        rowEl.remove();
        return prev;
    }

    /**
     * Move a row up (swap with previous sibling).
     */
    function moveRowUp(rowEl) {
        const prev = rowEl.previousElementSibling;
        if (prev) {
            rowEl.parentNode.insertBefore(rowEl, prev);
        }
    }

    /**
     * Re-number all row gutters sequentially.
     */
    function renumber(container) {
        const rows = container.querySelectorAll('.math-row');
        rows.forEach((row, i) => {
            row.querySelector('.row-gutter').textContent = i + 1;
        });
    }

    /**
     * Display a result in a row.
     * @param {HTMLElement} rowEl
     * @param {Object}      result — from sendExpression
     */
    function showResult(rowEl, result) {
        const sepEl = rowEl.querySelector('.row-separator');
        const resEl = rowEl.querySelector('.row-result');

        if (!result.ok) {
            sepEl.textContent = '';
            resEl.textContent = result.error || 'Error';
            resEl.className = 'row-result error';
            resEl.dataset.state = 'error';
            return;
        }

        if (result.type === 'empty') {
            sepEl.textContent = '';
            resEl.textContent = '';
            resEl.className = 'row-result';
            resEl.dataset.state = 'empty';
            return;
        }

        // Show separator
        if (result.type === 'assignment' || result.type === 'function_def') {
            sepEl.textContent = '≔';
        } else {
            sepEl.textContent = '=';
        }

        // Render result LaTeX via static MathQuill
        resEl.className = 'row-result';
        resEl.dataset.state = 'done';
        resEl.innerHTML = '';

        // Store both symbolic and numeric data for toggle
        resEl.dataset.symbolicLatex = result.latex || '';
        resEl.dataset.numericLatex = result.numeric_latex || '';
        resEl.dataset.displayMode = 'symbolic';
        resEl.dataset.isMatrix = result.is_matrix ? 'true' : 'false';

        if (result.latex) {
            const span = document.createElement('span');
            span.className = 'result-latex';
            resEl.appendChild(span);

            // Use KaTeX for matrix results (MathQuill can't render \begin{matrix})
            if (result.is_matrix && typeof katex !== 'undefined') {
                katex.render(result.latex, span, {
                    throwOnError: false,
                    displayMode: true,
                });
            } else {
                MQ.StaticMath(span).latex(result.latex);
            }
        } else {
            resEl.textContent = result.plain || '';
        }

        // Show assignment indicator
        if (result.name) {
            const badge = document.createElement('span');
            badge.className = 'row-assignment-indicator';
            badge.textContent = result.type === 'function_def'
                ? `${result.name}(${(result.params || []).join(', ')})`
                : result.name;
            resEl.prepend(badge);
        }

        // Show numeric toggle button if a numeric value is available
        if (result.numeric_latex && result.numeric_latex !== result.latex) {
            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'btn-numeric-toggle';
            toggleBtn.textContent = '≈';
            toggleBtn.title = 'Toggle numeric / symbolic';
            toggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleNumeric(resEl);
            });
            resEl.appendChild(toggleBtn);
        }
    }

    /**
     * Toggle between symbolic and numeric display.
     */
    function toggleNumeric(resEl) {
        const mode = resEl.dataset.displayMode;
        const symLatex = resEl.dataset.symbolicLatex;
        const numLatex = resEl.dataset.numericLatex;

        if (!numLatex) return;

        const newMode = mode === 'symbolic' ? 'numeric' : 'symbolic';
        const newLatex = newMode === 'numeric' ? numLatex : symLatex;
        resEl.dataset.displayMode = newMode;

        // Update the rendered math (preserve badge and toggle button)
        const badge = resEl.querySelector('.row-assignment-indicator');
        const toggleBtn = resEl.querySelector('.btn-numeric-toggle');
        const isMatrix = resEl.dataset.isMatrix === 'true';
        resEl.innerHTML = '';

        if (badge) resEl.appendChild(badge);

        const span = document.createElement('span');
        span.className = 'result-latex';
        resEl.appendChild(span);

        if (isMatrix && typeof katex !== 'undefined') {
            katex.render(newLatex, span, { throwOnError: false, displayMode: true });
        } else {
            MQ.StaticMath(span).latex(newLatex);
        }

        if (toggleBtn) {
            toggleBtn.textContent = newMode === 'numeric' ? '=' : '≈';
            toggleBtn.title = newMode === 'numeric'
                ? 'Show symbolic value'
                : 'Show numeric value';
            resEl.appendChild(toggleBtn);
        }
    }

    /**
     * Show loading state in result area.
     */
    function showLoading(rowEl) {
        const resEl = rowEl.querySelector('.row-result');
        resEl.className = 'row-result';
        resEl.dataset.state = 'loading';
        resEl.textContent = '…';
    }

    /**
     * Clear result area.
     */
    function clearResult(rowEl) {
        const sepEl = rowEl.querySelector('.row-separator');
        const resEl = rowEl.querySelector('.row-result');
        sepEl.textContent = '';
        resEl.textContent = '';
        resEl.className = 'row-result';
        resEl.dataset.state = 'empty';
    }

    return {
        createRow,
        switchToTextMode,
        switchToMathMode,
        deleteRow,
        moveRowUp,
        renumber,
        showResult,
        showLoading,
        clearResult,
    };
})();
