#!/bin/bash
set -euo pipefail

COVERAGE_SUFFIX="${COVERAGE_SUFFIX:-dev}"
HTML_COVDIR="htmlcov_${COVERAGE_SUFFIX}"
COV_DATAFILE=".coverage_${COVERAGE_SUFFIX}"

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd -P )"
VENV_DIR="${VENV_DIR:-venv}"
VENV_ROOT="${VENV_DIR:-$PROJECT_ROOT/$VENV_DIR}"

if ! [[ -z "${BUILD_CONTEXT+x}" ]]; then
    if [[ "$BUILD_CONTEXT" == "ci" ]]; then
        if ! [[ -z "${NODE_NAME+x}" ]]; then
            echo "Running tests on agent: ${NODE_NAME}"
            export PIP_CACHE_DIR=$VENV_ROOT/pip_cache   # Avoid concurrent cache access issue on CI
            echo "PIP_CACHE_DIR=${PIP_CACHE_DIR}"
        fi
    fi
fi

set -x 

python3 -m coverage run --data-file ${COV_DATAFILE} -m unittest -v
python3 -m mypy isotp --strict --no-warn-unused-ignore
python3 -m coverage report --data-file ${COV_DATAFILE}
python3 -m coverage html --data-file ${COV_DATAFILE} -d $HTML_COVDIR
  