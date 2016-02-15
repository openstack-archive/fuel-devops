#!/bin/bash

set -o errexit
set -o xtrace

USAGE="Usage: $0 EXPORT_DIR [SNAPSHOTS_DIR]"

LIBVIRT_EXPORT_DIR="${1?${USAGE}}"
SNAPSHOTS_DIR="${2:-"/var/lib/libvirt/qemu/snapshot"}"
MEMSTATE_EXPORT_DIR="${LIBVIRT_EXPORT_DIR}/memstate"
SNAPSHOTS_EXPORT_DIR="${LIBVIRT_EXPORT_DIR}/snapshot"

cp -fpr "${SNAPSHOTS_EXPORT_DIR}"/* "${SNAPSHOTS_DIR}"

for snapshot_path in "${SNAPSHOTS_EXPORT_DIR}"/*/*; do
    memstate_path=$(sed -ne\
        "s/\s\+<memory\s\+snapshot=\('\|\"\)external\('\|\"\)\s\+\(file=\('\|\"\)\(.*\)\('\|\"\)\/>\)\?/\5/gp"\
        "${snapshot_path}")
    if [ -n "${memstate_path}" ]; then
        memstate_dir=$(dirname "${memstate_path}")
        memstate_file=$(basename "${memstate_path}")
        mkdir -p "${memstate_dir}"
        cp -fp "${MEMSTATE_EXPORT_DIR}/${memstate_file}" "${memstate_path}"
    fi
done

# Restart libvirt-bin service to make snapshots visible in libvirt
service libvirt-bin restart
