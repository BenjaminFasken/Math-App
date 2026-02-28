# ============================================================
# Dockerfile — Build SymEngine for Pyodide in a container
# ============================================================
#
# Usage:
#   docker build -t symengine-pyodide-builder .
#   docker run --rm -v $(pwd)/dist:/output symengine-pyodide-builder
#
# The wheel will be copied to ./dist/ on your host.
# ============================================================

FROM python:3.12-bookworm

ARG PYODIDE_VERSION=0.27.4
ARG SYMENGINE_VERSION=0.14.0
ARG SYMENGINE_PY_VERSION=0.14.1
ARG BOOST_VERSION=1.84.0

ENV DEBIAN_FRONTEND=noninteractive
ENV PYODIDE_VERSION=${PYODIDE_VERSION}
ENV SYMENGINE_VERSION=${SYMENGINE_VERSION}
ENV SYMENGINE_PY_VERSION=${SYMENGINE_PY_VERSION}
ENV BOOST_VERSION=${BOOST_VERSION}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git wget ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install pyodide-build
RUN pip install --no-cache-dir pyodide-build

# Install Emscripten SDK
RUN EMSDK_VERSION=$(pyodide config get emscripten_version) && \
    git clone --depth 1 https://github.com/emscripten-core/emsdk.git /build/emsdk && \
    cd /build/emsdk && \
    ./emsdk install ${EMSDK_VERSION} && \
    ./emsdk activate ${EMSDK_VERSION}

# Install Pyodide xbuildenv
RUN . /build/emsdk/emsdk_env.sh && \
    pyodide xbuildenv install ${PYODIDE_VERSION}

# Download Boost headers
RUN BOOST_UNDER=$(echo ${BOOST_VERSION} | tr '.' '_') && \
    wget -q "https://boostorg.jfrog.io/artifactory/main/release/${BOOST_VERSION}/source/boost_${BOOST_UNDER}.tar.gz" && \
    tar xf "boost_${BOOST_UNDER}.tar.gz" && \
    rm "boost_${BOOST_UNDER}.tar.gz"

# Download & cross-compile SymEngine C++
RUN wget -q "https://github.com/symengine/symengine/releases/download/v${SYMENGINE_VERSION}/symengine-${SYMENGINE_VERSION}.tar.gz" && \
    tar xf "symengine-${SYMENGINE_VERSION}.tar.gz" && \
    rm "symengine-${SYMENGINE_VERSION}.tar.gz"

RUN BOOST_UNDER=$(echo ${BOOST_VERSION} | tr '.' '_') && \
    . /build/emsdk/emsdk_env.sh && \
    mkdir -p /build/symengine-build && cd /build/symengine-build && \
    emcmake cmake "/build/symengine-${SYMENGINE_VERSION}" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/build/install \
        -DINTEGER_CLASS=boostmp \
        -DBoost_INCLUDE_DIR="/build/boost_${BOOST_UNDER}" \
        -DBUILD_TESTS=OFF \
        -DBUILD_BENCHMARKS=OFF \
        -DWITH_SYMENGINE_THREAD_SAFE=OFF \
        -DWITH_SYMENGINE_RCP=ON \
        -DBUILD_SHARED_LIBS=OFF \
        -DWITH_FLINT=OFF \
        -DWITH_MPFR=OFF \
        -DWITH_MPC=OFF \
        -DWITH_LLVM=OFF && \
    emmake make -j$(nproc) && \
    emmake make install

# Download symengine.py
RUN wget -q "https://github.com/symengine/symengine.py/archive/refs/tags/v${SYMENGINE_PY_VERSION}.tar.gz" \
        -O "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz" && \
    tar xf "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz" && \
    rm "symengine.py-${SYMENGINE_PY_VERSION}.tar.gz"

# Build the Pyodide wheel
RUN . /build/emsdk/emsdk_env.sh && \
    SE_DIR=$(find /build/install -name "SymEngineConfig.cmake" -exec dirname {} \; | head -1) && \
    BOOST_UNDER=$(echo ${BOOST_VERSION} | tr '.' '_') && \
    export SymEngine_DIR="${SE_DIR}" && \
    export CMAKE_ARGS="-DSymEngine_DIR=${SE_DIR} -DBoost_INCLUDE_DIR=/build/boost_${BOOST_UNDER}" && \
    cd "/build/symengine.py-${SYMENGINE_PY_VERSION}" && \
    pyodide build

# Copy wheel to /dist (mount point)
RUN mkdir -p /dist && \
    cp /build/symengine.py-${SYMENGINE_PY_VERSION}/dist/*.whl /dist/ 2>/dev/null || \
    find /build -name "symengine*.whl" -exec cp {} /dist/ \;

# Default command: copy wheel to mounted /output
CMD cp /dist/*.whl /output/ 2>/dev/null && \
    echo "Wheel copied to /output:" && ls -la /output/*.whl || \
    echo "ERROR: No wheel found"
