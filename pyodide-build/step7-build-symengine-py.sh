#!/usr/bin/env bash
# Step 7: Build symengine.py Pyodide wheel
set -euo pipefail

BUILD_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/_build"
cd "$BUILD_DIR"

source "$BUILD_DIR/venv/bin/activate"
source "$BUILD_DIR/emsdk/emsdk_env.sh" 2>/dev/null

PREFIX="$BUILD_DIR/install"
BOOST_DIR="$BUILD_DIR/boost_1_84_0"
WHEEL_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/dist"
mkdir -p "$WHEEL_DIR"

# Download symengine.py
SYMENGINE_PY_VERSION="0.14.1"
SE_PY_SRC="$BUILD_DIR/symengine.py-${SYMENGINE_PY_VERSION}"
if [ ! -d "$SE_PY_SRC" ]; then
    echo "Downloading symengine.py ${SYMENGINE_PY_VERSION}..."
    curl -sL "https://github.com/symengine/symengine.py/archive/refs/tags/v${SYMENGINE_PY_VERSION}.tar.gz" \
        -o "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz"
    tar xzf "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz"
fi

cd "$SE_PY_SRC"
echo "symengine.py source: $(pwd)"

# Find SymEngine CMake config
SE_CMAKE_DIR="$PREFIX/lib/cmake/symengine"
echo "SymEngine_DIR: $SE_CMAKE_DIR"

# Set CMake args for the cross-compilation
export CMAKE_ARGS="-DSymEngine_DIR=$SE_CMAKE_DIR -DBoost_INCLUDE_DIR=$BOOST_DIR"
echo "CMAKE_ARGS: $CMAKE_ARGS"

echo ""
echo "=== Running pyodide build ==="
pyodide build 2>&1

echo ""
echo "=== Collecting wheel ==="
find "$SE_PY_SRC" -name "*.whl" | head -5
cp "$SE_PY_SRC"/dist/*.whl "$WHEEL_DIR/" 2>/dev/null || {
    echo "Checking for wheel in other locations..."
    find "$SE_PY_SRC" -name "*.whl" -exec cp {} "$WHEEL_DIR/" \;
}

echo ""
echo "=== Done ==="
ls -la "$WHEEL_DIR"/*.whl 2>/dev/null || echo "No wheel found!"
