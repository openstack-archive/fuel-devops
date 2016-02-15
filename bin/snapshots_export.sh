#!/bin/bash

set -o errexit
set -o xtrace

USAGE="Usage: $0 HOST_NAMES SNAPSHOT_NAMES EXPORT_DIR [SNAPSHOTS_DIR]"

HOSTS="${1?${USAGE}}"
SNAPSHOTS="${2?${USAGE}}"
LIBVIRT_EXPORT_DIR="${3?${USAGE}}"
SNAPSHOTS_DIR="${4:-"/var/lib/libvirt/qemu/snapshot"}"
memstate_dir="${LIBVIRT_EXPORT_DIR}/memstate"

OLDIFS="${IFS}"
IFS=","

mkdir -p "${memstate_dir}"

for domain in ${HOSTS}; do
    domain_dir="${LIBVIRT_EXPORT_DIR}/snapshot/${domain}"
    mkdir -p "${domain_dir}"
    SNAPSHOT_ACTIVE=1
    for snapshot in ${SNAPSHOTS}; do
        snpath="${SNAPSHOTS_DIR}/${domain}/${snapshot}.xml"
        if [ "$(grep -c "<active>${SNAPSHOT_ACTIVE}</active>" "${snpath}")" -eq 0 ]
        then
            sed "s/<active>[^${SNAPSHOT_ACTIVE}]<\/active>/<active>${SNAPSHOT_ACTIVE}<\/active>/g"\
                "${snpath}" > "${domain_dir}/${snapshot}.xml"
        else
            cp -p "${snpath}" "${domain_dir}"
        fi
        SNAPSHOT_ACTIVE=0
        memstate_file=$(sed -ne\
            "s/\s\+<memory\s\+snapshot=\('\|\"\)external\('\|\"\)\s\+\(file=\('\|\"\)\(.*\)\('\|\"\)\/>\)\?/\5/gp"\
            "${domain_dir}/${snapshot}.xml")
        [ -n "${memstate_file}" ] && cp -p "${memstate_file}" "${memstate_dir}"
    done
done
IFS="${OLDIFS}"
chmod -R +r "${LIBVIRT_EXPORT_DIR}"
