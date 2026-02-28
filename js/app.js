/* ============================================================
   app.js — Main application logic for MathApp CAS Calculator
   ============================================================
   Orchestrates rows, keyboard handling, evaluation, context
   menus, text-mode toggling and auto-cleanup.
   ============================================================ */

(function () {
    'use strict';

    const notebook = document.getElementById('notebook');

    // Map:  rowId → { el, mq, id }
    const rows = new Map();

    // Currently focused row id
    let focusedRowId = null;

    // Track which context menu is open
    let openMenuRowId = null;

    // ── Initialise first row ───────────────────────────────
    function init() {
        addRow();
    }

    // ── Row lifecycle ──────────────────────────────────────

    function addRow(afterRowEl = null) {
        const rowInfo = RowManager.createRow(notebook, afterRowEl);
        rows.set(rowInfo.id, rowInfo);
        wireRowEvents(rowInfo);
        RowManager.renumber(notebook);
        rowInfo.mq.focus();
        setFocused(rowInfo.id);
        return rowInfo;
    }

    function removeRow(id) {
        const info = rows.get(id);
        if (!info) return;

        // Don't delete the last row
        if (rows.size <= 1) return;

        const prev = RowManager.deleteRow(info.el);
        rows.delete(id);
        RowManager.renumber(notebook);

        // Focus the previous row (or the first remaining one)
        if (prev && prev.dataset && prev.dataset.rowId) {
            const prevId = parseInt(prev.dataset.rowId, 10);
            const prevInfo = rows.get(prevId);
            if (prevInfo) {
                prevInfo.mq.focus();
                setFocused(prevId);
            }
        } else {
            // Focus first remaining row
            const first = rows.values().next().value;
            if (first) {
                first.mq.focus();
                setFocused(first.id);
            }
        }
    }

    // ── Focus management ───────────────────────────────────

    function setFocused(id) {
        // Remove old focus
        if (focusedRowId !== null && focusedRowId !== id) {
            const old = rows.get(focusedRowId);
            if (old) old.el.classList.remove('focused');
        }
        focusedRowId = id;
        const info = rows.get(id);
        if (info) info.el.classList.add('focused');

        // Show/hide text toggle
        updateTextToggleVisibility(info);
    }

    function updateTextToggleVisibility(info) {
        if (!info) return;
        const toggleBtn = info.el.querySelector('.btn-text-toggle');
        if (!toggleBtn) return;

        if (info.el.dataset.mode === 'math') {
            const latex = info.mq.latex().trim();
            toggleBtn.classList.toggle('visible', latex === '');
        } else {
            toggleBtn.classList.remove('visible');
        }
    }

    // ── Wire events for a row ──────────────────────────────

    function wireRowEvents(info) {
        const { el, mq, id } = info;
        const inputWrap = el.querySelector('.row-input');
        const textToggle = el.querySelector('.btn-text-toggle');
        const menuBtn = el.querySelector('.btn-menu');
        const ctxMenu = el.querySelector('.context-menu');

        // --- MathQuill handlers ---
        // MathQuill 0.10.x requires handlers at creation time via MathField(),
        // but we can still reconfigure them. We use __controller to set the
        // callbacks since .config() with handlers can be unreliable.
        // Instead, we intercept keydown on the MQ element for Enter,
        // and use a MutationObserver for edit detection.

        // Enter key → evaluate
        const mqEl = el.querySelector('.mq-editable-field') || el.querySelector('.mq-field');
        if (mqEl) {
            mqEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.keyCode === 13) {
                    e.preventDefault();
                    e.stopPropagation();
                    evaluateRow(id);
                }
            });

            // Detect edits for toggling the T button
            mqEl.addEventListener('input', () => {
                updateTextToggleVisibility(info);
            });
            mqEl.addEventListener('keyup', () => {
                updateTextToggleVisibility(info);
            });
        }

        // Click on the row to focus
        el.addEventListener('mousedown', (e) => {
            // Don't steal focus from buttons
            if (e.target.closest('button') || e.target.closest('.context-menu')) return;
            setFocused(id);
            if (el.dataset.mode === 'math') {
                mq.focus();
            }
        });

        // --- Text toggle ---
        textToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            RowManager.switchToTextMode(el);
        });

        // --- Context menu ---
        menuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleContextMenu(id);
        });

        ctxMenu.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            if (!action) return;
            e.stopPropagation();
            closeAllMenus();
            handleContextAction(id, action);
        });
    }

    // ── Context menu ───────────────────────────────────────

    function toggleContextMenu(id) {
        if (openMenuRowId === id) {
            closeAllMenus();
            return;
        }
        closeAllMenus();
        const info = rows.get(id);
        if (!info) return;
        info.el.querySelector('.context-menu').classList.add('open');
        openMenuRowId = id;
    }

    function closeAllMenus() {
        if (openMenuRowId !== null) {
            const info = rows.get(openMenuRowId);
            if (info) {
                info.el.querySelector('.context-menu').classList.remove('open');
            }
            openMenuRowId = null;
        }
    }

    function handleContextAction(id, action) {
        const info = rows.get(id);
        if (!info) return;

        switch (action) {
            case 'delete':
                removeRow(id);
                break;
            case 'move-up':
                RowManager.moveRowUp(info.el);
                RowManager.renumber(notebook);
                break;
            case 'insert-above': {
                const prev = info.el.previousElementSibling;
                addRow(prev || null);
                // Move newly added row before current if prev was null
                if (!prev) {
                    notebook.insertBefore(
                        notebook.lastElementChild,
                        info.el
                    );
                    RowManager.renumber(notebook);
                }
                break;
            }
            case 'insert-below':
                addRow(info.el);
                break;
        }
    }

    // ── Evaluation ─────────────────────────────────────────

    async function evaluateRow(id) {
        const info = rows.get(id);
        if (!info) return;

        if (info.el.dataset.mode === 'text') {
            // Text rows don't evaluate; just create next row
            addRow(info.el);
            return;
        }

        const latexStr = info.mq.latex().trim();
        if (!latexStr) {
            // Empty expression → just create a new row
            addRow(info.el);
            return;
        }

        // Show loading
        RowManager.showLoading(info.el);

        try {
            const result = await sendExpression(latexStr);
            RowManager.showResult(info.el, result);
        } catch (err) {
            console.error('Evaluation error:', err);
            RowManager.showResult(info.el, {
                ok: false,
                error: err.message || 'Evaluation failed',
            });
        }

        // Create new row below
        addRow(info.el);
    }

    // ── Keyboard navigation ────────────────────────────────

    document.addEventListener('keydown', (e) => {
        // Close menus on Escape
        if (e.key === 'Escape') {
            closeAllMenus();
            return;
        }

        if (focusedRowId === null) return;
        const info = rows.get(focusedRowId);
        if (!info) return;

        // Arrow Up → focus previous row
        if (e.key === 'ArrowUp' && e.ctrlKey) {
            e.preventDefault();
            const prev = info.el.previousElementSibling;
            if (prev && prev.dataset.rowId) {
                const prevId = parseInt(prev.dataset.rowId, 10);
                const prevInfo = rows.get(prevId);
                if (prevInfo) {
                    if (prevInfo.el.dataset.mode === 'math') prevInfo.mq.focus();
                    setFocused(prevId);
                }
            }
        }

        // Arrow Down → focus next row
        if (e.key === 'ArrowDown' && e.ctrlKey) {
            e.preventDefault();
            const next = info.el.nextElementSibling;
            if (next && next.dataset.rowId) {
                const nextId = parseInt(next.dataset.rowId, 10);
                const nextInfo = rows.get(nextId);
                if (nextInfo) {
                    if (nextInfo.el.dataset.mode === 'math') nextInfo.mq.focus();
                    setFocused(nextId);
                }
            }
        }

        // Backspace on empty row → delete it
        if (e.key === 'Backspace' && info.el.dataset.mode === 'math') {
            const latex = info.mq.latex().trim();
            if (latex === '' && rows.size > 1) {
                e.preventDefault();
                removeRow(info.id);
            }
        }
    });

    // ── Click-away: clean up empty rows ────────────────────

    document.addEventListener('click', (e) => {
        closeAllMenus();

        // If clicking outside any row, clean up empty non-last rows
        if (!e.target.closest('.math-row')) {
            const allRows = Array.from(notebook.querySelectorAll('.math-row'));
            // Keep at least one row.  Remove empty ones that aren't the last.
            for (let i = 0; i < allRows.length - 1; i++) {
                const r = allRows[i];
                const rid = parseInt(r.dataset.rowId, 10);
                const rInfo = rows.get(rid);
                if (!rInfo) continue;

                const isEmpty =
                    r.dataset.mode === 'math'
                        ? rInfo.mq.latex().trim() === ''
                        : (r.querySelector('.row-text-input')?.value.trim() ?? '') === '';

                const hasResult = r.querySelector('.row-result')?.dataset.state === 'done';

                if (isEmpty && !hasResult) {
                    removeRow(rid);
                }
            }
        }
    });

    // ── Boot ───────────────────────────────────────────────
    let _booted = false;
    function boot() {
        if (_booted) return;
        _booted = true;
        init();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
