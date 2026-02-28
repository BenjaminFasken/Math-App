#!/usr/bin/env bash
# ============================================================
# build-symengine.sh — Cross-compile SymEngine for Pyodide/wasm32
# ============================================================
#
# This script builds symengine.py as a Pyodide-compatible wheel
# (.whl) that can be loaded in the browser via micropip.
#
# Requirements:
#   - Linux (or WSL2 on Windows)
#   - Python 3.12  (must match target Pyodide's Python)
#   - ~4 GB disk space for emsdk + build artefacts
#   - Internet access for downloads
#
# Usage:
#   chmod +x build-symengine.sh
#   ./build-symengine.sh
#
# The final wheel lands in ./dist/
# ============================================================

set -euo pipefail

# ── Configuration ───────────────────────────────────────────
PYODIDE_VERSION="${PYODIDE_VERSION:-0.27.4}"
SYMENGINE_VERSION="${SYMENGINE_VERSION:-0.14.0}"
SYMENGINE_PY_VERSION="${SYMENGINE_PY_VERSION:-0.14.1}"
BOOST_VERSION="${BOOST_VERSION:-1.84.0}"
BOOST_VERSION_UNDER="${BOOST_VERSION//./_}"    # 1_84_0
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/_build"
PREFIX="${BUILD_DIR}/install"
WHEEL_DIR="${SCRIPT_DIR}/dist"

echo "══════════════════════════════════════════════════════"
echo "  SymEngine for Pyodide — Cross-compilation"
echo "══════════════════════════════════════════════════════"
echo "  Pyodide version : ${PYODIDE_VERSION}"
echo "  SymEngine       : ${SYMENGINE_VERSION}"
echo "  symengine.py    : ${SYMENGINE_PY_VERSION}"
echo "  Boost           : ${BOOST_VERSION}"
echo "  Build jobs      : ${JOBS}"
echo "  Build dir       : ${BUILD_DIR}"
echo "  Install prefix  : ${PREFIX}"
echo "  Wheel output    : ${WHEEL_DIR}"
echo "══════════════════════════════════════════════════════"

mkdir -p "${BUILD_DIR}" "${WHEEL_DIR}"

# ── Step 1: Verify Python 3.12 ─────────────────────────────
echo ""
echo "▶ Step 1/8: Checking Python 3.12..."

PYTHON312=""
for candidate in python3.12 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oP '3\.12\.\d+' || true)
        if [ -n "$ver" ]; then
            PYTHON312="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON312" ]; then
    echo "  Python 3.12 not found. Installing via deadsnakes PPA..."
    sudo apt-get update -qq
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update -qq
    sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
    PYTHON312="python3.12"
fi

echo "  Using: $PYTHON312 ($($PYTHON312 --version 2>&1))"

# ── Step 2: Create venv + install pyodide-build ─────────────
echo ""
echo "▶ Step 2/8: Setting up virtual environment..."

VENV_DIR="${BUILD_DIR}/venv"
if [ ! -d "${VENV_DIR}" ]; then
    $PYTHON312 -m venv "${VENV_DIR}"
fi
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip setuptools wheel -q
pip install pyodide-build -q

echo "  pyodide-build $(pip show pyodide-build 2>/dev/null | grep Version | awk '{print $2}')"

# ── Step 3: Install Emscripten SDK ──────────────────────────
echo ""
echo "▶ Step 3/8: Setting up Emscripten SDK..."

EMSDK_VERSION=$(pyodide config get emscripten_version)
echo "  Required emsdk: ${EMSDK_VERSION}"

EMSDK_DIR="${BUILD_DIR}/emsdk"
if [ ! -d "${EMSDK_DIR}" ]; then
    git clone --depth 1 https://github.com/emscripten-core/emsdk.git "${EMSDK_DIR}"
fi

cd "${EMSDK_DIR}"
./emsdk install "${EMSDK_VERSION}" 2>&1 | tail -3
./emsdk activate "${EMSDK_VERSION}" 2>&1 | tail -3
source emsdk_env.sh 2>/dev/null

echo "  emcc: $(emcc --version 2>&1 | head -1)"

# ── Step 4: Install Pyodide cross-build environment ─────────
echo ""
echo "▶ Step 4/8: Installing Pyodide xbuildenv..."

pyodide xbuildenv install "${PYODIDE_VERSION}" 2>&1 | tail -3
echo "  xbuildenv ready"

# ── Step 5: Download Boost headers (header-only, for boostmp)
echo ""
echo "▶ Step 5/8: Downloading Boost headers..."

