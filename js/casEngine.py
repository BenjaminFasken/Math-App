"""
casEngine.py — SymPy-based Computer Algebra System engine
==========================================================
Runs inside Pyodide (browser).  Provides:
  • Variable definitions with recursive dependency tracking
  • Function definitions with recursive dependency tracking
  • Expression evaluation / simplification
  • solve, factor, expand, diff, integrate, limit, series, …
  • LaTeX input parsing and LaTeX output rendering
  • Matrix operations (det, inv, transpose, eigenvals, rref, …)

SymEngine note:
  When python-symengine is installed (local Python), it is used as a
  fast back-end for Symbol creation and basic algebra.  In Pyodide
  (browser) SymPy is always used — SymEngine has no wasm build yet.

All public API is exposed through the  `cas_evaluate(latex_str)`  function
which returns a JSON string:
    { "ok": true,  "latex": "...", "plain": "...", "type": "..." }
    { "ok": false, "error": "..." }
"""

import json
import re
import traceback
from sympy import (
    symbols, Symbol, Function, oo, pi, E, I, S,
    sin, cos, tan, cot, sec, csc,
    asin, acos, atan, atan2,
    sinh, cosh, tanh, coth,
    asinh, acosh, atanh,
    sqrt, cbrt, root, Abs,
    log, ln, exp,
    factorial, binomial, gamma,
    floor, ceiling,
    gcd, lcm,
    Rational, Integer, Float, Pow, Mul, Add,
    simplify, factor, expand, collect, cancel, apart, together, trigsimp, radsimp,
    solve, solveset, linsolve, nsolve,
    diff, integrate, limit, series, summation, product,
    Matrix, eye, zeros, ones, det, trace, Transpose,
    BlockMatrix, ImmutableMatrix,
    Eq, Ne, Lt, Le, Gt, Ge,
    latex, pretty, N,
    FiniteSet, Interval, Union, Intersection, EmptySet, S as Singletons,
)
from sympy.matrices import MatrixBase
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

# ── Optional SymEngine back-end ──────────────────────────────────────────────
# SymEngine provides faster symbolic manipulation and mirrors most of SymPy's
# API.  In Pyodide it is not yet available (no wasm build), so we fall back
# gracefully to pure SymPy.
try:
    import symengine as _symengine  # noqa: F401
    _HAS_SYMENGINE = True
except ImportError:
    _HAS_SYMENGINE = False

# Status queryable from JS
def cas_engine_info():
    """Return JSON info about the CAS back-end."""
    return json.dumps({
        'sympy_version': __import__('sympy').__version__,
        'symengine_available': _HAS_SYMENGINE,
        'symengine_version': __import__('symengine').__version__ if _HAS_SYMENGINE else None,
    })

# ── Global CAS State ────────────────────────────────────────
# Stores user-defined variables:  name → { 'expr': <sympy expr>, 'deps': set of names }
_variables = {}

# Stores user-defined functions: name → { 'params': [sym, …], 'expr': <sympy expr>, 'deps': set }
_functions = {}

# All known symbol objects, reused across evaluations
_symbols_cache = {}

# ── Helpers ──────────────────────────────────────────────────

def _get_symbol(name):
    """Return a cached Symbol, creating if needed."""
    if name not in _symbols_cache:
        _symbols_cache[name] = Symbol(name)
    return _symbols_cache[name]


def _resolve_variable(name, visited=None):
    """
    Recursively substitute dependent variables into the expression for `name`.
    Detects circular dependencies.
    """
    if visited is None:
        visited = set()
    if name in visited:
        raise ValueError(f"Circular dependency detected involving '{name}'")
    visited.add(name)

    if name not in _variables:
        return _get_symbol(name)

    expr = _variables[name]['expr']
    # Substitute every free symbol that is itself a defined variable
    subs = {}
    for sym in expr.free_symbols:
        sn = str(sym)
        if sn in _variables:
            subs[sym] = _resolve_variable(sn, visited.copy())
    if subs:
        expr = expr.subs(subs)
    return expr


def _resolve_expr(expr, exclude_vars=None):
    """Substitute all known variables and user-defined functions into an expression.
    
    Args:
        expr: SymPy expression
        exclude_vars: set of variable name strings to NOT substitute
                      (used by calculus commands to keep the operation variable free)
    """
    exclude = exclude_vars or set()
    # First, substitute user-defined functions
    expr = _apply_user_functions(expr)
    # Then substitute variables
    subs = {}
    for sym in expr.free_symbols:
        sn = str(sym)
        if sn in _variables and sn not in exclude:
            subs[sym] = _resolve_variable(sn)
    if subs:
        expr = expr.subs(subs)
    return expr


def _apply_user_functions(expr):
    """Replace occurrences of user-defined functions in expr."""
    from sympy import Function as SympyFunction
    from sympy.core.function import AppliedUndef

    # Walk through the expression tree and replace user-defined function calls
    if isinstance(expr, AppliedUndef):
        fname = str(expr.func)
        if fname in _functions:
            fdef = _functions[fname]
            params = fdef['params']
            body = fdef['expr']
            args = expr.args
            if len(args) == len(params):
                # Substitute parameters, then recursively resolve
                sub_map = dict(zip(params, args))
                result = body.subs(sub_map)
                result = _apply_user_functions(result)
                return _resolve_expr(result)

    if hasattr(expr, 'args') and expr.args:
        new_args = [_apply_user_functions(a) for a in expr.args]
        if new_args != list(expr.args):
            return expr.func(*new_args)
    return expr


def _free_names(expr):
    """Return the set of free symbol name strings in an expression."""
    return {str(s) for s in expr.free_symbols}


# ── LaTeX Pre-processing ────────────────────────────────────

