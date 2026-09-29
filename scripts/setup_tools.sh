#!/usr/bin/env bash
# Install the open-source toolchain pinned in requirements-tools.txt.
#
#   EDA_HOME   where the OSS CAD Suite is extracted (default /opt/eda)
#
# Needs curl, tar and (for place-and-route only) a running Docker daemon.
set -euo pipefail

EDA_HOME=${EDA_HOME:-/opt/eda}
OSS_CAD_TAG=2026-09-28
OSS_CAD_TGZ=oss-cad-suite-linux-x64-${OSS_CAD_TAG//-/}.tgz
ORFS_IMAGE=openroad/orfs@sha256:2e5bf6fe865e102ca2313aba1d849da50f5973bc91c4212a2f68e7d905a39c8f

mkdir -p "$EDA_HOME"
if [ ! -x "$EDA_HOME/oss-cad-suite/bin/yosys" ]; then
    echo "Downloading OSS CAD Suite $OSS_CAD_TAG ..."
    curl -fL -o "$EDA_HOME/$OSS_CAD_TGZ" \
        "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$OSS_CAD_TAG/$OSS_CAD_TGZ"
    tar -xzf "$EDA_HOME/$OSS_CAD_TGZ" -C "$EDA_HOME"
    rm -f "$EDA_HOME/$OSS_CAD_TGZ"
fi
"$EDA_HOME/oss-cad-suite/bin/yosys" -V

if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    docker pull "$ORFS_IMAGE"
    docker tag "$ORFS_IMAGE" openroad/orfs:latest
else
    echo "Docker is not running: skipping the OpenROAD image (only needed for 'make pd')."
fi

echo "Done. Use: make OSS_CAD=$EDA_HOME/oss-cad-suite test"
