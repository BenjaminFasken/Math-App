#!/usr/bin/env bash
# Step 7d: Build symengine.py Pyodide wheel — fix Python include path too
set -euo pipefail

BUILD_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/_build"
cd "$BUILD_DIR"

source "$BUILD_DIR/venv/bin/activate"
source "$BUILD_DIR/emsdk/emsdk_env.sh" 2>/dev/null

PREFIX="$BUILD_DIR/install"
BOOST_DIR="$BUILD_DIR/boost_1_84_0"
WHEEL_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/dist"
PYTHON_INCLUDE="/home/benjamin/.cache/.pyodide-xbuildenv-0.33.0/0.27.4/xbuildenv/pyodide-root/cpython/installs/python-3.12.7/include/python3.12"
mkdir -p "$WHEEL_DIR"

SYMENGINE_PY_VERSION="0.14.1"
SE_PY_SRC="$BUILD_DIR/symengine.py-${SYMENGINE_PY_VERSION}"
cd "$SE_PY_SRC"

# Clean previous build attempt
rm -rf build/ dist/ *.egg-info .pyodide_build/

# Re-download fresh setup.py if it was already patched
SYMENGINE_CMAKE_DIR="$PREFIX/lib/cmake/symengine"

# Replace the entire cmake_opts block with our patched version
cat > /tmp/patch_setup.py << 'PATCHEOF'
import sys

with open('setup.py', 'r') as f:
    content = f.read()

# Remove old patch if present
if 'PATCHED_FOR_PYODIDE' in content:
    lines = content.split('\n')
    new_lines = []
    skip = False
    for line in lines:
        if 'PATCHED_FOR_PYODIDE' in line:
            skip = True
            continue
        if skip and line.strip() == '])':
            skip = False
            continue
        if skip:
            continue
        new_lines.append(line)
    content = '\n'.join(new_lines)

# Insert after cmake_opts closing bracket
target = 'cmake_generator = [None]'
patch = f"""# PATCHED_FOR_PYODIDE
cmake_opts.extend([
    ("SymEngine_DIR", "{symengine_cmake_dir}"),
    ("Boost_INCLUDE_DIR", "{boost_dir}"),
    ("CMAKE_PREFIX_PATH", "{prefix}"),
    ("PYTHON_INCLUDE_PATH", "{python_include}"),
])
"""
content = content.replace(target, patch + target)

with open('setup.py', 'w') as f:
    f.write(content)
PATCHEOF

# Run the patcher with the right variables
python3 -c "
symengine_cmake_dir = '$SYMENGINE_CMAKE_DIR'
boost_dir = '$BOOST_DIR'
prefix = '$PREFIX'
python_include = '$PYTHON_INCLUDE'

with open('setup.py', 'r') as f:
    content = f.read()

# Remove old patch if present
import re
content = re.sub(r'# PATCHED_FOR_PYODIDE\ncmake_opts\.extend\(\[.*?\]\)\n', '', content, flags=re.DOTALL)

target = 'cmake_generator = [None]'
patch = f'''# PATCHED_FOR_PYODIDE
cmake_opts.extend([
    (\"SymEngine_DIR\", \"{symengine_cmake_dir}\"),
    (\"Boost_INCLUDE_DIR\", \"{boost_dir}\"),
    (\"CMAKE_PREFIX_PATH\", \"{prefix}\"),
    (\"PYTHON_INCLUDE_PATH\", \"{python_include}\"),
])
'''
content = content.replace(target, patch + target)

with open('setup.py', 'w') as f:
    f.write(content)
print('Patched successfully')
"

echo "Verify patch:"
grep -A8 "PATCHED_FOR_PYODIDE" setup.py

echo ""
echo "=== Running pyodide build ==="
pyodide build 2>&1

echo ""
echo "=== Collecting wheel ==="
ls -la dist/*.whl 2>/dev/null || true
cp dist/*.whl "$WHEEL_DIR/" 2>/dev/null || {
    find . -name "*.whl" -exec cp {} "$WHEEL_DIR/" \;
}

echo ""
echo "=== Done ==="
ls -la "$WHEEL_DIR"/*.whl 2>/dev/null || echo "No wheel found!"
