/* ============================================================
   matrixPicker.js — Matrix size selector + input modal
   ============================================================
   Provides:
     • A Word-style hover grid for selecting matrix dimensions
     • A modal with individual cell inputs for entering values
     • LaTeX matrix generation → CAS evaluation
   ============================================================ */

const MatrixPicker = (() => {
    'use strict';

    const GRID_ROWS = 6;
    const GRID_COLS = 6;

    let _selectedRows = 0;
    let _selectedCols = 0;

    // Lazily-resolved references (DOM is ready when boot() is called)
    let _pickerBtn, _popup, _sizeGrid, _sizeLabel, _modal;
    let _modalTitle, _modalGrid, _nameInput, _insertBtn, _cancelBtn, _closeBtn;

    // Callback injected by app.js to access focused row
    let _getFocusedRowInfo = () => null;

    // ── Size selector popup ─────────────────────────────────

    function _buildSizeGrid() {
        _sizeGrid.innerHTML = '';
        for (let r = 1; r <= GRID_ROWS; r++) {
            for (let c = 1; c <= GRID_COLS; c++) {
                const cell = document.createElement('div');
                cell.className = 'matrix-size-cell';
                cell.dataset.r = r;
                cell.dataset.c = c;

                cell.addEventListener('mouseenter', () => _onCellHover(r, c));
                cell.addEventListener('mouseleave', () => _onCellHoverEnd());
                cell.addEventListener('click', (e) => {
                    e.stopPropagation();
                    _openModal(r, c);
                });

                _sizeGrid.appendChild(cell);
            }
        }
    }

    function _onCellHover(r, c) {
        _selectedRows = r;
        _selectedCols = c;
        _sizeLabel.textContent = `${r} × ${c}`;
        // Highlight all cells in the r×c rectangle
        _sizeGrid.querySelectorAll('.matrix-size-cell').forEach(cell => {
            const cr = parseInt(cell.dataset.r, 10);
            const cc = parseInt(cell.dataset.c, 10);
            cell.classList.toggle('highlighted', cr <= r && cc <= c);
        });
    }

    function _onCellHoverEnd() {
        if (_selectedRows === 0) {
            _sizeLabel.textContent = 'Select size';
        }
        // Keep highlight showing the last hovered size
    }

    function _openPopup() {
        _popup.classList.add('open');
        // Reset highlight
        _selectedRows = 0;
        _selectedCols = 0;
        _sizeLabel.textContent = 'Select size';
        _sizeGrid.querySelectorAll('.matrix-size-cell').forEach(cell =>
            cell.classList.remove('highlighted')
        );
    }

    function _closePopup() {
        _popup.classList.remove('open');
    }

    // ── Modal ───────────────────────────────────────────────

    function _openModal(rows, cols) {
        _closePopup();
        _modalTitle.textContent = `Insert ${rows} × ${cols} Matrix`;
        _nameInput.value = '';
        _buildModalGrid(rows, cols);
        _modal.setAttribute('aria-hidden', 'false');
        _modal.classList.add('open');

        // Focus first cell
        const firstCell = _modalGrid.querySelector('.matrix-cell-input');
        if (firstCell) firstCell.focus();
    }

    function _closeModal() {
        _modal.classList.remove('open');
        _modal.setAttribute('aria-hidden', 'true');
    }

    function _buildModalGrid(rows, cols) {
        _modalGrid.innerHTML = '';
        _modalGrid.style.gridTemplateColumns = `repeat(${cols}, 64px)`;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const inp = document.createElement('input');
                inp.type = 'text';
                inp.className = 'matrix-cell-input';
                inp.placeholder = '0';
                inp.dataset.r = r;
                inp.dataset.c = c;
                inp.setAttribute('aria-label', `Row ${r + 1}, Col ${c + 1}`);

                // Tab navigation: left-to-right, top-to-bottom (default)
                // Enter moves to next cell
                inp.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        const all = Array.from(_modalGrid.querySelectorAll('.matrix-cell-input'));
                        const idx = all.indexOf(inp);
                        if (idx >= 0 && idx < all.length - 1) {
                            all[idx + 1].focus();
                        } else {
                            // Last cell — trigger insert
                            _onInsert();
                        }
                    }
                });

                _modalGrid.appendChild(inp);
            }
        }
    }

    function _collectMatrixLatex() {
        const inputs = Array.from(_modalGrid.querySelectorAll('.matrix-cell-input'));
        if (!inputs.length) return null;

        const rows = parseInt(inputs[inputs.length - 1].dataset.r, 10) + 1;
        const cols = parseInt(inputs[inputs.length - 1].dataset.c, 10) + 1;

        const data = Array.from({ length: rows }, () => Array(cols).fill('0'));
        inputs.forEach(inp => {
            const r = parseInt(inp.dataset.r, 10);
            const c = parseInt(inp.dataset.c, 10);
            data[r][c] = inp.value.trim() || '0';
        });

        // Build LaTeX: \begin{pmatrix} a & b \\ c & d \end{pmatrix}
        const rowStrings = data.map(row => row.join(' & '));
        return `\\begin{pmatrix}${rowStrings.join(' \\\\ ')}\\end{pmatrix}`;
    }

    async function _onInsert() {
        const matLatex = _collectMatrixLatex();
        if (!matLatex) return;

        const varName = _nameInput.value.trim().replace(/[^a-zA-Z_0-9]/g, '');
        const fullLatex = varName ? `${varName} = ${matLatex}` : matLatex;

        _closeModal();

        // Delegate evaluation to app.js via the global evaluateMatrixExpression function
        if (typeof evaluateMatrixExpression === 'function') {
            await evaluateMatrixExpression(fullLatex);
        }
    }

    // ── Matrix command buttons ──────────────────────────────

    function _initCommandButtons() {
        document.querySelectorAll('[data-matrix-cmd]').forEach(btn => {
            btn.addEventListener('click', () => {
                const cmd = btn.dataset.matrixCmd;
                const rowInfo = _getFocusedRowInfo();
                if (!rowInfo || rowInfo.el.dataset.mode !== 'math') return;

                const currentLatex = rowInfo.mq.latex().trim();
                if (currentLatex) {
                    // Replace entire field content with cmd(currentContent)
                    rowInfo.mq.latex(`\\operatorname{${cmd}}\\left(${currentLatex}\\right)`);
                } else {
                    // Insert the command with empty arg — cursor lands inside parens
                    rowInfo.mq.write(`\\operatorname{${cmd}}\\left(`);
                }
                rowInfo.mq.focus();
            });
        });
    }

    // ── Bootstrap ───────────────────────────────────────────

    function boot(getFocusedRowInfo) {
        _getFocusedRowInfo = getFocusedRowInfo;

        _pickerBtn   = document.getElementById('matrix-picker-btn');
        _popup       = document.getElementById('matrix-size-popup');
        _sizeGrid    = document.getElementById('matrix-size-grid');
        _sizeLabel   = document.getElementById('matrix-size-label');
        _modal       = document.getElementById('matrix-modal');
        _modalTitle  = document.getElementById('matrix-modal-title');
        _modalGrid   = document.getElementById('matrix-modal-grid');
        _nameInput   = document.getElementById('matrix-name-input');
        _insertBtn   = document.getElementById('matrix-modal-insert');
        _cancelBtn   = document.getElementById('matrix-modal-cancel');
        _closeBtn    = document.getElementById('matrix-modal-close');

        if (!_pickerBtn) return; // Elements not present

        // Build the 6×6 size grid
        _buildSizeGrid();

        // Toggle popup on button click
        _pickerBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (_popup.classList.contains('open')) {
                _closePopup();
            } else {
                _openPopup();
            }
        });

        // Close popup when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#matrix-picker-wrap') && !e.target.closest('#matrix-modal')) {
                _closePopup();
            }
        });

        // Modal controls
        _insertBtn.addEventListener('click', _onInsert);
        _cancelBtn.addEventListener('click', _closeModal);
        _closeBtn.addEventListener('click', _closeModal);

        // Close modal on backdrop click
        _modal.addEventListener('click', (e) => {
            if (e.target === _modal) _closeModal();
        });

        // Escape key closes both
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                _closeModal();
                _closePopup();
            }
        });

        // Matrix command buttons (det, inv, etc.)
        _initCommandButtons();
    }

    return { boot };
})();