cd "${BUILD_DIR}"
BOOST_DIR="${BUILD_DIR}/boost_${BOOST_VERSION_UNDER}"
if [ ! -d "${BOOST_DIR}" ]; then
    BOOST_URL="https://boostorg.jfrog.io/artifactory/main/release/${BOOST_VERSION}/source/boost_${BOOST_VERSION_UNDER}.tar.gz"
    echo "  Downloading from ${BOOST_URL}..."
    wget -q "${BOOST_URL}" -O "boost_${BOOST_VERSION_UNDER}.tar.gz"
    tar xf "boost_${BOOST_VERSION_UNDER}.tar.gz"
fi
echo "  Boost headers at: ${BOOST_DIR}"

# ── Step 6: Download & cross-compile SymEngine C++ ──────────
echo ""
echo "▶ Step 6/8: Cross-compiling SymEngine C++ library..."

cd "${BUILD_DIR}"
SE_SRC="${BUILD_DIR}/symengine-${SYMENGINE_VERSION}"
if [ ! -d "${SE_SRC}" ]; then
    SE_URL="https://github.com/symengine/symengine/releases/download/v${SYMENGINE_VERSION}/symengine-${SYMENGINE_VERSION}.tar.gz"
    echo "  Downloading SymEngine ${SYMENGINE_VERSION}..."
    wget -q "${SE_URL}" -O "symengine-${SYMENGINE_VERSION}.tar.gz"
    tar xf "symengine-${SYMENGINE_VERSION}.tar.gz"
fi

SE_BUILD="${BUILD_DIR}/symengine-build"
rm -rf "${SE_BUILD}"
mkdir -p "${SE_BUILD}"
cd "${SE_BUILD}"

echo "  Running emcmake cmake..."
emcmake cmake "${SE_SRC}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
    -DINTEGER_CLASS=boostmp \
    -DBoost_INCLUDE_DIR="${BOOST_DIR}" \
    -DBUILD_TESTS=OFF \
    -DBUILD_BENCHMARKS=OFF \
    -DWITH_SYMENGINE_THREAD_SAFE=OFF \
    -DWITH_SYMENGINE_RCP=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DWITH_FLINT=OFF \
    -DWITH_MPFR=OFF \
    -DWITH_MPC=OFF \
    -DWITH_LLVM=OFF \
    2>&1 | tail -20

echo "  Building (${JOBS} jobs)..."
emmake make -j"${JOBS}" 2>&1 | tail -5

echo "  Installing..."
emmake make install 2>&1 | tail -3

echo "  SymEngine installed to ${PREFIX}"
ls -la "${PREFIX}/lib/"*.a 2>/dev/null || echo "  (checking lib64...)"
ls -la "${PREFIX}/lib64/"*.a 2>/dev/null || true

# ── Step 7: Download & build symengine.py wheel ─────────────
echo ""
echo "▶ Step 7/8: Building symengine.py Pyodide wheel..."

cd "${BUILD_DIR}"
SE_PY_SRC="${BUILD_DIR}/symengine.py-${SYMENGINE_PY_VERSION}"
if [ ! -d "${SE_PY_SRC}" ]; then
    SE_PY_URL="https://github.com/symengine/symengine.py/archive/refs/tags/v${SYMENGINE_PY_VERSION}.tar.gz"
    echo "  Downloading symengine.py ${SYMENGINE_PY_VERSION}..."
    wget -q "${SE_PY_URL}" -O "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz"
    tar xf "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz"
fi

cd "${SE_PY_SRC}"

# Point CMake to our wasm SymEngine installation
export SymEngine_DIR="${PREFIX}"
# Also try the cmake subdirectory where SymEngineConfig.cmake lives
for d in "${PREFIX}/lib/cmake/symengine" "${PREFIX}/lib64/cmake/symengine" "${PREFIX}/share/cmake/symengine"; do
    if [ -d "$d" ]; then
        export SymEngine_DIR="$d"
        break
    fi
done
echo "  SymEngine_DIR=${SymEngine_DIR}"

# Extra CMake flags for the cross-compilation
export CMAKE_ARGS="-DSymEngine_DIR=${SymEngine_DIR} -DBoost_INCLUDE_DIR=${BOOST_DIR}"

echo "  Running pyodide build..."
pyodide build 2>&1 | tail -20

# ── Step 8: Collect wheel ───────────────────────────────────
echo ""
echo "▶ Step 8/8: Collecting wheel..."

cp "${SE_PY_SRC}"/dist/*.whl "${WHEEL_DIR}/" 2>/dev/null || {
    echo "  Checking for wheel in other locations..."
    find "${SE_PY_SRC}" -name "*.whl" -exec cp {} "${WHEEL_DIR}/" \;
}

echo ""
echo "══════════════════════════════════════════════════════"
echo "  BUILD COMPLETE"
echo "══════════════════════════════════════════════════════"
ls -la "${WHEEL_DIR}"/*.whl 2>/dev/null || echo "  WARNING: No wheel found!"
echo ""
echo "To use in your app, copy the .whl to your web server"
echo "and load it via micropip.install('URL_TO_WHEEL')"
echo "══════════════════════════════════════════════════════"
