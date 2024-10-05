import json
import os
from flask import Flask, request, jsonify, render_template_string
from latex2sympy2 import latex2sympy
import sympy as sp

app = Flask(__name__)

DATA_FILE = 'data.json'

# Load existing data or initialize
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    # Ensure 'variables' and 'equations' keys exist
    data.setdefault('variables', {})
    data.setdefault('equations', [])
else:
    data = {'variables': {}, 'equations': []}

# HTML Template with embedded JavaScript and CSS
with open('htmla.html', 'r') as file:
    HTML_TEMPLATE = file.read()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/compute', methods=['POST'])
def compute():
    global data
    content = request.json
    equation = content.get('equation', '').strip()

    try:
        # Detect assignment operators ':=' or '='
        if ':=' in equation:
            lhs, rhs = equation.split(':=', 1)
        elif '=' in equation:
            lhs, rhs = equation.split('=', 1)
        else:
            lhs, rhs = None, equation

        # Prepare the current variables for evaluation
        # Convert stored variable strings to sympy expressions
        sympy_vars = {k: sp.sympify(v) for k, v in data.get('variables', {}).items()}

        if lhs:
            # It's an assignment
            var_name = lhs.strip()
            rhs_latex = rhs.strip()
            # Convert LaTeX to sympy expression
            rhs_expr = latex2sympy(rhs_latex)
            # Evaluate the expression with current variables
            sympy_expr = sp.sympify(str(rhs_expr), locals=sympy_vars)
            # Store the variable as a string representation
            data['variables'][var_name] = str(sympy_expr)
            # Optionally, store the equation
            data['equations'].append({'equation': equation, 'result': str(sympy_expr)})
            result = str(sympy_expr)
        else:
            # It's a regular expression
            expr_latex = rhs.strip()
            expr = latex2sympy(expr_latex)
            sympy_expr = sp.sympify(str(expr), locals=sympy_vars)
            # Store the equation
            data['equations'].append({'equation': equation, 'result': str(sympy_expr)})
            result = str(sympy_expr)

        # Save the updated data to the JSON file
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)

    except Exception as e:
        result = f'Error: {e}'

    return jsonify({'result': result})

@app.route('/save', methods=['POST'])
def save():
    global data
    content = request.json
    # Update equations from frontend
    equations = content.get('equations', [])
    data['equations'] = equations
    # Note: Variables are handled in the /compute route
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)
    return jsonify({'status': 'success'})

@app.route('/data')
def get_data():
    return jsonify({'equations': data.get('equations', []), 'variables': data.get('variables', {})})

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)
