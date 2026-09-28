#!/bin/bash
# Makes the skill's own Python environment (.venv inside the skill folder) and installs primp if missing (plus typing_extensions, which primp needs on Python 3.9 but pip 21 skips).
cd "$(dirname "$0")/.." || exit 1
[ -x .venv/bin/python ] || { echo "Creating .venv..."; python3 -m venv .venv || exit 1; }
.venv/bin/python -c "import primp" 2>/dev/null || { echo "Installing primp..."; .venv/bin/pip install -q --disable-pip-version-check primp typing_extensions || exit 1; }
echo "Ready: $(pwd)/.venv/bin/python"
