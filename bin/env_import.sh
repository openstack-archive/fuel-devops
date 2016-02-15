#!/bin/bash

set -o errexit

# Set xtrace option if run by Jenkins
if [ -n "${WORKSPACE}" ]; then
    set -o xtrace
fi

baseDir=$(dirname "$0")
VERBOSITY=0
DRY_RUN=0
DEBUG=0

INVALIDOPTS_ERR=100
FILENOTFOUND_ERR=101
STORAGEPOOLCONF_ERR=102
STORAGEPOOLDEFINE_ERR=103
STORAGEPOOLSTART_ERR=104
STORAGEPOOLAUTOSTART_ERR=105
NETWORKDEFINE_ERR=106
NETWORKSTART_ERR=107
NETWORKAUTOSTART_ERR=108
VOLUMECREATE_ERR=109
VOLUMEUPLOAD_ERR=110
DOMAINDEFINE_ERR=111
SNAPSHOTIMPORT_ERR=112
MEMORYSTATEIMPORT_ERR=113

ShowHelp() {
cat << EOF
Usage: $0 [-dhv[vv]] DUMP_PATH
DUMP_PATH   - Path where all items to import are placed.

NOTE: Extra privileges are needed to run snapshot_import.sh script with sudo

The following options are available:

-d          - Nothing is to be imported. Only commands are to be printed.
-h          - Show this help page
-v          - Set verbose log level
-vv         - Increased verbosity
-vvv        - Set debug log level (print commands as well)


You can override the following variables:
DEVOPS_DB_NAME      - fuel-devops DB name
DEVOPS_DB_HOST      - fuel-devops DB hostname
DEVOPS_DB_USER      - fuel-devops DB username
DEVOPS_DB_PASSWORD  - fuel-devops DB password
CONNECTION_STRING   - hypervisor connection URI
STORAGE_POOL_NAME   - name of the storage pool to use
EOF
}

exec 3>&1

GetoptsVariables() {
    while getopts ":dhv" opt; do
        case $opt in
            d)
                DRY_RUN=1
                ;;
            h)
                ShowHelp
                exit 0
                ;;
            v)
                VERBOSITY=$((VERBOSITY+1))
                ;;
            \?)
                ShowHelp
                exit ${INVALIDOPTS_ERR}
                ;;

            :)
                echo "Option -${OPTARG} requires an argument." >&2
                ShowHelp
                exit ${INVALIDOPTS_ERR}
                ;;
        esac
    done
    shift $((OPTIND-1))

    if [ ${#} -ne 1 ]; then
        ShowHelp
        exit ${INVALIDOPTS_ERR}
    fi

    case ${VERBOSITY} in
        0)
            exec 4> /dev/null
            exec 5> /dev/null
            ;;
        1)
            exec 4>&1
            exec 5> /dev/null
            ;;
        2)
            exec 4>&1
            exec 5>&1
            ;;
        *)
            DEBUG=1
            exec 4>&1
            exec 5>&1
            ;;
    esac

    DUMP_PATH="${1}"
}

GlobalVariables() {
    echo "Using DB Name: ${DEVOPS_DB_NAME:=fuel_devops}" >&4
    echo "Using DB User: ${DEVOPS_DB_USER:=fuel_devops}" >&4
    echo "Using DB Host: ${DEVOPS_DB_HOST:=localhost}" >&4
    export PGPASSWORD="${DEVOPS_DB_PASSWORD:-fuel_devops}"

    FUELDEVOPS_EXPORT_DIR="${DUMP_PATH}/fuel-devops"
    LIBVIRT_EXPORT_DIR="${DUMP_PATH}/libvirt"
    LIBVIRT_EXPORT_DEFS_DIR="${LIBVIRT_EXPORT_DIR}/definitions"
    LIBVIRT_EXPORT_VOLUMES_DIR="${LIBVIRT_EXPORT_DIR}/volumes"
    LIBVIRT_EXPORT_SNAPSHOTS_DEFS_DIR="${LIBVIRT_EXPORT_DIR}/snapshot"
    LIBVIRT_EXPORT_MEMSTATE_DIR="${LIBVIRT_EXPORT_DIR}/memstate"
    CONNECTION_STRING="${CONNECTION_STRING:-"qemu:///system"}"
    SNAPSHOTS_DIR="${SNAPSHOTS_DIR:-"/var/lib/libvirt/qemu/snapshot"}"
    STORAGE_POOL="${STORAGE_POOL_NAME:-default}"
    # Tables in fuel-devops DB
    DEVOPS_ENVIRONMENT_TABLE="devops_environment"
    DEVOPS_NETWORK_TABLE="devops_network"
    DEVOPS_VOLUME_TABLE="devops_volume"
    DEVOPS_NODE_TABLE="devops_node"
    DEVOPS_INTERFACE_TABLE="devops_interface"
    DEVOPS_ADDRESS_TABLE="devops_address"
    DEVOPS_DISKDEVICE_TABLE="devops_diskdevice"
}