def _preprocess_latex(tex):
    """
    Clean and normalize LaTeX before feeding to SymPy's parse_latex.
    Handles common MathQuill outputs.
    """
    s = tex.strip()

    # Remove \left and \right (MathQuill inserts them)
    s = s.replace(r'\left', '').replace(r'\right', '')

    # Convert \cdot to *
    s = s.replace(r'\cdot', '*')

    # Convert \times to *
    s = s.replace(r'\times', '*')

    # Convert \div to /
    s = s.replace(r'\div', '/')

    # Convert \pm — just keep +  (CAS can't represent ±)
    s = s.replace(r'\pm', '+')

    # \operatorname{...} → just the name (for user-defined function names)
    s = re.sub(r'\\operatorname\{([^}]+)\}', r'\1', s)

    # Ensure \ln is recognized
    s = s.replace(r'\ln', r'\log')

    # Ensure common math functions have \ prefix when followed by ( or {
    # ONLY when the input already contains LaTeX commands (mixed plain/LaTeX).
    # Pure plain inputs like sin(pi) must go through parse_expr instead.
    if re.search(r'\\[a-zA-Z]', s):
        s = re.sub(
            r'(?<![\w\\])(sin|cos|tan|cot|sec|csc|arcsin|arccos|arctan'
            r'|sinh|cosh|tanh|coth|exp|log|ln|det|lim)(?=\s*[\(\{])',
            r'\\\1', s)

    # Normalize single-character superscripts by adding braces:
    # ^x → ^{x} for a single non-brace, non-backslash char.
    # Fixes e.g. \int_0^55x being mis-parsed as \int_0^{55}x.
    # In the fallback parse_expr path, _latex_to_algebra converts ^{…} → **()
    s = re.sub(r'\^\s*([^{\\\s])', r'^{\1}', s)

    # Normalize subscripts only after non-word chars (spaces, braces, parens).
    # This preserves identifiers like e_var while fixing \int _0 → \int _{0}.
    s = re.sub(r'(?<=[\s})])_\s*([^{\\\s])', r'_{\1}', s)
    # Also handle _ directly after LaTeX commands like \int_0 (no space)
    s = re.sub(r'(\\(?:int|sum|prod|lim|log|ln))_([^{\\])', r'\1_{\2}', s)

    return s


# ── Command Detection ───────────────────────────────────────

# Patterns for built-in CAS commands

_CMD_PATTERNS = {
    'solve':      re.compile(r'^\\?solve\s*\((.+)\)\s*$', re.I),
    'factor':     re.compile(r'^\\?factor\s*\((.+)\)\s*$', re.I),
    'expand':     re.compile(r'^\\?expand\s*\((.+)\)\s*$', re.I),
    'simplify':   re.compile(r'^\\?simplify\s*\((.+)\)\s*$', re.I),
    'diff':       re.compile(r'^\\?diff\s*\((.+)\)\s*$', re.I),
    'integrate':  re.compile(r'^\\?integrate\s*\((.+)\)\s*$', re.I),
    'limit':      re.compile(r'^\\?limit\s*\((.+)\)\s*$', re.I),
    'series':     re.compile(r'^\\?series\s*\((.+)\)\s*$', re.I),
    'numerical':  re.compile(r'^N\s*\((.+)\)\s*$'),
    'subs':       re.compile(r'^\\?subs\s*\((.+)\)\s*$', re.I),
    # Matrix commands
    'det':         re.compile(r'^\\?det\s*\((.+)\)\s*$', re.I),
    'inv':         re.compile(r'^\\?inv\s*\((.+)\)\s*$', re.I),
    'trace':       re.compile(r'^\\?tr(?:ace)?\s*\((.+)\)\s*$', re.I),
    'transpose':   re.compile(r'^\\?(?:transpose|trans)\s*\((.+)\)\s*$', re.I),
    'eigenvals':   re.compile(r'^\\?eigenvals?\s*\((.+)\)\s*$', re.I),
    'eigenvects':  re.compile(r'^\\?eigenvects?(?:ors?)?\s*\((.+)\)\s*$', re.I),
    'rank':        re.compile(r'^\\?rank\s*\((.+)\)\s*$', re.I),
    'rref':        re.compile(r'^\\?rref\s*\((.+)\)\s*$', re.I),
    'charpoly':    re.compile(r'^\\?charpoly\s*\((.+)\)\s*$', re.I),
    'nullspace':   re.compile(r'^\\?nullspace\s*\((.+)\)\s*$', re.I),
    'colspace':    re.compile(r'^\\?colspace\s*\((.+)\)\s*$', re.I),
}

# Detect assignment:  x = expr   or   f(x, y) = expr
_ASSIGN_VAR  = re.compile(r'^([a-zA-Z_]\w*)\s*=\s*(.+)$')
_ASSIGN_FUNC = re.compile(r'^([a-zA-Z_]\w*)\s*\(([^)]+)\)\s*=\s*(.+)$')

# ── LaTeX calculus notation: \sum, \prod, \lim ────────────
# \sum_{lower}^{upper} body  or  \prod_{lower}^{upper} body
_LATEX_SUM_PROD = re.compile(
    r'^\\(sum|prod)\s*_\{([^}]*)\}\s*\^\{([^}]*)\}\s*(.+)$'
)

# \int_{lower}^{upper} body  (also handles with trailing dx)
_LATEX_INT_DEF = re.compile(
    r'^\\int\s*_\{([^}]*)\}\s*\^\{([^}]*)\}\s*(.+)$'
)

# \lim_{var \to point} body
_LATEX_LIM_SUB = re.compile(
    r'^\\(?:lim|operatorname\{lim\})\s*_\{([^}]*?)(?:\\to|\\rightarrow|→)\s*([^}]*)\}\s*(.+)$'
)

