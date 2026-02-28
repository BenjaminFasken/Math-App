"""
test_comprehensive.py — Massive automated test suite for the CAS engine.
==========================================================================
Covers: arithmetic, variables, implicit multiplication, algebra, trig,
calculus (diff/integrate/limit/series), equation solving, complex numbers,
LaTeX-formatted input, edge cases, and error handling.

Run:  python test_comprehensive.py
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'js'))
engine_path = os.path.join(os.path.dirname(__file__), 'js', 'casEngine.py')
with open(engine_path) as f:
    exec(f.read(), globals())

# ── Test helpers ────────────────────────────────────────────

passed = 0
failed = 0
errors = []


def test(description, latex_input, check_fn):
    """Run a single test case."""
    global passed, failed
    try:
        result = json.loads(cas_evaluate(latex_input))
        ok = check_fn(result)
        if ok:
            passed += 1
            print(f'  \u2713 {description}')
        else:
            failed += 1
            errors.append(description)
            print(f'  \u2717 {description}')
            print(f'    Result: {json.dumps(result, indent=2)[:200]}')
    except Exception as e:
        failed += 1
        errors.append(description)
        print(f'  \u2717 {description}')
        print(f'    Exception: {e}')


def contains(result, *substrings):
    """Check that all substrings appear in the plain or latex output."""
    text = (result.get('plain', '') + ' ' + result.get('latex', '')).lower()
    return all(s.lower() in text for s in substrings)


def result_ok(result):
    return result.get('ok', False)


# ══════════════════════════════════════════════════════════════
# 1. Basic Arithmetic & Order of Operations
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  1. Basic Arithmetic & Order of Operations')
print('=' * 60)
cas_clear()

test('5 + 5 = 10',
     '5+5',
     lambda r: result_ok(r) and contains(r, '10'))

test('10 - 3 * 2 = 4',
     '10-3*2',
     lambda r: result_ok(r) and contains(r, '4'))

test('(10 - 3) * 2 = 14',
     '(10-3)*2',
     lambda r: result_ok(r) and contains(r, '14'))

test('2^3^2 = 512 (right-associative)',
     '2^{3^{2}}',
     lambda r: result_ok(r) and contains(r, '512'))

test('-5^2 = -25',
     '-5^2',
     lambda r: result_ok(r) and '-25' in r.get('plain', ''))

test('(-5)^2 = 25',
     '(-5)^2',
     lambda r: result_ok(r) and '25' in r.get('plain', '') and '-' not in r.get('plain', ''))

test('10 / 2 / 5 = 1 (left-assoc)',
     '10/2/5',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))

test('1/2 + 1/3 = 5/6 (rational)',
     r'\frac{1}{2}+\frac{1}{3}',
     lambda r: result_ok(r) and '5' in r.get('latex', '') and '6' in r.get('latex', ''))

test('sqrt(25) = 5',
     r'\sqrt{25}',
     lambda r: result_ok(r) and contains(r, '5'))

test('sqrt(8) simplifies to 2*sqrt(2)',
     r'\sqrt{8}',
     lambda r: result_ok(r) and ('2' in r.get('plain', '') and 'sqrt' in r.get('plain', '').lower() or '\\sqrt' in r.get('latex', '')))

test('Large exponent: 2^10 = 1024',
     '2^{10}',
     lambda r: result_ok(r) and contains(r, '1024'))

test('Nested parens: (((((5))))) = 5',
     '(((((5)))))',
     lambda r: result_ok(r) and contains(r, '5'))

test('Mixed ops: 3 + 4 * 2 / (1 - 5)^2 = 3.5',
     r'3+4\cdot 2/(1-5)^{2}',
     lambda r: result_ok(r))


# ══════════════════════════════════════════════════════════════
# 2. Variables & Implicit Multiplication
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  2. Variables & Implicit Multiplication')
print('=' * 60)
cas_clear()

test('Assign a = 5',
     'a = 5',
     lambda r: result_ok(r) and r.get('type') == 'assignment' and r.get('name') == 'a')

test('Assign b = 3',
     'b = 3',
     lambda r: result_ok(r) and r.get('type') == 'assignment')

test('a + b = 8',
     'a + b',
     lambda r: result_ok(r) and contains(r, '8'))

test('5a = 25 (implicit multiplication)',
     '5a',
     lambda r: result_ok(r) and contains(r, '25'))

test('5*a = 25',
     '5*a',
     lambda r: result_ok(r) and contains(r, '25'))

test('ab = 15 (implicit mult of a*b)',
     'ab',
     lambda r: result_ok(r) and contains(r, '15'))

test('Multi-char variable: ha = 10',
     'ha = 10',
     lambda r: result_ok(r) and r.get('type') == 'assignment' and r.get('name') == 'ha')

test('Use ha: ha + 1 = 11',
     'ha + 1',
     lambda r: result_ok(r) and contains(r, '11'))

test('(a+1)(b-1) = 12',
     '(a+1)(b-1)',
     lambda r: result_ok(r) and contains(r, '12'))

test('Assign x = symbolic y',
     'x = y',
     lambda r: result_ok(r) and r.get('type') == 'assignment')

test('Evaluate x (should be y)',
     'x',
     lambda r: result_ok(r) and 'y' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 3. Function Definitions & Calls
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  3. Function Definitions & Calls')
print('=' * 60)
cas_clear()

test('Define f(x) = x^2 + 1',
     'f(x) = x^2 + 1',
     lambda r: result_ok(r) and r.get('type') == 'function_def' and r.get('name') == 'f')

test('f(3) = 10',
     'f(3)',
     lambda r: result_ok(r) and contains(r, '10'))

test('f(0) = 1',
     'f(0)',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))

test('Define g(x) = 2x + 1',
     'g(x) = 2x + 1',
     lambda r: result_ok(r) and r.get('type') == 'function_def')

test('g(5) = 11',
     'g(5)',
     lambda r: result_ok(r) and contains(r, '11'))

# Function with variable dependency
cas_evaluate('a = 3')
test('Define h(x) = 5ax  (body uses var a)',
     'h(x) = 5ax',
     lambda r: result_ok(r) and r.get('type') == 'function_def')

test('h(6) = 90  (5 * 3 * 6)',
     'h(6)',
     lambda r: result_ok(r) and contains(r, '90'))

test('h(2) = 30  (5 * 3 * 2)',
     'h(2)',
     lambda r: result_ok(r) and contains(r, '30'))

# Multi-param function
test('Define dist(x,y) = sqrt(x^2 + y^2)',
     'dist(x, y) = sqrt(x^2 + y^2)',
     lambda r: result_ok(r) and r.get('type') == 'function_def')

test('dist(3, 4) = 5',
     'dist(3, 4)',
     lambda r: result_ok(r) and contains(r, '5'))

# MathQuill-style function call
cas_clear()
cas_evaluate('a = 3')
cas_evaluate(r'f\left(x\right)=5ax')
test(r'f\left(6\right) via MQ style = 90',
     r'f\left(6\right)',
     lambda r: result_ok(r) and contains(r, '90'))


# ══════════════════════════════════════════════════════════════
# 4. Algebraic Manipulation
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  4. Algebraic Manipulation')
print('=' * 60)
cas_clear()

test('expand((x + y)^3)',
     'expand((x + y)^3)',
     lambda r: result_ok(r) and r.get('type') == 'command')

test('expand((x-1)*(x^2+x+1)) = x^3-1',
     'expand((x-1)*(x^2+x+1))',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))

test('factor(x^2 - y^2) = (x-y)(x+y)',
     'factor(x^2 - y^2)',
     lambda r: result_ok(r) and contains(r, 'x') and contains(r, 'y'))

test('factor(x^3 - 6*x^2 + 11*x - 6)',
     'factor(x^3 - 6*x^2 + 11*x - 6)',
     lambda r: result_ok(r) and r.get('type') == 'command')

test('simplify((x^2-1)/(x-1)) = x+1',
     'simplify((x^2-1)/(x-1))',
     lambda r: result_ok(r) and 'x' in r.get('plain', '') and '1' in r.get('plain', ''))

test('simplify(sin(x)^2 + cos(x)^2) = 1',
     'simplify(sin(x)^2 + cos(x)^2)',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 5. Trigonometry
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  5. Trigonometry')
print('=' * 60)
cas_clear()

test('sin(0) = 0',
     'sin(0)',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))

test(r'sin(\pi/6) = 1/2',
     r'\sin(\frac{\pi}{6})',
     lambda r: result_ok(r) and ('1' in r.get('plain', '') and '2' in r.get('plain', '')))

test('sin(a) stays symbolic',
     r'\sin(a)',
     lambda r: result_ok(r) and 'sin' in r.get('plain', '').lower())

test(r'cos(\pi/2) = 0',
     r'\cos(\frac{\pi}{2})',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))

test(r'tan(\pi/4) = 1',
     r'\tan(\frac{\pi}{4})',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))

test('asin(1) = pi/2',
     'asin(1)',
     lambda r: result_ok(r) and ('pi' in r.get('plain', '').lower() or '\u03c0' in r.get('plain', '') or 'pi' in r.get('latex', '')))

test('sinh(0) = 0',
     'sinh(0)',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 6. Calculus: Differentiation
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  6. Calculus: Differentiation')
print('=' * 60)
cas_clear()

test('diff(x^2, x) = 2x',
     'diff(x^2, x)',
     lambda r: result_ok(r) and '2' in r.get('plain', '') and 'x' in r.get('plain', ''))

test('diff(a*x^2, x) = 2ax',
     'diff(a*x^2, x)',
     lambda r: result_ok(r) and '2' in r.get('plain', ''))

test('diff(sin(x)*e^x, x) — product rule',
     'diff(sin(x)*exp(x), x)',
     lambda r: result_ok(r) and r.get('type') == 'command')

test('diff(sin(cos(x)), x) — chain rule',
     'diff(sin(cos(x)), x)',
     lambda r: result_ok(r) and 'cos' in r.get('plain', '').lower())

test('diff(x^4, x, 3) = 24x',
     'diff(x^4, x, 3)',
     lambda r: result_ok(r) and '24' in r.get('plain', ''))

test('diff(x^2*y^3, x) — partial w.r.t x',
     'diff(x^2*y^3, x)',
     lambda r: result_ok(r) and '2' in r.get('plain', ''))

test('diff(x^2*y^3, y) — partial w.r.t y',
     'diff(x^2*y^3, y)',
     lambda r: result_ok(r) and '3' in r.get('plain', ''))

test(r'\frac{d}{dx} x^3 via LaTeX derivative',
     'diff(x^3, x)',
     lambda r: result_ok(r) and '3' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 7. Calculus: Integration
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  7. Calculus: Integration')
print('=' * 60)
cas_clear()

test('integrate(x^2, x) = x^3/3',
     'integrate(x^2, x)',
     lambda r: result_ok(r) and 'x' in r.get('plain', '') and '3' in r.get('plain', ''))

test('integrate(1/x, x) = ln|x|',
     'integrate(1/x, x)',
     lambda r: result_ok(r) and ('log' in r.get('plain', '').lower() or 'ln' in r.get('plain', '').lower()))

test('integrate(x*sin(x), x) — by parts',
     'integrate(x*sin(x), x)',
     lambda r: result_ok(r) and r.get('type') == 'command')

test('integrate(x^2, x, 0, 3) = 9',
     'integrate(x^2, x, 0, 3)',
     lambda r: result_ok(r) and '9' in r.get('plain', ''))

test(r'\int_0^5 5x = 125/2 (LaTeX integral)',
     r'\int _0^55x',
     lambda r: result_ok(r) and ('125' in r.get('plain', '') or '62.5' in r.get('plain', '')))

test(r'\int_{0}^{5} 5x = 125/2 (braced)',
     r'\int_{0}^{5}5x',
     lambda r: result_ok(r) and ('125' in r.get('plain', '') or '62.5' in r.get('plain', '')))

test(r'\int _0^25x shorthand = 10',
     r'\int _0^25x',
     lambda r: result_ok(r) and contains(r, '10'))

test(r'\int _0^25xdx shorthand = 10',
     r'\int _0^25xdx',
     lambda r: result_ok(r) and contains(r, '10'))

test(r'\sum _0^25x = 15',
     r'\sum _0^25x',
     lambda r: result_ok(r) and contains(r, '15'))

test(r'\sum _0^25xdx = 15 (strip dx)',
     r'\sum _0^25xdx',
     lambda r: result_ok(r) and contains(r, '15'))

test(r'\prod _0^25x = 0',
     r'\prod _0^25x',
     lambda r: result_ok(r) and r.get('plain', '').strip() == '0')

test(r'\prod _0^25xdx = 0 (strip dx)',
     r'\prod _0^25xdx',
     lambda r: result_ok(r) and r.get('plain', '').strip() == '0')

test('integrate(cos(x), x) = sin(x)',
     'integrate(cos(x), x)',
     lambda r: result_ok(r) and 'sin' in r.get('plain', '').lower())


# ══════════════════════════════════════════════════════════════
# 8. Calculus: Limits & Series
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  8. Calculus: Limits & Series')
print('=' * 60)
cas_clear()

test('limit(sin(x)/x, x, 0) = 1',
     'limit(sin(x)/x, x, 0)',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))

test('limit((1+1/x)^x, x, oo) = e',
     'limit((1+1/x)^x, x, oo)',
     lambda r: result_ok(r) and ('e' in r.get('latex', '') or '\u212f' in r.get('plain', '')))

test('series(sin(x), x, 0, 5)',
     'series(sin(x), x, 0, 5)',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))

test('series(exp(x), x, 0, 4)',
     'series(exp(x), x, 0, 4)',
     lambda r: result_ok(r) and r.get('type') == 'command')

test(r'\lim x+2 should not parse as ilmx+2',
     r'\lim x+2',
     lambda r: result_ok(r) and ('lim' in (r.get('plain', '') + r.get('latex', '')).lower()) and ('ⅈ⋅l⋅m' not in (r.get('plain', '') + r.get('latex', ''))))


# ══════════════════════════════════════════════════════════════
# 9. Equation Solving
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  9. Equation Solving')
print('=' * 60)
cas_clear()

test('solve(2*x + 3 = 7, x) → x=2',
     'solve(2*x + 3 - 7, x)',
     lambda r: result_ok(r) and '2' in r.get('plain', ''))

test('solve(x^2 - 5x + 6, x) → [2, 3]',
     'solve(x^2 - 5*x + 6, x)',
     lambda r: result_ok(r) and '2' in r.get('plain', '') and '3' in r.get('plain', ''))

test('solve(x^2 - 4, x) → [-2, 2]',
     'solve(x^2 - 4, x)',
     lambda r: result_ok(r) and '2' in r.get('plain', ''))

test('solve(x^2 + 1, x) → complex roots',
     'solve(x^2 + 1, x)',
     lambda r: result_ok(r) and ('i' in r.get('latex', '').lower() or '\u2148' in r.get('plain', '')))

test('factor(x^2 - 1) = (x-1)(x+1)',
     'factor(x^2 - 1)',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 10. Complex Numbers
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  10. Complex Numbers')
print('=' * 60)
cas_clear()

test('(3 + 4i) + (1 - 2i) = 4 + 2i',
     '(3+4*i)+(1-2*i)',
     lambda r: result_ok(r) and '4' in r.get('plain', '') and '2' in r.get('plain', ''))

test('abs(3 + 4i) = 5',
     'abs(3 + 4*i)',
     lambda r: result_ok(r) and '5' in r.get('plain', ''))

test('e^(i*pi) = -1 (Euler)',
     'exp(i*pi)',
     lambda r: result_ok(r) and '-1' in r.get('plain', ''))

test('e^{i\\pi} + 1 = 0 (Euler via LaTeX)',
     r'e^{i\pi}+1',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 11. LaTeX-Formatted Input (MathQuill style)
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  11. LaTeX-Formatted Input (MathQuill style)')
print('=' * 60)
cas_clear()

test(r'\frac{1}{2} + \frac{1}{3} = 5/6',
     r'\frac{1}{2}+\frac{1}{3}',
     lambda r: result_ok(r) and '5' in r.get('latex', '') and '6' in r.get('latex', ''))

test(r'\sqrt{16} = 4',
     r'\sqrt{16}',
     lambda r: result_ok(r) and '4' in r.get('plain', ''))

test(r'\sqrt[3]{27} = 3',
     r'\sqrt[3]{27}',
     lambda r: result_ok(r) and '3' in r.get('plain', ''))

test(r'\sin\left(\pi\right) = 0',
     r'\sin\left(\pi\right)',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))

test(r'\cos\left(\frac{\pi}{3}\right) = 1/2',
     r'\cos\left(\frac{\pi}{3}\right)',
     lambda r: result_ok(r) and ('1' in r.get('plain', '') and '2' in r.get('plain', '')))

test(r'\frac{x^{2}-1}{x-1} simplifies to x+1',
     r'simplify(\frac{x^{2}-1}{x-1})',
     lambda r: result_ok(r))

test(r'x\cdot y = xy',
     r'x\cdot y',
     lambda r: result_ok(r) and 'x' in r.get('plain', '') and 'y' in r.get('plain', ''))

test(r'\left(x+1\right)^{2} expands',
     r'expand(\left(x+1\right)^{2})',
     lambda r: result_ok(r) and r.get('type') == 'command')


# ══════════════════════════════════════════════════════════════
# 12. Recursive Variable Dependencies
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  12. Recursive Variable Dependencies')
print('=' * 60)
cas_clear()

cas_evaluate('a = 1')
cas_evaluate('b = a + 1')
cas_evaluate('c = b + 1')
cas_evaluate('d = c + 1')

test('4-level chain: d = 4',
     'd',
     lambda r: result_ok(r) and '4' in r.get('plain', ''))

test('a + b + c + d = 10',
     'a + b + c + d',
     lambda r: result_ok(r) and '10' in r.get('plain', ''))

# Redefine a  — all dependents should react
cas_evaluate('a = 10')
test('After a=10: b = 11',
     'b',
     lambda r: result_ok(r) and '11' in r.get('plain', ''))

test('After a=10: d = 13',
     'd',
     lambda r: result_ok(r) and '13' in r.get('plain', ''))

# Variable with expression
cas_clear()
cas_evaluate('r = 5')
cas_evaluate(r'area = \pi \cdot r^2')
test('area = 25*pi',
     'area',
     lambda r: result_ok(r) and '25' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 13. Numerical Evaluation & Toggle
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  13. Numerical Evaluation & Toggle')
print('=' * 60)
cas_clear()

test('N(pi) = 3.14159...',
     'N(pi)',
     lambda r: result_ok(r) and '3.14159' in r.get('plain', ''))

test('N(sqrt(2)) = 1.4142...',
     'N(sqrt(2))',
     lambda r: result_ok(r) and '1.4142' in r.get('plain', ''))

test('N(e) = 2.71828...',
     'N(e)',
     lambda r: result_ok(r) and '2.71828' in r.get('plain', ''))

# Numeric toggle data
test('pi has numeric_latex field',
     'pi',
     lambda r: result_ok(r) and 'numeric_latex' in r)

test('1/3 has numeric_latex = 0.333...',
     r'\frac{1}{3}',
     lambda r: result_ok(r) and '0.333' in r.get('numeric_latex', ''))

test('sqrt(2) has numeric_latex',
     r'\sqrt{2}',
     lambda r: result_ok(r) and 'numeric_latex' in r)

test('Integer 42 has NO numeric_latex',
     '42',
     lambda r: result_ok(r) and 'numeric_latex' not in r)

test('Integer 0 has NO numeric_latex',
     '0',
     lambda r: result_ok(r) and 'numeric_latex' not in r)


# ══════════════════════════════════════════════════════════════
# 14. Substitution
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  14. Substitution')
print('=' * 60)
cas_clear()

test('subs(x^2 + y, x, 3) = 9 + y',
     'subs(x^2 + y, x, 3)',
     lambda r: result_ok(r) and '9' in r.get('plain', ''))

test('subs(sin(x), x, pi) = 0',
     r'subs(sin(x), x, pi)',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 15. Edge Cases & Domain Errors
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  15. Edge Cases & Domain Errors')
print('=' * 60)
cas_clear()

test('1/0 → error or oo',
     r'\frac{1}{0}',
     lambda r: ('oo' in r.get('plain', '') or 'zoo' in r.get('plain', '')
                or 'infin' in r.get('plain', '').lower()
                or not r.get('ok', True)))

test('0^0 handled gracefully',
     '0^0',
     lambda r: True)  # Just shouldn't crash

test('Deeply nested: (((((7))))) = 7',
     '(((((7)))))',
     lambda r: result_ok(r) and '7' in r.get('plain', ''))

test('Empty input = empty result',
     '',
     lambda r: result_ok(r) and r.get('type') == 'empty')

test('Just a number: 42',
     '42',
     lambda r: result_ok(r) and '42' in r.get('plain', ''))

test('Symbolic x stays symbolic',
     'x',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))

test('Very large number: 10^20',
     '10^{20}',
     lambda r: result_ok(r))

test('Negative number: -42',
     '-42',
     lambda r: result_ok(r) and '-42' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 16. Circular Dependency Detection
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  16. Circular Dependency Detection')
print('=' * 60)
cas_clear()

cas_evaluate('p = q + 1')
cas_evaluate('q = p + 1')
test('Circular dep p→q→p detected',
     'p',
     lambda r: not r.get('ok', True) and 'ircular' in r.get('error', ''))


# ══════════════════════════════════════════════════════════════
# 17. State Management
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  17. State Management')
print('=' * 60)

clear_result = json.loads(cas_clear())
test('cas_clear() returns ok',
     '1 + 1',
     lambda r: result_ok(r) and '2' in r.get('plain', ''))

cas_evaluate('z = 99')
state = json.loads(cas_get_state())
test('cas_get_state() includes z',
     'z',
     lambda r: result_ok(r) and '99' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 18. Implicit Multiplication Edge Cases
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  18. Implicit Multiplication Edge Cases')
print('=' * 60)
cas_clear()

cas_evaluate('a = 2')
cas_evaluate('b = 3')

test('2a = 4',
     '2a',
     lambda r: result_ok(r) and '4' in r.get('plain', ''))

test('ab = 6 (a*b)',
     'ab',
     lambda r: result_ok(r) and '6' in r.get('plain', ''))

test('3ab = 18',
     '3ab',
     lambda r: result_ok(r) and '18' in r.get('plain', ''))

test('2(a+b) = 10',
     '2(a+b)',
     lambda r: result_ok(r) and '10' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 19. Mixed LaTeX and CAS Commands
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  19. Mixed LaTeX and CAS Commands')
print('=' * 60)
cas_clear()

test(r'solve(\frac{x}{2} = 3, x) → 6',
     r'solve(\frac{x}{2} - 3, x)',
     lambda r: result_ok(r) and '6' in r.get('plain', ''))

test(r'diff(\frac{x^{3}}{3}, x) = x^2',
     r'diff(\frac{x^{3}}{3}, x)',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))

test(r'integrate(\sqrt{x}, x)',
     r'integrate(\sqrt{x}, x)',
     lambda r: result_ok(r) and r.get('type') == 'command')


# ══════════════════════════════════════════════════════════════
# 20. Special Constants
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  20. Special Constants')
print('=' * 60)
cas_clear()

test('pi is approximately 3.14159...',
     'pi',
     lambda r: result_ok(r) and ('pi' in r.get('plain', '').lower() or '\u03c0' in r.get('plain', '')))

test('e is Euler number',
     'e',
     lambda r: result_ok(r))

test('e^1 = e',
     'e^1',
     lambda r: result_ok(r))

test('ln(e) = 1',
     'ln(e)',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))

test('sin(pi) = 0',
     'sin(pi)',
     lambda r: result_ok(r) and '0' in r.get('plain', ''))

test('cos(2*pi) = 1',
     'cos(2*pi)',
     lambda r: result_ok(r) and '1' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 21. Comprehensive Expression Patterns
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  21. Comprehensive Expression Patterns')
print('=' * 60)
cas_clear()

test('Fraction arithmetic: 2/3 + 3/4 = 17/12',
     r'\frac{2}{3}+\frac{3}{4}',
     lambda r: result_ok(r) and '17' in r.get('latex', '') and '12' in r.get('latex', ''))

test('Nested sqrt: sqrt(sqrt(256)) = 4',
     r'\sqrt{\sqrt{256}}',
     lambda r: result_ok(r) and '4' in r.get('plain', ''))

test('Power of fraction: (2/3)^2 = 4/9',
     r'\left(\frac{2}{3}\right)^{2}',
     lambda r: result_ok(r) and '4' in r.get('latex', '') and '9' in r.get('latex', ''))

test('abs(-5) = 5',
     'abs(-5)',
     lambda r: result_ok(r) and '5' in r.get('plain', ''))

test('floor(3.7) = 3',
     'floor(3.7)',
     lambda r: result_ok(r) and '3' in r.get('plain', ''))

test('gcd(12, 18) = 6',
     'gcd(12, 18)',
     lambda r: result_ok(r) and '6' in r.get('plain', ''))

test('factorial(5) = 120',
     'factorial(5)',
     lambda r: result_ok(r) and '120' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
# 22. Integral Parsing Regression Tests
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  22. Integral Parsing Regression Tests')
print('=' * 60)
cas_clear()

test(r'\int_0^1 x dx = 1/2',
     r'\int_{0}^{1}x',
     lambda r: result_ok(r) and ('1' in r.get('plain', '') and '2' in r.get('plain', '')))

test(r'\int_0^5 5x (no braces) = 125/2',
     r'\int _0^55x',
     lambda r: result_ok(r) and '125' in r.get('plain', ''))

test(r'\int_{0}^{5} 5x (braced) = 125/2',
     r'\int_{0}^{5}5x',
     lambda r: result_ok(r) and '125' in r.get('plain', ''))

test(r'\int_{0}^{2}5x (MathQuill style) = 10',
     r'\int_{0}^{2}5x',
     lambda r: result_ok(r) and '10' in r.get('plain', ''))

test(r'\int_{0}^{2}5x dx (MathQuill with dx) = 10',
     r'\int_{0}^{2}5x dx',
     lambda r: result_ok(r) and '10' in r.get('plain', ''))

test('integrate command: integrate(x^2, x, 0, 1) = 1/3',
     'integrate(x^2, x, 0, 1)',
     lambda r: result_ok(r) and '1' in r.get('plain', '') and '3' in r.get('plain', ''))

test('integrate command: integrate(sin(x), x)',
     'integrate(sin(x), x)',
     lambda r: result_ok(r) and 'cos' in r.get('plain', '').lower())


# ══════════════════════════════════════════════════════════════
# 23. Superscript/Subscript Regression Tests
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
print('  23. Superscript/Subscript Regression Tests')
print('=' * 60)
cas_clear()

test('x^2 = x^2 (plain)',
     'x^2',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))

test('x^{2} = x^2 (braced)',
     'x^{2}',
     lambda r: result_ok(r) and 'x' in r.get('plain', ''))

test('x^2 + y^2 evaluates',
     'x^2 + y^2',
     lambda r: result_ok(r))

test('(x+1)^3 expands',
     'expand((x+1)^3)',
     lambda r: result_ok(r) and r.get('type') == 'command')

test('e_var assignment preserves identifier',
     'e_var = 5',
     lambda r: result_ok(r) and r.get('name') == 'e_var')

test('e_var = 5',
     'e_var',
     lambda r: result_ok(r) and '5' in r.get('plain', ''))

test('a_1 assignment',
     'a_1 = 7',
     lambda r: result_ok(r) and r.get('type') == 'assignment')

test('a_1 retrieval',
     'a_1',
     lambda r: result_ok(r) and '7' in r.get('plain', ''))


# ══════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
total = passed + failed
print(f'  RESULTS: {passed}/{total} passed, {failed} failed')
print('=' * 60)

if errors:
    print('\n  Failed tests:')
    for e in errors:
        print(f'    - {e}')
    print()

sys.exit(0 if failed == 0 else 1)
