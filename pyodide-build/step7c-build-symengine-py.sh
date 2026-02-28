#!/usr/bin/env bash
# Step 7c: Build symengine.py Pyodide wheel — patch setup.py to hardcode paths
set -euo pipefail

BUILD_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/_build"
cd "$BUILD_DIR"

source "$BUILD_DIR/venv/bin/activate"
source "$BUILD_DIR/emsdk/emsdk_env.sh" 2>/dev/null

PREFIX="$BUILD_DIR/install"
BOOST_DIR="$BUILD_DIR/boost_1_84_0"
WHEEL_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/dist"
mkdir -p "$WHEEL_DIR"

SYMENGINE_PY_VERSION="0.14.1"
SE_PY_SRC="$BUILD_DIR/symengine.py-${SYMENGINE_PY_VERSION}"
cd "$SE_PY_SRC"

# Clean previous build attempt
rm -rf build/ dist/ *.egg-info .pyodide_build/

# Patch setup.py: inject SymEngine_DIR and Boost path into cmake_opts
# Add right after the existing cmake_opts definition (line 44-45)
SYMENGINE_CMAKE_DIR="$PREFIX/lib/cmake/symengine"

if ! grep -q "PATCHED_FOR_PYODIDE" setup.py; then
    echo "Patching setup.py..."
    sed -i '/^cmake_opts = \[/,/\]/ {
        /\]/ a\
# PATCHED_FOR_PYODIDE\
cmake_opts.extend([\
    ("SymEngine_DIR", "'"$SYMENGINE_CMAKE_DIR"'"),\
    ("Boost_INCLUDE_DIR", "'"$BOOST_DIR"'"),\
    ("CMAKE_PREFIX_PATH", "'"$PREFIX"'"),\
])
    }' setup.py

    echo "Patched. Verify:"
    grep -A5 "PATCHED_FOR_PYODIDE" setup.py
else
    echo "setup.py already patched"
fi

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