# Bare \lim body (no subscript)
_LATEX_LIM_BARE = re.compile(
    r'^\\(?:lim|operatorname\{lim\})\s+(.+)$'
)


# Known function / constant names that should NOT become Symbol products
_KNOWN_NAMES = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'asin', 'acos', 'atan', 'atan2',
    'arcsin', 'arccos', 'arctan',
    'sinh', 'cosh', 'tanh', 'coth',
    'asinh', 'acosh', 'atanh',
    'sqrt', 'cbrt', 'root', 'abs',
    'log', 'ln', 'exp',
    'factorial', 'binomial', 'gamma',
    'floor', 'ceiling', 'ceil',
    'gcd', 'lcm',
    'pi', 'oo', 'inf',
    'solve', 'factor', 'expand', 'simplify',
    'diff', 'integrate', 'limit', 'series',
    'lim', 'int', 'sum', 'prod',
    # Matrix commands
    'det', 'inv', 'trace', 'tr', 'transpose', 'trans',
    'eigenvals', 'eigenvects', 'eigenvectors', 'rank', 'rref',
    'nullspace', 'colspace', 'charpoly',
    'Rational', 'Integer', 'Float',
    'True', 'False', 'None',
}


# ── Matrix LaTeX Parsing ────────────────────────────────────────────

# Pattern to detect a matrix environment
_MATRIX_ENV_RE = re.compile(
    r'^\\begin\{(p|b|v|B|V|small)?matrix\}(.+?)\\end\{(?:p|b|v|B|V|small)?matrix\}$',
    re.DOTALL
)


def _parse_matrix_latex(tex):
    """Parse a LaTeX matrix environment into a SymPy Matrix.

    Handles \\begin{pmatrix}, \\begin{bmatrix}, \\begin{vmatrix},
    \\begin{matrix}, etc.
    Returns a SymPy Matrix or raises ValueError on failure.
    """
    m = _MATRIX_ENV_RE.match(tex.strip())
    if not m:
        raise ValueError(f'Not a recognized matrix environment: {tex[:60]}')

    content = m.group(2)

    # Split rows on \\\ (LaTeX row separator)
    # Be careful: \\\\  in raw string is one LaTeX \\\\
    row_strs = re.split(r'\\\\', content)
    matrix_data = []
    for row_str in row_strs:
        row_str = row_str.strip()
        if not row_str:
            continue
        cells = [c.strip() for c in row_str.split('&')]
        parsed_cells = []
        for cell in cells:
            if cell == '':
                parsed_cells.append(S.Zero)
            else:
                parsed_cells.append(_safe_parse_latex(cell))
        matrix_data.append(parsed_cells)

    if not matrix_data:
        raise ValueError('Empty matrix')

    # Verify rectangular
    ncols = len(matrix_data[0])
    for i, row in enumerate(matrix_data):
        if len(row) != ncols:
            raise ValueError(f'Jagged matrix: row {i} has {len(row)} cols, expected {ncols}')

    return Matrix(matrix_data)


def _is_matrix_expr(tex):
    """Return True if tex starts with a matrix environment."""
    return bool(_MATRIX_ENV_RE.match(tex.strip()))


# Map of symbol names that should be replaced with SymPy constants after parsing
_CONSTANT_SUBS = {
    Symbol('pi'): pi,
    Symbol('e'): E,
    Symbol('i'): I,
    Symbol('oo'): oo,
    Symbol('inf'): oo,
    Symbol('infty'): oo,
}

# Multi-character names that must be preserved as single symbols
# (not split by implicit_multiplication_application).
_MULTICHAR_SYMBOLS = {
    # Greek letters
    'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'varepsilon',
    'zeta', 'eta', 'theta', 'vartheta',
    'iota', 'kappa', 'mu', 'nu', 'xi',
    'rho', 'sigma', 'tau', 'upsilon', 'phi', 'varphi',
    'chi', 'psi', 'omega',
    'Gamma', 'Delta', 'Theta', 'Lambda', 'Xi',
    'Sigma', 'Upsilon', 'Phi', 'Psi', 'Omega',
    # Special constants (handled later by _fix_constants)
    'infty', 'infinity',
}


def _fix_constants(expr):
    """Replace pi/e/i Symbols with their SymPy constant counterparts."""
    subs = {}
    for sym in expr.free_symbols:
        if sym in _CONSTANT_SUBS:
            subs[sym] = _CONSTANT_SUBS[sym]
    return expr.subs(subs) if subs else expr


def _make_result(expr, result_type, skip_numeric=False, **extra):
    """Build a JSON result string, optionally including a numeric approximation."""
    sym_latex = latex(expr)
    sym_plain = pretty(expr, use_unicode=True)
    result = {
        'ok': True,
        'latex': sym_latex,
        'plain': sym_plain,
        'type': result_type,
    }
    if not skip_numeric:
        try:
            num_val = N(expr)
            num_lat = latex(num_val)
            # Include numeric only when meaningfully different from symbolic
            if num_lat != sym_latex and not getattr(expr, 'is_Integer', False):
                result['numeric_latex'] = num_lat
                result['numeric_plain'] = pretty(num_val, use_unicode=True)
        except Exception:
            pass
    result.update(extra)
    return json.dumps(result)