ImportItemsToDB() {
    # Args: $1 - SQL statement
    if [ ${DEBUG} -ne 0 ] || [ ${DRY_RUN} -ne 0 ]; then
        printf " Run: psql -h %s -U %s -c \"%s\"\n" "${DEVOPS_DB_HOST}" \
            "${DEVOPS_DB_USER}" "${@}" | sed 's/[ ]\+/ /g'
    fi
    if [ "${DRY_RUN}" -eq 0 ]; then
        psql -h "${DEVOPS_DB_HOST}" -U "${DEVOPS_DB_USER}" -c "${1}" >&5
    fi
}

CheckFile() {
    # Check if the file exists, set ERROR_FOUND to 1 otherwise
    # Args: $1 - file path
    [ -f "${1}" ] || {
        ERROR_FOUND=1
        echo "No ${1} file found" >&2
        }
}

CheckFuelDevopsFiles() {
    # Check if the files to import to fuel-devops DB exist.
    # Abort script otherwise
    ERROR_FOUND=0

    echo "=== Checking for exported tables from fuel-devops DB..." >&4
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/environment.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/networks.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/domains.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/interfaces.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/addresses.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/diskdevices.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/volumes.psql"
    CheckFile "${FUELDEVOPS_EXPORT_DIR}/volumes_empty.txt"

    # Compare ERROR_FOUND to 0 !!!!
    [ "${ERROR_FOUND}" -eq 0 ] || exit ${FILENOTFOUND_ERR}
}

CheckEnvFiles() {
    # Check for the files for libvirt.
    # Abort script otherwise
    local ERROR_FOUND=0
    echo "=== Checking for storage pool definition..." >&4
    env_name=$(awk '{ print $2 }' "${FUELDEVOPS_EXPORT_DIR}/environment.psql")
    pool_xmlfile="${LIBVIRT_EXPORT_DEFS_DIR}/pool-${STORAGE_POOL}.xml"
    CheckFile "${pool_xmlfile}"

    echo "=== Checking for domains definitions..." >&4
    domains=$(awk '{ print $2 }' "${FUELDEVOPS_EXPORT_DIR}/domains.psql")
    for domain in ${domains}; do
        domain_xmlfile="${LIBVIRT_EXPORT_DEFS_DIR}/${env_name}_${domain}.xml"
        CheckFile "${domain_xmlfile}"
    done

    echo "=== Checking for networks definitions..." >&4
    networks=$(awk -v env="${env_name}" '{ print env"_"$2 }' \
                    "${FUELDEVOPS_EXPORT_DIR}/networks.psql")
    for network in ${networks}; do
        net_xmlfile="${LIBVIRT_EXPORT_DEFS_DIR}/network-${network}.xml"
        CheckFile "${net_xmlfile}"
    done

    echo "=== Checking for volumes definitions and content files..." >&4
    volumes=$(awk -v env="${env_name}" '{ print env"_"$2 }' \
                    "${FUELDEVOPS_EXPORT_DIR}/volumes.psql")
    for volume in ${volumes}; do
        vol_xmlfile="${LIBVIRT_EXPORT_DEFS_DIR}/vol-${volume}.xml"
        vol_binfile="${LIBVIRT_EXPORT_VOLUMES_DIR}/${volume}"
        CheckFile "${vol_xmlfile}"
        if ! grep -q "^${volume}$" "${FUELDEVOPS_EXPORT_DIR}/volumes_empty.txt"
        then
            [ -f "${vol_binfile}" ] || {
                ERROR_FOUND=1
                echo "No ${vol_binfile} file found" >&2
                }
        fi
    done
    [ "${ERROR_FOUND}" -eq 0 ] || exit ${FILENOTFOUND_ERR}
}

