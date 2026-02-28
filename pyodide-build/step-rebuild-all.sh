#!/usr/bin/env bash
# Rebuild SymEngine C++ with cereal disabled, then rebuild symengine.py
set -euo pipefail

BUILD_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/_build"
cd "$BUILD_DIR"

source "$BUILD_DIR/venv/bin/activate"
source "$BUILD_DIR/emsdk/emsdk_env.sh" 2>/dev/null

PREFIX="$BUILD_DIR/install"
BOOST_DIR="$BUILD_DIR/boost_1_84_0"
SE_SRC="$BUILD_DIR/symengine-0.14.0"
SE_BUILD="$BUILD_DIR/symengine-build"
WHEEL_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/dist"
PYTHON_INCLUDE="/home/benjamin/.cache/.pyodide-xbuildenv-0.33.0/0.27.4/xbuildenv/pyodide-root/cpython/installs/python-3.12.7/include/python3.12"
mkdir -p "$WHEEL_DIR"

# ── Part 1: Rebuild SymEngine C++ without cereal ───────────
echo "=== Part 1: Rebuild SymEngine C++ (no cereal) ==="
rm -rf "$SE_BUILD" "$PREFIX"
mkdir -p "$SE_BUILD" "$PREFIX"
cd "$SE_BUILD"

emcmake cmake "$SE_SRC" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DINTEGER_CLASS=boostmp \
    -DBoost_INCLUDE_DIR="$BOOST_DIR" \
    -DBUILD_TESTS=OFF \
    -DBUILD_BENCHMARKS=OFF \
    -DWITH_SYMENGINE_THREAD_SAFE=OFF \
    -DWITH_SYMENGINE_RCP=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DWITH_FLINT=OFF \
    -DWITH_MPFR=OFF \
    -DWITH_MPC=OFF \
    -DWITH_LLVM=OFF \
    -DWITH_COTIRE=OFF \
    2>&1 | tail -20

echo "Building..."
emmake make -j"$(nproc)" 2>&1 | tail -5

echo "Installing..."
emmake make install 2>&1 | tail -5

# Check if cereal is still being installed
echo "Checking cereal in install headers..."
find "$PREFIX" -name "serialize-cereal.h" | head -2

# If serialize-cereal.h exists, create a symlink / fix the cereal path
CEREAL_INC="$PREFIX/include/symengine/utilities/cereal/include"
if [ -d "$CEREAL_INC/cereal" ]; then
    if [ ! -f "$CEREAL_INC/cereal/macros.hpp" ]; then
        echo "Creating cereal macros.hpp stub..."
        # The vendored cereal might not have macros.hpp - create an empty one
        touch "$CEREAL_INC/cereal/macros.hpp"
    fi
fi

# ── Part 2: Rebuild symengine.py ───────────────────────────
echo ""
echo "=== Part 2: Rebuild symengine.py wheel ==="

SYMENGINE_PY_VERSION="0.14.1"
SE_PY_SRC="$BUILD_DIR/symengine.py-${SYMENGINE_PY_VERSION}"
cd "$SE_PY_SRC"

# Clean previous build
rm -rf build/ dist/ *.egg-info .pyodide_build/

# Re-patch setup.py
SYMENGINE_CMAKE_DIR="$PREFIX/lib/cmake/symengine"
python3 -c "
symengine_cmake_dir = '$SYMENGINE_CMAKE_DIR'
boost_dir = '$BOOST_DIR'
prefix = '$PREFIX'
python_include = '$PYTHON_INCLUDE'
cereal_include = '$CEREAL_INC'

with open('setup.py', 'r') as f:
    content = f.read()

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
import os
os.environ['CXXFLAGS'] = os.environ.get('CXXFLAGS', '') + ' -I{cereal_include}'
'''
content = content.replace(target, patch + target)

with open('setup.py', 'w') as f:
    f.write(content)
print('setup.py patched')
"

echo "Running pyodide build..."
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
