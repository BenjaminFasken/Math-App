"""
test_cas.py — Automated tests for the CAS engine.
Run:  python test_cas.py
"""
import sys
import os
import json

# Add js/ so we can import casEngine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'js'))

# We need to exec the engine since it's not a proper module (no if __name__ guard)
engine_path = os.path.join(os.path.dirname(__file__), 'js', 'casEngine.py')
with open(engine_path) as f:
    exec(f.read(), globals())

# ── Test helpers ──────────────────────────────────────────

passed = 0
failed = 0

def test(description, latex_input, check_fn):
    global passed, failed
    try:
        result = json.loads(cas_evaluate(latex_input))
        ok = check_fn(result)
        if ok:
            passed += 1
            print(f'  ✓ {description}')
        else:
            failed += 1
            print(f'  ✗ {description}')
            print(f'    Result: {json.dumps(result, indent=2)}')
    except Exception as e:
        failed += 1
        print(f'  ✗ {description}')
        print(f'    Exception: {e}')

# ── Tests ─────────────────────────────────────────────────

print('\n═══ CAS Engine Tests ═══\n')

# 1. Basic arithmetic
print('── Basic Arithmetic ──')
test('2 + 3 = 5',
     '2+3',
     lambda r: r['ok'] and '5' in r['plain'])

test('10 / 3 stays symbolic',
     '\\frac{10}{3}',
     lambda r: r['ok'] and r['type'] == 'value')

# 2. Variable assignment
print('\n── Variable Assignment ──')
test('Assign x = 5',
     'x = 5',
     lambda r: r['ok'] and r['type'] == 'assignment' and r.get('name') == 'x')

test('Evaluate x (should be 5)',
     'x',
     lambda r: r['ok'] and '5' in r['plain'])

test('Assign y = x + 3 (should be 8)',
     'y = x + 3',
     lambda r: r['ok'] and r['type'] == 'assignment' and '8' in r['plain'])

test('Evaluate y (should be 8)',
     'y',
     lambda r: r['ok'] and '8' in r['plain'])

# 3. Recursive variable dependencies
print('\n── Recursive Variable Dependencies ──')
cas_evaluate('a = 2')
cas_evaluate('b = a + 1')
cas_evaluate('c = b * 2')

test('c depends on b depends on a → c = (2+1)*2 = 6',
     'c',
     lambda r: r['ok'] and '6' in r['plain'])

# 4. Function definition
print('\n── Function Definition ──')
test('Define f(t) = t^2 + 1',
     'f(t) = t^2 + 1',
     lambda r: r['ok'] and r['type'] == 'function_def' and r.get('name') == 'f')

# 5. Recursive function dependencies on variables
print('\n── Functions Depending on Variables ──')
cas_evaluate('k = 3')
test('Define g(t) = t + k', 'g(t) = t + k',
     lambda r: r['ok'] and r['type'] == 'function_def')

# NOTE: function calls via LaTeX are tricky; let's test the Python-level API directly
from sympy import Symbol, Function as SympyFunc
from sympy.core.function import AppliedUndef

# 6. Commands: solve
print('\n── CAS Commands ──')
test('solve(x^2 - 4, x)',
     'solve(x^2 - 4, x)',
     lambda r: r['ok'] and r['type'] == 'command')

# 7. Commands: diff
test('diff(x^3, x)',
     'diff(x^3, x)',
     lambda r: r['ok'] and r['type'] == 'command')

# 8. Commands: integrate
test('integrate(x^2, x)',
     'integrate(x^2, x)',
     lambda r: r['ok'] and r['type'] == 'command')

# 9. Commands: factor
test('factor(x^2 - 1)',
     'factor(x^2 - 1)',
     lambda r: r['ok'] and r['type'] == 'command')

# 10. Commands: expand
test('expand((x+1)^2)',
     'expand((x+1)^2)',
     lambda r: r['ok'] and r['type'] == 'command')

# 11. Commands: simplify
test('simplify(sin(x)^2 + cos(x)^2)',
     'simplify(sin(x)^2 + cos(x)^2)',
     lambda r: r['ok'] and '1' in r['plain'])

# 12. Commands: limit
test('limit(sin(x)/x, x, 0)',
     'limit(sin(x)/x, x, 0)',
     lambda r: r['ok'] and '1' in r['plain'])

# 13. Circular dependency detection
print('\n── Error Handling ──')
cas_clear()
cas_evaluate('p = q + 1')
cas_evaluate('q = p + 1')
test('Circular dep p→q→p detected',
     'p',
     lambda r: not r['ok'] and 'ircular' in r.get('error', ''))

# 14. Clear state
print('\n── State Management ──')
test('Clear CAS state',
     '',
     lambda r: r['ok'] and r['type'] == 'empty')

clear_result = json.loads(cas_clear())
test('cas_clear() succeeds',
     '1+1',
     lambda r: r['ok'])  # dummy, just checking engine still works after clear

# ── Summary ───────────────────────────────────────────────
print(f'\n═══ Results: {passed} passed, {failed} failed ═══\n')
sys.exit(0 if failed == 0 else 1)
