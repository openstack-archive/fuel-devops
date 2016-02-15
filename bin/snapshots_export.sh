#!/bin/bash

set -o errexit
set -o xtrace

USAGE="Usage: $0 EXPORT_DIR"

LIBVIRT_EXPORT_DIR="${1?${USAGE}}"
memstate_dir="${LIBVIRT_EXPORT_DIR}/memstate"

mkdir -p "${memstate_dir}"

for snapshot in "${LIBVIRT_EXPORT_DIR}/snapshot"/*/*.xml; do
    memstate_file=$(sed -ne\
        "s/\s\+<memory\s\+snapshot=\('\|\"\)external\('\|\"\)\s\+\(file=\('\|\"\)\(.*\)\('\|\"\)\/>\)\?/\5/gp"\
        "${snapshot}")
    [ -n "${memstate_file}" ] && cp -p "${memstate_file}" "${memstate_dir}"
done
chmod -R +r "${LIBVIRT_EXPORT_DIR}/memstate"