ImportFuelDevopsDB() {
    echo "=== Import environment to fuel-devops DB..." >&4
    ENVIRONMENTS_IMPORT_SQL="\copy ${DEVOPS_ENVIRONMENT_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/environment.psql"
    ImportItemsToDB "${ENVIRONMENTS_IMPORT_SQL}"

    echo "=== Import networks to fuel-devops DB..." >&4
    NETWORKS_IMPORT_SQL="\copy ${DEVOPS_NETWORK_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/networks.psql"
    ImportItemsToDB "${NETWORKS_IMPORT_SQL}"

    echo "=== Import domains to fuel-devops DB..." >&4
    DOMAINS_IMPORT_SQL="\copy ${DEVOPS_NODE_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/domains.psql"
    ImportItemsToDB "${DOMAINS_IMPORT_SQL}"

    echo "=== Import interfaces to fuel-devops DB..." >&4
    INTERFACES_IMPORT_SQL="\copy ${DEVOPS_INTERFACE_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/interfaces.psql"
    ImportItemsToDB "${INTERFACES_IMPORT_SQL}"

    echo "=== Import addresses to fuel-devops DB..." >&4
    ADDRESSES_IMPORT_SQL="\copy ${DEVOPS_ADDRESS_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/addresses.psql"
    ImportItemsToDB "${ADDRESSES_IMPORT_SQL}"

    echo "=== Import volumes to fuel-devops DB..." >&4
    VOLUMES_IMPORT_SQL="\copy ${DEVOPS_VOLUME_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/volumes.psql"
    ImportItemsToDB "${VOLUMES_IMPORT_SQL}"

    echo "=== Import diskdevices to fuel-devops DB..." >&4
    DISKDEVICES_IMPORT_SQL="\copy ${DEVOPS_DISKDEVICE_TABLE}\
        from ${FUELDEVOPS_EXPORT_DIR}/diskdevices.psql"
    ImportItemsToDB "${DISKDEVICES_IMPORT_SQL}"
}

PrepareStoragePool() {
    echo "=== Checking if storage pool is already exist..." >&4
    StoragePoolInfo "${STORAGE_POOL}" > /dev/null
    if [ $? -eq 0 ]; then
        # Get dir path for the storage pool from the exported definition
        srcPoolDir=$(awk '{if ($0 ~ /<path>/) {
                gsub(/<\/?path>/, "");
                print $1;
            }}' "${LIBVIRT_EXPORT_DEFS_DIR}/pool-${STORAGE_POOL}.xml")
        # Get dir path from the existing storage pool
        targetPoolDir=$(StoragePoolGetXML "${STORAGE_POOL}" |\
                            awk '{if ($0 ~ /<path>/) {
                                    gsub(/<\/?path>/, "");
                                    print $1;}}')
        echo " Checking the storage pool configuration..." >&5
        if [ "${srcPoolDir}" != "${targetPoolDir}" ]; then
            echo " Default Storage pool: \"${STORAGE_POOL}\" on target system"\
                 "is set to ${targetPoolDir}, but on source system"\
                 "${srcPoolDir} is used." >&2
            exit ${STORAGEPOOLCONF_ERR}
        fi
        echo " Storage pool \"${STORAGE_POOL}\" is already configured..." >&5
    else
        echo " Defining the storage pool..." >&5
        StoragePoolDefine "${LIBVIRT_EXPORT_DEFS_DIR}/pool-${STORAGE_POOL}.xml"\
            || exit ${STORAGEPOOLDEFINE_ERR}
    fi
    echo " Start the storage pool if it is stopped..." >&5
    if [ "$(StoragePoolInfo "${STORAGE_POOL}" | awk '{
            if ($0 ~ /State/) { print $2 } }')" = "inactive" ]; then
        StoragePoolStart "${STORAGE_POOL}" || exit ${STORAGEPOOLSTART_ERR}
        echo "Started." >&5
    fi
    echo " Set autostart to the storage pool if it is not enabled..." >&5
    if [ "$(StoragePoolInfo "${STORAGE_POOL}" | awk '{
            if ($0 ~ /Autostart/) { print $2 } }')" = "no" ]; then
        StoragePoolAutoStart "${STORAGE_POOL}" ||\
            exit ${STORAGEPOOLAUTOSTART_ERR}
        echo "Autostart enabled." >&5
    fi
}

PrepareNetworks() {
    echo "=== Defining networks..." >&4
    for network in ${networks}; do
        echo " Defining network: ${network}" >&5
        NetworkDefine "${LIBVIRT_EXPORT_DEFS_DIR}/network-${network}.xml" ||\
            exit ${NETWORKDEFINE_ERR}
        echo " Set autostart for network: ${network}" >&5
        NetworkAutoStart "${network}" ||\
            exit ${NETWORKAUTOSTART_ERR}
        echo " Start network: ${network}" >&5
        NetworkStart "${network}" ||\
            exit ${NETWORKSTART_ERR}
    done
}

