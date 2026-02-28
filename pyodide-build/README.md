# Building SymEngine for Pyodide (WebAssembly)

SymEngine is a fast C++ symbolic manipulation library. This directory contains
the build infrastructure to cross-compile `symengine.py` (Python bindings) as
a Pyodide-compatible WebAssembly wheel that can be loaded in the browser.

## Why?

SymEngine is **10–1000× faster** than SymPy for operations like `expand()`,
`diff()`, polynomial arithmetic, and expression substitution. By loading it in
Pyodide alongside SymPy, we get the best of both worlds: SymEngine for speed
on supported operations, SymPy for the full feature set.

## Build Options

### Option 1: WSL / Linux (Direct)

```bash
cd pyodide-build
chmod +x build-symengine.sh
./build-symengine.sh
```

**Requirements:**
- Ubuntu 22.04+ (or WSL2 on Windows)
- Python 3.12 will be auto-installed if missing
- ~4 GB disk for emsdk + build artifacts
- Internet access

The script automatically:
1. Installs Python 3.12 (if needed)
2. Creates a venv with `pyodide-build`
3. Downloads & installs Emscripten SDK (matching Pyodide's version)
4. Downloads Boost headers (for `INTEGER_CLASS=boostmp`)
5. Cross-compiles SymEngine C++ with `emcc`
6. Builds `symengine.py` wheel with `pyodide build`

Output: `pyodide-build/dist/symengine-*.whl`

### Option 2: Docker

```bash
cd pyodide-build
docker build -t symengine-pyodide-builder .
docker run --rm -v $(pwd)/dist:/output symengine-pyodide-builder
```

This is fully self-contained and reproducible.

### Option 3: GitHub Actions CI

Push to a GitHub repository and manually trigger the
**"Build SymEngine for Pyodide"** workflow from the Actions tab.
The wheel will be available as a downloadable artifact.

See `.github/workflows/build-symengine-wasm.yml`.

## Using the Built Wheel

### Local Development

1. Copy the `.whl` file to your project's root (or a `wheels/` dir)
2. Serve via your local dev server (e.g. `python serve.py`)
3. The app's `loadPyodide.js` will auto-detect and load it

### Production

Host the `.whl` on a CDN or static file server. Update the wheel URL
in `loadPyodide.js`:

```javascript
const SYMENGINE_WHEEL_URL = 'https://your-cdn.com/symengine-0.14.1-cp312-cp312-pyodide_2024_0_wasm32.whl';
```

## Architecture

```
SymEngine C++ (wasm32)          ← cross-compiled with emcc
    ↓
symengine.py (Cython → wasm)   ← built with pyodide build
    ↓
.whl file                       ← loaded via micropip in browser
    ↓
casEngine.py                    ← uses symengine for fast operations,
                                   falls back to sympy when needed
```

## Build Configuration

The build uses these SymEngine CMake options:
- `INTEGER_CLASS=boostmp` — Uses Boost.Multiprecision (header-only, no GMP dependency)
- `BUILD_SHARED_LIBS=OFF` — Static library (required for wasm)
- No FLINT, MPFR, MPC, or LLVM — Minimal dependencies for wasm

This provides core symbolic operations. For maximum performance, a build
with GMP would be better, but GMP requires its own wasm cross-compilation.

## Customizing Versions

Set environment variables before running the build:

```bash
export PYODIDE_VERSION=0.27.4
export SYMENGINE_VERSION=0.14.0
export SYMENGINE_PY_VERSION=0.14.1
export BOOST_VERSION=1.84.0
./build-symengine.sh
```

## Troubleshooting

**"Python 3.12 not found"** — The script auto-installs it. If that fails,
install manually: `sudo apt install python3.12 python3.12-venv python3.12-dev`

**CMake errors about Boost** — Ensure the Boost download succeeded. The
headers should be at `_build/boost_1_84_0/boost/`.

**"SymEngineConfig.cmake not found"** — Check that SymEngine C++ compiled
successfully. Look in `_build/install/lib/cmake/symengine/`.

**symengine.py Cython errors** — Ensure the symengine.py version matches
the SymEngine C++ version (check `symengine_version.txt`).
