#!/usr/bin/env bash
# Step 7b: Build symengine.py Pyodide wheel (fixed CMake path)
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

# The key: CMAKE_PREFIX_PATH tells CMake where to find SymEngineConfig.cmake
export CMAKE_PREFIX_PATH="$PREFIX"
# Also set as CMAKE_ARGS for scikit-build-core
export CMAKE_ARGS="-DSymEngine_DIR=$PREFIX/lib/cmake/symengine -DBoost_INCLUDE_DIR=$BOOST_DIR -DCMAKE_PREFIX_PATH=$PREFIX"
# And set SymEngine_DIR directly as env var (CMake reads this)
export SymEngine_DIR="$PREFIX/lib/cmake/symengine"

echo "CMAKE_PREFIX_PATH: $CMAKE_PREFIX_PATH"
echo "SymEngine_DIR: $SymEngine_DIR"
echo "CMAKE_ARGS: $CMAKE_ARGS"

# Clean previous build attempt
rm -rf build/ dist/ *.egg-info .pyodide_build/

echo ""
echo "=== Running pyodide build ==="
pyodide build 2>&1

echo ""
echo "=== Collecting wheel ==="
find . -name "*.whl" | head -5
ls -la dist/*.whl 2>/dev/null || true
cp dist/*.whl "$WHEEL_DIR/" 2>/dev/null || {
    find . -name "*.whl" -exec cp {} "$WHEEL_DIR/" \;
}

echo ""
echo "=== Done ==="
ls -la "$WHEEL_DIR"/*.whl 2>/dev/null || echo "No wheel found!"