PrepareVolumes() {
    # Recursive function. Finds volumes which have the provided volumes as
    # backing stores, then defines ones and upload content to libvirt
    # Args: $1 - |-separated list of volumes id which are backing stores

    # Get volumes id which have the provided backing stores
    volumes_ids=$(awk -v env="${env_name}" -v backingStore="^(${1})$" '
                    BEGIN { resStr = "" }
                    { if ($6 ~ backingStore) { resStr = resStr"|"$1 }}
                    END { print resStr }' \
                    "${FUELDEVOPS_EXPORT_DIR}/volumes.psql")
    # Get volumes names which have the provided backing stores
    volumes=$(awk -v env="${env_name}" -v backingStore="^(${1})$"\
                    '{ if ($6 ~ backingStore) { print env"_"$2 }}' \
                    "${FUELDEVOPS_EXPORT_DIR}/volumes.psql")
    # Exit if there no volumes found
    [ ${#volumes} -eq 0 ] && return
    # Define and upload volume content for all volumes from gotten list
    for volume in ${volumes}; do
        echo " Creating volume: ${volume}" >&5
        VolumeCreate "${LIBVIRT_EXPORT_DEFS_DIR}/vol-${volume}.xml"\
            "${STORAGE_POOL}" || exit ${VOLUMECREATE_ERR}
        # Upload content only for volumes which names are not in the
        # volumes_empty file
        grep -q "^${volume}$" "${FUELDEVOPS_EXPORT_DIR}/volumes_empty.txt" ||\
            VolumeUpload "${volume}" "${LIBVIRT_EXPORT_VOLUMES_DIR}"\
                "${STORAGE_POOL}" || exit ${VOLUMEUPLOAD_ERR}
    done
    PrepareVolumes "${volumes_ids##|}"
}

DefineVolumes() {
    # Create all volumes
    echo "=== Defining volumes..." >&4
    # Start from volumes that have no backing stores (\N - in the volumes.psql)
    # It needs to escape backslash twice
    PrepareVolumes '\\\\N'
}

DefineDomains() {
    echo "=== Defining domains..." >&4
    for domain in ${domains}; do
        echo " Defining domain: ${domain}" >&5
        DomainDefine "${LIBVIRT_EXPORT_DEFS_DIR}/${env_name}_${domain}.xml" ||\
            exit ${DOMAINDEFINE_ERR}
    done
}

ImportSnapshots() {
    echo "=== Importing snapshots and memory state files..." >&4
    echo " Import snapshot definitions" >&5
    if [ "${DRY_RUN:-0}" -eq 1 ] || [ "${DEBUG}" -eq 1 ]; then
        echo "  sudo cp -fr ${LIBVIRT_EXPORT_SNAPSHOTS_DEFS_DIR}/*" \
            "${SNAPSHOTS_DIR}"
    fi
    if [ "${DRY_RUN:-0}" -eq 0 ]; then
        sudo cp -fr "${LIBVIRT_EXPORT_SNAPSHOTS_DEFS_DIR}"/* \
            "${SNAPSHOTS_DIR}" || exit ${SNAPSHOTIMPORT_ERR}
    fi
    echo " Import memory state files" >&5
    for snapshot_path in "${LIBVIRT_EXPORT_SNAPSHOTS_DEFS_DIR}"/*/*; do
        memstate_path=$(sed -ne\
            "s/\s\+<memory\s\+snapshot=\('\|\"\)external\('\|\"\)\s\+\(file=\('\|\"\)\(.*\)\('\|\"\)\/>\)\?/\5/gp"\
            "${snapshot_path}")
        if [ -n "${memstate_path}" ]; then
            echo "  Domain: $(basename "$(dirname "${snapshot_path}")")" \
              " snapshot: $(basename "${snapshot_path}" | sed 's/\.xml$//g')" >&5
            memstate_dir=$(dirname "${memstate_path}")
            memstate_file=$(basename "${memstate_path}")
            mkdir -p "${memstate_dir}"
            if [ "${DRY_RUN:-0}" -eq 1 ] || [ "${DEBUG}" -eq 1 ]; then
                echo "   cp -f ${LIBVIRT_EXPORT_MEMSTATE_DIR}/${memstate_file} "\
                    "${memstate_path}"
            fi
            if [ "${DRY_RUN:-0}" -eq 0 ]; then
                cp -f "${LIBVIRT_EXPORT_MEMSTATE_DIR}/${memstate_file}" \
                    "${memstate_path}" || exit ${MEMORYSTATEIMPORT_ERR}
            fi
        fi
    done
    echo "=== Restarting libvirt-bin daemon..." >&4
    if [ "${DRY_RUN:-0}" -eq 1 ] || [ "${DEBUG}" -eq 1 ]; then
        echo "  sudo service libvirt-bin restart"
    fi
    if [ "${DRY_RUN:-0}" -eq 0 ]; then
        sudo service libvirt-bin restart >&5
    fi
}

GetoptsVariables "${@}"
GlobalVariables
. "${baseDir}/libvirt_functions.sh"
CheckFuelDevopsFiles
CheckEnvFiles
ImportFuelDevopsDB
PrepareStoragePool
PrepareNetworks
DefineVolumes
DefineDomains
ImportSnapshots
