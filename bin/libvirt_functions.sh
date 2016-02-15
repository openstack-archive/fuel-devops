#!/bin/bash

PrintCommand() {
    echo "  virsh -c ${CONNECTION_STRING} ${*}" | sed 's/,/ /g' >&3
}

RunCommand() {
    if [ "${DEBUG}" -ne 0 ]; then
        PrintCommand "${@}"
    fi
    virsh -c "${CONNECTION_STRING}" "${@}"
}

CheckSnapshot() {
    RunCommand snapshot-list "${1}" --name | grep -q "^${2}$"
}

DomainDefine() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand define "${1}"
    else
        RunCommand define "${1}" >&5
    fi
}

DomainGetXML() {
    RunCommand dumpxml "${1}" --update-cpu > "${2}/${1}.xml"
}

NetworkAutoStart() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand net-autostart "${@}"
    else
        RunCommand net-autostart "${@}" >&5
    fi
}

NetworkDefine() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand net-define "${1}"
    else
        RunCommand net-define "${1}" >&5
    fi
}

NetworkFilterGetXML() {
    RunCommand nwfilter-dumpxml "${1}" |
        sed -r "/<uuid>(.*)<\/uuid>/d" > "${2}/nwfilter-${1}.xml"
}

NetworkFilterDefine() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand nwfilter-define "${1}"
    else
        RunCommand nwfilter-define "${1}" >&5
    fi
}

NetworkGetXML() {
    RunCommand net-dumpxml "${1}" > "${2}/network-${1}.xml"
}

NetworkStart() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand net-start "${1}"
    else
        RunCommand net-start "${1}" >&5
    fi
}

SnapshotGetCurrent() {
    RunCommand snapshot-current "${1}" --name 2>&5
}

SnapshotGetParent() {
    RunCommand snapshot-parent "${1}" --snapshotname "${2}" 2>&5
}

SnapshotGetXML() {
    RunCommand snapshot-dumpxml "${1}" --snapshotname "${2}" 2>&5
}

StoragePoolAutoStart() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand pool-autostart "${@}"
    else
        RunCommand pool-autostart "${@}" >&5
    fi
}

StoragePoolDefine() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand pool-define "${@}"
    else
        RunCommand pool-define "${@}" >&5
    fi
}

StoragePoolGetXML() {
    RunCommand pool-dumpxml "${@}"
}

StoragePoolInfo() {
    RunCommand pool-info "${@}"
}

StoragePoolStart() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand pool-start "${@}"
    else
        RunCommand pool-start "${@}" >&5
    fi
}

VolumeCreate() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand vol-create "${2:-default}" "${1}"
    else
        RunCommand vol-create "${2:-default}" "${1}" >&5
    fi
}

VolumeDownload() {
    if [ "${DEFS_ONLY:-0}" -ne 0 ]; then
        PrintCommand vol-download "${1}" "${2}/${1}" --pool "${3:-default}"
    else
        RunCommand vol-download "${1}" "${2}/${1}" --pool "${3:-default}"
    fi
}

VolumeUpload() {
    if [ "${DRY_RUN:-0}" -ne 0 ]; then
        PrintCommand vol-upload "${1}" "${2}/${1}" --pool "${3:-default}"
    else
        RunCommand vol-upload "${1}" "${2}/${1}" --pool "${3:-default}" >&5
    fi
}

VolumeGetXML() {
    RunCommand vol-dumpxml "${1}" --pool "${3:-default}" > "${2}/vol-${1}.xml"
}