def _extract_braced(s, pos):
    """Extract content between balanced braces starting at pos.
    Returns (content, end_pos) or (None, pos) if no brace at pos."""
    if pos >= len(s) or s[pos] != '{':
        return None, pos
    depth = 0
    start = pos + 1
    for i in range(pos, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[start:i], i + 1
    return None, pos


def _latex_to_algebra(tex):
    r"""Convert LaTeX constructs (\frac, \sqrt, etc.) to algebraic notation
    that parse_expr can handle.  Called when parse_latex is unavailable."""
    s = tex

    # ── \frac{num}{den} → ((num)/(den)) ──
    while True:
        idx = s.find(r'\frac')
        if idx == -1:
            break
        num, pos = _extract_braced(s, idx + 5)
        if num is None:
            break
        den, pos2 = _extract_braced(s, pos)
        if den is None:
            break
        # Recursively convert inner content
        num = _latex_to_algebra(num)
        den = _latex_to_algebra(den)
        s = s[:idx] + f'(({num})/({den}))' + s[pos2:]

    # ── \sqrt[n]{a} or \sqrt{a} ──
    while True:
        idx = s.find(r'\sqrt')
        if idx == -1:
            break
        pos = idx + 5
        if pos < len(s) and s[pos] == '[':
            # \sqrt[n]{a} → ((a)**(1/(n)))
            end_bracket = s.find(']', pos)
            if end_bracket == -1:
                break
            n_arg = s[pos + 1:end_bracket]
            pos = end_bracket + 1
            arg, pos2 = _extract_braced(s, pos)
            if arg is None:
                break
            arg = _latex_to_algebra(arg)
            n_arg = _latex_to_algebra(n_arg)
            s = s[:idx] + f'(({arg})**(1/({n_arg})))' + s[pos2:]
        else:
            # \sqrt{a} → sqrt(a)
            arg, pos2 = _extract_braced(s, pos)
            if arg is None:
                break
            arg = _latex_to_algebra(arg)
            s = s[:idx] + f'sqrt({arg})' + s[pos2:]

    # ── Superscripts: ^{exp} → **(exp) ──
    # Only convert brace-delimited exponents (single-char exponents are handled
    # by implicit_multiplication_application)
    result = []
    i = 0
    while i < len(s):
        if s[i] == '^' and i + 1 < len(s) and s[i + 1] == '{':
            exp_content, end = _extract_braced(s, i + 1)
            if exp_content is not None:
                exp_content = _latex_to_algebra(exp_content)
                result.append(f'**({exp_content})')
                i = end
                continue
        result.append(s[i])
        i += 1
    s = ''.join(result)

    return s


def _safe_parse_latex(tex):
    """Parse LaTeX with fallback to sympy_parser if parse_latex fails."""
    # If the input looks like plain math (no backslash-prefixed commands),
    # go straight to parse_expr which handles sin/cos/etc. natively.
    has_latex_commands = bool(re.search(r'\\[a-zA-Z]', tex))

    if has_latex_commands:
        try:
            result = parse_latex(tex)
            return _fix_constants(result)
        except Exception:
            pass  # fall through to algebra conversion

    # ── Convert LaTeX constructs to algebra then use parse_expr ──
    # Always run _latex_to_algebra to handle ^{exp} → **(exp) etc.,
    # even for inputs with no \ commands (brace normalization may have added them).
    algebraic = _latex_to_algebra(tex)

    # Strip remaining \commandname → commandname
    cleaned = re.sub(r'\\([a-zA-Z]+)', r'\1', algebraic)

    # Remove subscript braces so x_{1} becomes x_1 (valid Python identifier)
    cleaned = re.sub(r'_\{([^}]*)\}', r'_\1', cleaned)

    # Build local_dict — include user-defined functions, known variables,
    # Greek letters, and single-character names as symbols.
    # Multi-character unknown names are left out so that
    # implicit_multiplication_application can split them (e.g. "xy" → x*y).
    names_in_expr = set(re.findall(r'[a-zA-Z_]\w*', cleaned))
    local = {}
    for n in names_in_expr:
        if n in _functions:
            local[n] = Function(n)
        elif n in _variables:
            local[n] = _get_symbol(n)
        elif n in _MULTICHAR_SYMBOLS:
            local[n] = _get_symbol(n)
        elif n in _KNOWN_NAMES:
            pass  # built-in funcs/constants handled by parse_expr globals
        elif len(n) == 1:
            local[n] = _get_symbol(n)
        # else: multi-char unknown → don't add; implicit mult will split it
    result = parse_expr(
        cleaned,
        transformations=standard_transformations + (implicit_multiplication_application, convert_xor),
        local_dict=local,
    )
    return _fix_constants(result)


def _parse_inner(inner_tex):
    """Parse the inner part of a command like solve(...), splitting on top-level commas."""
    # Split on commas that are not inside parentheses or braces
    parts = []
    depth = 0
    current = []
    for ch in inner_tex:
        if ch in '({[':
            depth += 1
            current.append(ch)
        elif ch in ')}]':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append(''.join(current).strip())
    return parts


# ── Main Evaluation ─────────────────────────────────────────

def cas_evaluate(raw_latex):
    """
    Evaluate a LaTeX expression from the front-end.

    Returns a JSON string with:
      ok    : bool
      latex : str   (rendered LaTeX of the result)
      plain : str   (pretty-printed plaintext)
      type  : str   ('value' | 'assignment' | 'function_def' | 'command' | 'equation')
    """
    try:
        return _eval_inner(raw_latex)
    except Exception as exc:
        return json.dumps({
            'ok': False,
            'error': str(exc),
        })


def _eval_inner(raw_latex):
    tex = _preprocess_latex(raw_latex)
    if not tex:
        return json.dumps({'ok': True, 'latex': '', 'plain': '', 'type': 'empty'})

    # ── 0.  Check for CAS commands ──────────────────────────

    # For command detection we strip backslashes, but we keep a mapping
    # from the plain-text match position back to the original LaTeX.
    plain_cmd = re.sub(r'\\([a-zA-Z]+)', r'\1', tex).strip()

    for cmd_name, pat in _CMD_PATTERNS.items():
        m = pat.match(plain_cmd)
        if m:
            # Extract the inner content from the *original* LaTeX too.
            # We try matching the original first; fall back to plain match.
            m_orig = pat.match(tex.strip())
            inner = m_orig.group(1) if m_orig else m.group(1)
            return _handle_command(cmd_name, inner, tex)

    # ── 0.5  LaTeX calculus notation (\sum, \prod, \int, \lim) ──
    m = _LATEX_INT_DEF.match(tex)
    if m:
        return _handle_latex_int(m.group(1), m.group(2), m.group(3))

    m = _LATEX_SUM_PROD.match(tex)
    if m:
        return _handle_latex_sum_prod(m.group(1), m.group(2), m.group(3), m.group(4))

    m = _LATEX_LIM_SUB.match(tex)
    if m:
        return _handle_latex_limit(m.group(1), m.group(2), m.group(3))

    m = _LATEX_LIM_BARE.match(tex)
    if m:
        return _handle_latex_limit_bare(m.group(1))

    # ── 0.6  Matrix environment \begin{pmatrix}...\end{pmatrix} ──
    if _is_matrix_expr(tex):
        return _handle_matrix_literal(tex)

    # ── 1.  Detect function definition:  f(x, y) = expr ────
    m = _ASSIGN_FUNC.match(plain_cmd)
    if m:
        fname, params_str, body_tex = m.group(1), m.group(2), m.group(3)
        return _handle_function_def(fname, params_str, body_tex)

    # ── 2.  Detect variable assignment:  x = expr ──────────
    m = _ASSIGN_VAR.match(plain_cmd)
    if m:
        vname = m.group(1)
        # Re-extract body from original tex to preserve LaTeX backslash commands
        # (plain_cmd has backslashes stripped, which breaks \begin{matrix}...)
        eq_idx = tex.index('=')
        body_tex = tex[eq_idx + 1:].strip()
        # Make sure this isn't a known constant like e, i, pi
        if vname not in ('e', 'i', 'pi', 'E', 'I'):
            # Check if the body is a matrix
            body_preprocessed = _preprocess_latex(body_tex)
            if _is_matrix_expr(body_preprocessed):
                return _handle_matrix_assignment(vname, body_preprocessed)
            return _handle_var_assignment(vname, body_tex)

    # ── 3.  Check for equation (contains =) → maybe solve? ─
    if '=' in tex and not tex.startswith('='):
        parts = tex.split('=', 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            try:
                lhs = _safe_parse_latex(_preprocess_latex(parts[0]))
                rhs = _safe_parse_latex(_preprocess_latex(parts[1]))
                eq = Eq(lhs, rhs)
                eq_resolved = _resolve_expr(eq)
                result = simplify(eq_resolved)
                return _make_result(result, 'equation')
            except Exception:
                pass  # Fall through to plain evaluation

    # ── 4.  Plain expression evaluation ─────────────────────
    expr = _safe_parse_latex(tex)
    resolved = _resolve_expr(expr)

    # If substitution yielded a matrix (e.g. user typed a matrix variable name)
    if isinstance(resolved, MatrixBase):
        return _make_matrix_result(resolved, 'value')

    result = simplify(resolved)

    # Evaluate Integral / Derivative objects that simplify didn't resolve
    if hasattr(result, 'doit'):
        try:
            evaled = result.doit()
            if evaled is not result:
                result = simplify(evaled)
        except Exception:
            pass

    if isinstance(result, MatrixBase):
        return _make_matrix_result(result, 'value')

    return _make_result(result, 'value')


# ── Command Handlers ────────────────────────────────────────

def _handle_command(cmd, inner_tex, full_tex):
    parts = _parse_inner(inner_tex)

    if cmd == 'solve':
        return _cmd_solve(parts)
    elif cmd == 'factor':
        expr = _safe_parse_latex(parts[0])
        result = factor(_resolve_expr(expr))
    elif cmd == 'expand':
        expr = _safe_parse_latex(parts[0])
        result = expand(_resolve_expr(expr))
    elif cmd == 'simplify':
        expr = _safe_parse_latex(parts[0])
        result = simplify(_resolve_expr(expr))
    elif cmd == 'diff':
        return _cmd_diff(parts)
    elif cmd == 'integrate':
        return _cmd_integrate(parts)
    elif cmd == 'limit':
        return _cmd_limit(parts)
    elif cmd == 'series':
        return _cmd_series(parts)
    elif cmd == 'numerical':
        expr = _safe_parse_latex(parts[0])
        prec = int(parts[1]) if len(parts) > 1 else 15
        result = N(_resolve_expr(expr), prec)
    elif cmd == 'subs':
        return _cmd_subs(parts)
    # ── Matrix commands ──────────────────────────────────────────
    elif cmd == 'det':
        return _cmd_mat_det(parts)
    elif cmd == 'inv':
        return _cmd_mat_inv(parts)
    elif cmd == 'trace':
        return _cmd_mat_trace(parts)
    elif cmd == 'transpose':
        return _cmd_mat_transpose(parts)
    elif cmd == 'eigenvals':
        return _cmd_mat_eigenvals(parts)
    elif cmd == 'eigenvects':
        return _cmd_mat_eigenvects(parts)
    elif cmd == 'rank':
        return _cmd_mat_rank(parts)
    elif cmd == 'rref':
        return _cmd_mat_rref(parts)
    elif cmd == 'charpoly':
        return _cmd_mat_charpoly(parts)
    elif cmd == 'nullspace':
        return _cmd_mat_nullspace(parts)
    elif cmd == 'colspace':
        return _cmd_mat_colspace(parts)
    else:
        return json.dumps({'ok': False, 'error': f'Unknown command: {cmd}'})

    return _make_result(result, 'command')


def _cmd_solve(parts):
    """solve(expr, var)  or  solve(expr)  — solve equation for variable."""
    expr = _safe_parse_latex(parts[0])
    if len(parts) >= 2:
        var = _get_symbol(parts[1].strip())
    else:
        free = list(expr.free_symbols)
        if not free:
            return json.dumps({'ok': False, 'error': 'No free variable to solve for'})
        var = free[0]

    # Don't substitute the solve variable
    expr = _resolve_expr(expr, exclude_vars={str(var)})

    if isinstance(expr, Eq):
        result = solve(expr, var)
    else:
        result = solve(expr, var)

    return _make_result(result, 'command', skip_numeric=True)


def _cmd_diff(parts):
    """diff(expr, var) or diff(expr, var, n)"""
    expr = _safe_parse_latex(parts[0])
    var = _get_symbol(parts[1].strip()) if len(parts) > 1 else list(expr.free_symbols)[0]
    order = int(parts[2]) if len(parts) > 2 else 1
    # Don't substitute the differentiation variable
    expr = _resolve_expr(expr, exclude_vars={str(var)})
    result = diff(expr, var, order)
    return _make_result(result, 'command')


def _cmd_integrate(parts):
    """integrate(expr, var)  or  integrate(expr, var, a, b) for definite integrals."""
    expr = _safe_parse_latex(parts[0])
    var = _get_symbol(parts[1].strip()) if len(parts) > 1 else list(expr.free_symbols)[0]
    # Don't substitute the integration variable
    expr = _resolve_expr(expr, exclude_vars={str(var)})
    if len(parts) >= 4:
        a = _safe_parse_latex(parts[2])
        b = _safe_parse_latex(parts[3])
        result = integrate(expr, (var, a, b))
    else:
        result = integrate(expr, var)
    return _make_result(result, 'command')


def _cmd_limit(parts):
    """limit(expr, var, point)"""
    expr = _safe_parse_latex(parts[0])
    var = _get_symbol(parts[1].strip())
    # Don't substitute the limit variable
    expr = _resolve_expr(expr, exclude_vars={str(var)})
    point = _safe_parse_latex(parts[2])
    result = limit(expr, var, point)
    return _make_result(result, 'command')


def _cmd_series(parts):
    """series(expr, var, point, n)"""
    expr = _safe_parse_latex(parts[0])
    var = _get_symbol(parts[1].strip()) if len(parts) > 1 else list(expr.free_symbols)[0]
    # Don't substitute the series variable
    expr = _resolve_expr(expr, exclude_vars={str(var)})
    point = _safe_parse_latex(parts[2]) if len(parts) > 2 else S.Zero
    n = int(parts[3]) if len(parts) > 3 else 6
    result = series(expr, var, point, n)
    return _make_result(result, 'command', skip_numeric=True)


def _cmd_subs(parts):
    """subs(expr, old, new)"""
    expr = _safe_parse_latex(parts[0])
    expr = _resolve_expr(expr)
    old = _safe_parse_latex(parts[1])
    new = _safe_parse_latex(parts[2])
    result = expr.subs(old, new)
    result = simplify(result)
    return _make_result(result, 'command')


# ── Matrix Handlers ─────────────────────────────────────────

def _resolve_matrix_arg(tex):
    """Parse a matrix argument — either a matrix literal or a named matrix variable."""
    tex = tex.strip()
    # Already a matrix environment?
    if _is_matrix_expr(tex):
        return _parse_matrix_latex(tex)
    # A named variable holding a matrix?
    name = re.sub(r'\\([a-zA-Z]+)', r'\1', tex).strip()
    if name in _variables:
        val = _resolve_variable(name)
        if isinstance(val, MatrixBase):
            return val
    # Try parsing as an expression (e.g. A*B where A, B are matrix vars)
    try:
        return _resolve_matrix_expr(tex)
    except Exception:
        pass
    raise ValueError(f'Cannot interpret as a matrix: {tex[:80]}')


def _resolve_matrix_expr(tex):
    """Attempt to evaluate a matrix expression involving defined matrix variables."""
    # Replace variable names with their stored matrix values
    # Simple approach: substitute each known matrix variable
    result = _safe_parse_latex(tex)
    for sym in list(result.free_symbols):
        n = str(sym)
        if n in _variables:
            val = _resolve_variable(n)
            result = result.subs(sym, val)
    return result


def _handle_matrix_literal(tex):
    """Evaluate a bare matrix literal."""
    try:
        mat = _parse_matrix_latex(tex)
        # Resolve any symbolic entries that are defined variables
        mat = mat.applyfunc(lambda e: _resolve_expr(e))
        return _make_matrix_result(mat, 'value')
    except Exception as exc:
        return json.dumps({'ok': False, 'error': str(exc)})


def _handle_matrix_assignment(name, matrix_tex):
    """Assign a matrix to a variable name."""
    try:
        mat = _parse_matrix_latex(matrix_tex)
        mat = mat.applyfunc(lambda e: _resolve_expr(e))
        # Store as an ImmutableMatrix so it behaves like a scalar in subs
        _variables[name] = {'expr': ImmutableMatrix(mat), 'deps': set()}
        return _make_matrix_result(mat, 'assignment', name=name)
    except Exception as exc:
        return json.dumps({'ok': False, 'error': str(exc)})


def _make_matrix_result(mat, result_type, **extra):
    """Build a JSON result for a matrix, with LaTeX and plain rendering."""
    sym_latex = latex(mat)
    sym_plain = pretty(mat, use_unicode=True)
    result = {
        'ok': True,
        'latex': sym_latex,
        'plain': sym_plain,
        'type': result_type,
        'is_matrix': True,
        'rows': mat.rows,
        'cols': mat.cols,
    }
    result.update(extra)
    return json.dumps(result)


def _cmd_mat_det(parts):
    """det(M) — determinant of a matrix."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    if mat.rows != mat.cols:
        return json.dumps({'ok': False, 'error': f'det() requires a square matrix, got {mat.rows}×{mat.cols}'})
    result = simplify(mat.det())
    return _make_result(result, 'command')


def _cmd_mat_inv(parts):
    """inv(M) — matrix inverse."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    if mat.rows != mat.cols:
        return json.dumps({'ok': False, 'error': f'inv() requires a square matrix, got {mat.rows}×{mat.cols}'})
    try:
        result = mat.inv()
        return _make_matrix_result(result, 'command')
    except Exception as exc:
        return json.dumps({'ok': False, 'error': f'Matrix is singular or non-invertible: {exc}'})


def _cmd_mat_trace(parts):
    """trace(M) — sum of diagonal elements."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    result = simplify(trace(mat))
    return _make_result(result, 'command')


def _cmd_mat_transpose(parts):
    """transpose(M) — matrix transpose."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    return _make_matrix_result(mat.T, 'command')


def _cmd_mat_eigenvals(parts):
    """eigenvals(M) — eigenvalues with multiplicities."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    if mat.rows != mat.cols:
        return json.dumps({'ok': False, 'error': 'eigenvals() requires a square matrix'})
    evals = mat.eigenvals()
    # Format: {eigenvalue: multiplicity, ...}
    sym_latex = r'\left\{' + ',\ '.join(
        f'{latex(v)} \\text{{ (mult. {m})}}'
        for v, m in evals.items()
    ) + r'\right\}'
    sym_plain = '{' + ', '.join(
        f'{pretty(v, use_unicode=True)} (mult. {m})'
        for v, m in evals.items()
    ) + '}'
    return json.dumps({'ok': True, 'latex': sym_latex, 'plain': sym_plain, 'type': 'command'})


def _cmd_mat_eigenvects(parts):
    """eigenvects(M) — eigenvalues and their eigenvectors."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    if mat.rows != mat.cols:
        return json.dumps({'ok': False, 'error': 'eigenvects() requires a square matrix'})
    evects = mat.eigenvects()
    # Format: [(eigenvalue, multiplicity, [vectors]), ...]
    parts_latex = []
    parts_plain = []
    for eigenval, mult, vectors in evects:
        vecs_latex = ', '.join(latex(v) for v in vectors)
        vecs_plain = ', '.join(pretty(v, use_unicode=True) for v in vectors)
        parts_latex.append(rf'\lambda={latex(eigenval)}\ (\times{mult}):\ [{vecs_latex}]')
        parts_plain.append(f'λ={pretty(eigenval, use_unicode=True)} (×{mult}): [{vecs_plain}]')
    return json.dumps({
        'ok': True,
        'latex': r'\\'.join(parts_latex),
        'plain': '\n'.join(parts_plain),
        'type': 'command',
    })


def _cmd_mat_rank(parts):
    """rank(M) — matrix rank."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    result = Integer(mat.rank())
    return _make_result(result, 'command')


def _cmd_mat_rref(parts):
    """rref(M) — reduced row echelon form."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    rref_mat, pivots = mat.rref()
    result = _make_matrix_result(rref_mat, 'command')
    # Inject pivot info into result
    r = json.loads(result)
    r['pivots'] = list(pivots)
    r['plain'] += f'\nPivot columns: {list(pivots)}'
    return json.dumps(r)


def _cmd_mat_charpoly(parts):
    """charpoly(M) — characteristic polynomial det(λI - M)."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    if mat.rows != mat.cols:
        return json.dumps({'ok': False, 'error': 'charpoly() requires a square matrix'})
    lam = Symbol('lambda')
    poly = mat.charpoly(lam)
    result = poly.as_expr()
    return _make_result(result, 'command')


def _cmd_mat_nullspace(parts):
    """nullspace(M) — basis vectors of the null space."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    basis = mat.nullspace()
    if not basis:
        return json.dumps({'ok': True, 'latex': r'\{0\}', 'plain': '{0}', 'type': 'command'})
    sym_latex = r'\left\{' + ',\ '.join(latex(v) for v in basis) + r'\right\}'
    sym_plain = '{' + ', '.join(pretty(v, use_unicode=True) for v in basis) + '}'
    return json.dumps({'ok': True, 'latex': sym_latex, 'plain': sym_plain, 'type': 'command'})


def _cmd_mat_colspace(parts):
    """colspace(M) — basis vectors of the column space."""
    mat = _resolve_matrix_arg(parts[0])
    if not isinstance(mat, MatrixBase):
        return json.dumps({'ok': False, 'error': 'Argument is not a matrix'})
    basis = mat.columnspace()
    if not basis:
        return json.dumps({'ok': True, 'latex': r'\{0\}', 'plain': '{0}', 'type': 'command'})
    sym_latex = r'\left\{' + ',\ '.join(latex(v) for v in basis) + r'\right\}'
    sym_plain = '{' + ', '.join(pretty(v, use_unicode=True) for v in basis) + '}'
    return json.dumps({'ok': True, 'latex': sym_latex, 'plain': sym_plain, 'type': 'command'})


# ── LaTeX Calculus Notation Handlers ────────────────────────

def _handle_latex_int(lower_tex, upper_tex, body_tex):
    """Handle \\int_{a}^{b} body or \\int_{a}^{b} body dx."""
    # Strip trailing d<var> (variable of integration notation)
    body_tex = re.sub(r'\s*d([a-zA-Z_]\w*)\s*$', '', body_tex).strip()

    lower_expr = _safe_parse_latex(lower_tex)
    upper_expr = _safe_parse_latex(upper_tex)
    body_expr = _safe_parse_latex(body_tex)

    # Infer integration variable from body free symbols
    body_expr_resolved_check = _resolve_expr(body_expr)
    free = list(body_expr_resolved_check.free_symbols)
    # Prefer 'x' if present, otherwise take the first free symbol
    var = next((s for s in free if str(s) == 'x'), free[0] if free else None)
    if var is None:
        # Constant integrand — integrate with dummy variable
        from sympy import Dummy
        var = Dummy('x')

    body_expr = _resolve_expr(body_expr, exclude_vars={str(var)})
    result = integrate(body_expr, (var, lower_expr, upper_expr))
    return _make_result(result, 'value')


def _handle_latex_sum_prod(op, lower_tex, upper_tex, body_tex):
    """Handle \\sum_{a}^{b} body or \\prod_{a}^{b} body."""
    # Strip trailing d<var> from body (not meaningful for sum/prod)
    body_tex = re.sub(r'\s*d([a-zA-Z])\s*$', '', body_tex).strip()

    # Check if lower bound contains variable assignment like "n=0"
    lower_assign = re.match(r'^\s*([a-zA-Z_]\w*)\s*=\s*(.+)$', lower_tex)
    if lower_assign:
        var_name = lower_assign.group(1)
        lower_val_tex = lower_assign.group(2)
        var = _get_symbol(var_name)
        lower_expr = _safe_parse_latex(lower_val_tex)
    else:
        lower_expr = _safe_parse_latex(lower_tex)
        var = None  # will infer from body

    upper_expr = _safe_parse_latex(upper_tex)
    body_expr = _safe_parse_latex(body_tex)

    # Infer variable from body if not explicitly given
    if var is None:
        free = list(body_expr.free_symbols)
        if free:
            var = free[0]
        else:
            return json.dumps({'ok': False, 'error': f'Cannot determine variable for \\{op}'})

    # Resolve body but keep the summation/product variable free
    body_expr = _resolve_expr(body_expr, exclude_vars={str(var)})

    if op == 'sum':
        result = summation(body_expr, (var, lower_expr, upper_expr))
    elif op == 'prod':
        result = product(body_expr, (var, lower_expr, upper_expr))
    else:
        return json.dumps({'ok': False, 'error': f'Unknown operator: {op}'})

    return _make_result(result, 'value')


def _handle_latex_limit(var_tex, point_tex, body_tex):
    """Handle \\lim_{x\\to a} body."""
    var = _get_symbol(var_tex.strip())
    point = _safe_parse_latex(point_tex.strip())
    body_expr = _safe_parse_latex(body_tex)
    body_expr = _resolve_expr(body_expr, exclude_vars={str(var)})
    result = limit(body_expr, var, point)
    return _make_result(result, 'value')


def _handle_latex_limit_bare(body_tex):
    """Handle bare \\lim body (no subscript specification).
    Without a variable and approach point, we cannot evaluate the limit.
    Return the body expression with \\lim notation preserved."""
    body_expr = _safe_parse_latex(body_tex)
    body_expr = _resolve_expr(body_expr)
    result = simplify(body_expr)
    sym_latex = r'\lim ' + latex(result)
    sym_plain = 'lim ' + pretty(result, use_unicode=True)
    return json.dumps({
        'ok': True,
        'latex': sym_latex,
        'plain': sym_plain,
        'type': 'value',
    })
    return _make_result(result, 'command')


# ── Assignment Handlers ─────────────────────────────────────

def _handle_var_assignment(name, body_tex):
    """Process:  x = <expression>"""
    expr = _safe_parse_latex(body_tex)

    # Check for circular dependency
    deps = _free_names(expr)
    # Resolve to make sure there's no cycle
    test_visited = {name}
    for dep_name in deps:
        if dep_name in _variables:
            try:
                _resolve_variable(dep_name, test_visited.copy())
            except ValueError as e:
                return json.dumps({'ok': False, 'error': str(e)})

    _variables[name] = {'expr': expr, 'deps': deps}

    # Compute the fully resolved value
    resolved = _resolve_variable(name)
    simplified = simplify(resolved)

    return _make_result(simplified, 'assignment', name=name)


def _handle_function_def(fname, params_str, body_tex):
    """Process:  f(x, y) = <expression>"""
    param_names = [p.strip() for p in params_str.split(',')]
    param_syms = [_get_symbol(p) for p in param_names]
    expr = _safe_parse_latex(body_tex)

    _functions[fname] = {
        'params': param_syms,
        'expr': expr,
        'deps': _free_names(expr) - set(param_names),
    }

    return _make_result(expr, 'function_def', skip_numeric=True, name=fname, params=param_names)


# ── Utility: list all defined symbols ───────────────────────

def cas_get_state():
    """Return JSON summary of all defined variables and functions."""
    vars_info = {}
    for name, info in _variables.items():
        vars_info[name] = {
            'latex': latex(info['expr']),
            'deps': list(info['deps']),
        }

    funcs_info = {}
    for name, info in _functions.items():
        funcs_info[name] = {
            'latex': latex(info['expr']),
            'params': [str(p) for p in info['params']],
            'deps': list(info['deps']),
        }

    return json.dumps({'variables': vars_info, 'functions': funcs_info})


def cas_clear():
    """Reset all CAS state."""
    _variables.clear()
    _functions.clear()
    _symbols_cache.clear()
    return json.dumps({'ok': True})
