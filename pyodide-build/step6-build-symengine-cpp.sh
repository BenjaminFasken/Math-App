#!/usr/bin/env bash
# Step 6: Cross-compile SymEngine C++ with emcmake
set -euo pipefail

BUILD_DIR="/mnt/e/Projects/Visual-Studio/Math-App/pyodide-build/_build"
cd "$BUILD_DIR"

source "$BUILD_DIR/venv/bin/activate"
source "$BUILD_DIR/emsdk/emsdk_env.sh" 2>/dev/null

PREFIX="$BUILD_DIR/install"
BOOST_DIR="$BUILD_DIR/boost_1_84_0"
SE_SRC="$BUILD_DIR/symengine-0.14.0"
SE_BUILD="$BUILD_DIR/symengine-build"

rm -rf "$SE_BUILD"
mkdir -p "$SE_BUILD" "$PREFIX"
cd "$SE_BUILD"

echo "=== Running emcmake cmake ==="
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
    2>&1

echo ""
echo "=== Building ($(nproc) jobs) ==="
emmake make -j"$(nproc)" 2>&1

echo ""
echo "=== Installing ==="
emmake make install 2>&1

echo ""
echo "=== Done ==="
ls -la "$PREFIX/lib/"*.a 2>/dev/null || ls -la "$PREFIX/lib64/"*.a 2>/dev/null || echo "Checking install..."
find "$PREFIX" -name "*.a" -o -name "SymEngineConfig.cmake" | head -10
