#!/bin/bash

set -o errexit

# Set xtrace option if run by Jenkins
if [ -n "${WORKSPACE}" ]; then
    set -o xtrace
fi

baseDir=$(dirname "$0")
DEFS_ONLY=0
DEBUG=0
EXPORT_CHANGES="${EXPORT_CHANGES:-0}"
HOST_PASSTHROUGH_CPU_MODE=0
VERBOSITY=0
WORKAROUND="${WORKAROUND:-0}"

INVALIDOPTS_ERR=100
NOENVFOUND_ERR=101
NOSNAPSHOTFOUND_ERR=102
INVALIDSNAPSHOTORDER_ERR=103
MEMORYSTATEEXPORT_ERR=104


ShowHelp() {
cat << EOF
Usage: $0 [OPTION]... ENV SNAPSHOT[,SNAPSHOT[,...]]

ENV         - Name of the environment to export snapshots from
SNAPSHOT    - Comma-separated list of snapshots to export. First snapshot in
              the list will be set as a current one

NOTE: Extra privileges are needed to copy memory state files and change ones'
    permissions with sudo

NOTE: First snapshot in the list must be the tip of the snapshot chain, as
    the script modifies neither snapshot tree nor volume tree during the export

The following options are available:

-d          - Only definitions are to be exported. Volumes and memory state
              files are skipped
-e path     - Set the directory for exporting system test environment to
-h          - Show this help page
-p          - Preserve changes made after snapshot (1st in the list) is created,
              i.e. the volume where changes are stored is to be exported as well
-s path     - Directory where snapshot definitions are stored
-v          - Set verbose log level
-vv         - Set debug log level
-w          - Workaround for vol-download poor performance for older
              libvirt versions: using cp
-ww         - Workaround: cp called via sudo

You can override the following variables:
DEVOPS_DB_NAME      - fuel-devops DB name
DEVOPS_DB_HOST      - fuel-devops DB hostname
DEVOPS_DB_USER      - fuel-devops DB username
DEVOPS_DB_PASSWORD  - fuel-devops DB password
EXPORT_CHANGES      - (0-default,1). 1 enables -p option (0 by default)
CONNECTION_STRING   - hypervisor connection URI
STORAGE_POOL_NAME   - name of the storage pool to use
WORKAROUND          - (0-default,1,2). 1 (-w option) / 2 (-ww option)
EOF
}

exec 3>&1

GetoptsVariables() {
    while getopts ":de:hps:vw" opt; do
        case $opt in
            d)
                DEFS_ONLY=1
                ;;
            e)
                EXPORT_DIR="${OPTARG}"
                ;;
            h)
                ShowHelp
                exit 0
                ;;
            p)
                EXPORT_CHANGES=1
                ;;
            s)
                SNAPSHOTS_DIR="${OPTARG}"
                ;;
            v)
                VERBOSITY=$((VERBOSITY+1))
                ;;
            w)
                WORKAROUND=$((WORKAROUND+1))
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

    if [ ${#} -ne 2 ]; then
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
        *)
            DEBUG=1
            exec 4>&1
            exec 5>&1
            ;;
    esac

    SYSTEST_ENV="${1}"
    SNAPSHOT_NAMES="${2}"

    [ "${DEBUG}" -eq 0 ] || echo "Debug mode on."
    [ "${DEFS_ONLY}" -eq 0 ] || echo "Definitions only are to be exported."
}

GlobalVariables() {
    echo "Using DB Name: ${DEVOPS_DB_NAME:=fuel_devops}" >&4
    echo "Using DB Host: ${DEVOPS_DB_HOST:=localhost}" >&4
    echo "Using DB User: ${DEVOPS_DB_USER:=fuel_devops}" >&4
    export PGPASSWORD="${DEVOPS_DB_PASSWORD:-fuel_devops}"

    EXPORT_DIR="${EXPORT_DIR:-"${HOME}/.devops/export"}"
    FUELDEVOPS_EXPORT_DIR="${EXPORT_DIR}/fuel-devops"
    LIBVIRT_EXPORT_DIR="${EXPORT_DIR}/libvirt"
    LIBVIRT_EXPORT_DEFS_DIR="${LIBVIRT_EXPORT_DIR}/definitions"
    LIBVIRT_EXPORT_VOLUMES_DIR="${LIBVIRT_EXPORT_DIR}/volumes"
    LIBVIRT_EXPORT_SNAPSHOTS_DEFS_DIR="${LIBVIRT_EXPORT_DIR}/snapshot"
    LIBVIRT_EXPORT_MEMSTATE_DIR="${LIBVIRT_EXPORT_DIR}/memstate"
    CONNECTION_STRING="${CONNECTION_STRING:-"qemu:///system"}"
    STORAGE_POOL="default"
    SNAPSHOTS_DIR="${SNAPSHOTS_DIR:-"/var/lib/libvirt/qemu/snapshot"}"
    # Tables in fuel-devops DB
    DEVOPS_ENVIRONMENT_TABLE="devops_environment"
    DEVOPS_NETWORK_TABLE="devops_network"
    DEVOPS_VOLUME_TABLE="devops_volume"
    DEVOPS_NODE_TABLE="devops_node"
    DEVOPS_INTERFACE_TABLE="devops_interface"
    DEVOPS_ADDRESS_TABLE="devops_address"
    DEVOPS_DISKDEVICE_TABLE="devops_diskdevice"
}

ExportItemsFromDB() {
    # Args: $@ - SQL statement
    printf " Run: psql -h %s -U %s -c \"%s\"\n" "${DEVOPS_DB_HOST}" \
        "${DEVOPS_DB_USER}" "${@}" | sed 's/[ ]\+/ /g' >&5
    psql -h "${DEVOPS_DB_HOST}" -U "${DEVOPS_DB_USER}" -c "${1}" >&5
}

RunPSQL() {
    # Args: $@ - SQL statement
    printf " Run: psql -h %s -U %s -t -c \"%s\"\n" "${DEVOPS_DB_HOST}" \
        "${DEVOPS_DB_USER}" "${@}" | sed 's/[ ]\+/ /g' >&5
    res=$(psql -h "${DEVOPS_DB_HOST}" -U "${DEVOPS_DB_USER}" -t -c "${@}")
    echo "${res}" | sed 's/[[:space:]]//'
}

GetItemsFromDB() {
    # Create comma-separated list of items returned by RunPSQL
    # Args: $1 - SQL statement
    for item in $(RunPSQL "${1}"); do
        items_list="${items_list:-""},${item}"
    done
    items_list="${items_list##,}"
    echo "${items_list}"
}

CheckEnvironmentExists() {
    #Check if the environment exist
    env_count=$(RunPSQL \
                   "select count(*) from ${DEVOPS_ENVIRONMENT_TABLE}\
                   where name='${SYSTEST_ENV}'")

    if [ "${env_count}" -eq 0 ]; then
        echo "No environments found: ${SYSTEST_ENV}" >&2
        exit ${NOENVFOUND_ERR}
    fi

    # Get environment id in fuel-devops DB
    ENVIRONMENT_ID_SQL="select id from ${DEVOPS_ENVIRONMENT_TABLE}\
                        where name='${SYSTEST_ENV}'"
    env_id=$(GetItemsFromDB "${ENVIRONMENT_ID_SQL}")

    # Get domain names created in the envionment from fuel-devops DB
    DOMAINS_NAMES_SQL="select concat('${SYSTEST_ENV}_', name) \
                          from ${DEVOPS_NODE_TABLE}\
                          where environment_id='${env_id}'"
    domain_names=$(GetItemsFromDB "${DOMAINS_NAMES_SQL}")
}

CheckSnapshotExists() {
    # Check the requested snapshot is available across all the domains
    # from the environment. Abort otherwise.
    OLDIFS="${IFS}"
    IFS=","
    for domain in ${domain_names}; do
        for snapshot_name in ${SNAPSHOT_NAMES}; do
            if ! CheckSnapshot "${domain}" "${snapshot_name}"; then
                echo "No '${snapshot_name}' snapshot found for '${domain}'" >&2
                exit ${NOSNAPSHOTFOUND_ERR}
            fi
        done
    done
    IFS="${OLDIFS}"
}

ExportEnvironmentRecords() {
    # Export environment record from fuel-devops DB
    echo "=== Export environment records from DB" >&4
    mkdir -p "${FUELDEVOPS_EXPORT_DIR}"
    ENVIRONMENTS_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_ENVIRONMENT_TABLE}\
            where name='${SYSTEST_ENV}') \
        to ${FUELDEVOPS_EXPORT_DIR}/environment.psql"
    ExportItemsFromDB "${ENVIRONMENTS_EXPORT_SQL}"
}

ExportNetworksRecords() {
    # Export networks records from fuel-devops DB
    echo "=== Export networks records from DB" >&4
    NETWORKS_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_NETWORK_TABLE}\
            where environment_id='${env_id}') \
        to ${FUELDEVOPS_EXPORT_DIR}/networks.psql"
    ExportItemsFromDB "${NETWORKS_EXPORT_SQL}"
}

ExportDomainsRecords() {
    # Export domains records from fuel-devops DB
    echo "=== Export domains records from DB" >&4
    DOMAINS_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_NODE_TABLE} where environment_id='${env_id}')\
        to ${FUELDEVOPS_EXPORT_DIR}/domains.psql"
    ExportItemsFromDB "${DOMAINS_EXPORT_SQL}"

    # Get list of domains ids in the environment
    DOMAINS_IDS_SQL="select id from ${DEVOPS_NODE_TABLE}\
                        where environment_id='${env_id}'"
    domains_list=$(GetItemsFromDB "${DOMAINS_IDS_SQL}")
}

ExportInterfacesRecords() {
    # Export interfaces records from fuel-devops DB
    echo "=== Export interfaces records from DB" >&4
    INTERFACES_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_INTERFACE_TABLE} \
            where node_id in (${domains_list})) \
        to ${FUELDEVOPS_EXPORT_DIR}/interfaces.psql"
    ExportItemsFromDB "${INTERFACES_EXPORT_SQL}"

    # Get list of interfaces in the environment
    INTERFACES_IDS_SQL="select id from ${DEVOPS_INTERFACE_TABLE}\
                            where node_id in (${domains_list})"
    interfaces_list=$(GetItemsFromDB "${INTERFACES_IDS_SQL}")
}

ExportAddressesRecords() {
    # Export addresses records from fuel-devops DB
    echo "=== Export addresses records from DB" >&4
    ADDRESSES_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_ADDRESS_TABLE} \
            where interface_id in (${interfaces_list})) \
        to ${FUELDEVOPS_EXPORT_DIR}/addresses.psql"
    ExportItemsFromDB "${ADDRESSES_EXPORT_SQL}"
}

ExportDiskDevicesRecords() {
    # Export diskdevices records from fuel-devops DB
    echo "=== Export disk devices records from DB" >&4
    DISKDEVICES_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_DISKDEVICE_TABLE} \
            where node_id in (${domains_list})) \
        to ${FUELDEVOPS_EXPORT_DIR}/diskdevices.psql"
    ExportItemsFromDB "${DISKDEVICES_EXPORT_SQL}"
}

GetDiskDevicesFromSnapshot() {
    # Takes snapshot XML definition, parses it
    # and returns |-separated list of strings like
    # <disk_name>\t<path_to_volume_file>
    # Args: $1 - name of the domain, $2 - name of the snapshot
sed -n -f - <(SnapshotGetXML "${1}" "${2}") <<-'SEDSCRIPT'
/<disks>/{
    /<disks>/n

    :loop
    N
    s/\(.*\)<disk name='\([a-z]*\)'\(.*\)<source file='\(.*\)'\(.*\)/\2\t\4|/
    thold
    bnext

    :hold
    H

    :next
    /<\/disks>/!bloop

    x
    s/|$//g
    s/\n//g
    p
}
SEDSCRIPT
}

SetCurrentVMState() {
    # Set VM state to the state from the snapshot which is the first one
    # in the list of snapshots to export
    # Args: $1 - name of the domain, $2 - name of the snapshot
    diskdevices=$(GetDiskDevicesFromSnapshot "${1}" "${2}")
    # Get id for the domain name from exported domain records
    dom_id=$(awk -v name="${1#${SYSTEST_ENV}_}" '
          { if ($2 == name) {
                print $1
            }
          }' "${FUELDEVOPS_EXPORT_DIR}/domains.psql")
    SNAPSHOT_VOLUME_IDS=""
    local OLDIFS="${IFS}"
    IFS="|"
    # Iterate over |- separated list of diskdevices gotten from snapshot
    for disk in ${diskdevices}; do
        d_dev=$(echo "$disk" | awk '{ print $1 }')
        d_path=$(echo "$disk" | awk '{ print $2 }')
        # Get volume id connected to the disk of the domain from diskdevices
        # records. (7th column)
        vol_id=$(awk -v dev="${d_dev}" -v id="${dom_id}" 'BEGIN { FS=" " }
                      { if (($2 == "disk") && ($5 == dev) &&
                                ($6 == id)) {
                            print $7
                        }
                      }' "${FUELDEVOPS_EXPORT_DIR}/diskdevices.psql")

        # Get escaped path of the volume file
        current_volpath=$(awk -v id="${vol_id}" '
                            { if ($1 == id) { gsub(/\//, "\\/"); print $3 }}
                            ' "${FUELDEVOPS_EXPORT_DIR}/volumes_all.psql")
        # Escaped path of the volume gotten from snapshot XML
        new_volpath=$(echo "$disk" | awk '{ gsub(/\//, "\\/"); print $2 }')
        # Update domain XML definition
        sed "s/${current_volpath}/${new_volpath}/g"\
             "${LIBVIRT_EXPORT_DEFS_DIR}/${1}.xml" >\
             "${LIBVIRT_EXPORT_DEFS_DIR}/${1}.xml.bak"
        mv "${LIBVIRT_EXPORT_DEFS_DIR}/${1}.xml.bak"\
           "${LIBVIRT_EXPORT_DEFS_DIR}/${1}.xml"

        # Get volume id of the volume from snapshot XML
        new_volid=$(awk -v uuid="${d_path}" '
                        { if ($3 == uuid) { print $1 }}
                        ' "${FUELDEVOPS_EXPORT_DIR}/volumes_all.psql")
        # Update exported diskdevices records with new volume_id
        awk -v dev="${d_dev}" -v id="${dom_id}" -v volid="${new_volid}" '
            BEGIN { OFS="\t" }
            { if (($2 == "disk") && ($5 == dev) &&
                    ($6 == id)) {
                $7 = volid;
              }
            print > ARGV[1];
            }' "${FUELDEVOPS_EXPORT_DIR}/diskdevices.psql"
        # Save list of recently processed volumes
        SNAPSHOT_VOLUME_IDS="${SNAPSHOT_VOLUME_IDS},${new_volid}"
    done
    IFS="${OLDIFS}"
    echo "${SNAPSHOT_VOLUME_IDS}"
}

ExportAllVolumesRecords() {
    echo "=== Export all volumes records from DB" >&4
    VOLUMES_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_VOLUME_TABLE} \
            where environment_id='${env_id}') \
        to ${FUELDEVOPS_EXPORT_DIR}/volumes_all.psql"
    ExportItemsFromDB "${VOLUMES_EXPORT_SQL}"
}

ExportVolumesRecords() {
    # Export volumes records requested by ids
    # Args: $1 - comma-separated list of volumes ids
    echo "=== Export volumes records from DB" >&4
    VOLUMES_EXPORT_SQL="\copy \
        (select * from ${DEVOPS_VOLUME_TABLE} \
            where id in (${1})) \
        to ${FUELDEVOPS_EXPORT_DIR}/volumes.psql"
    ExportItemsFromDB "${VOLUMES_EXPORT_SQL}"
}

ProcessSnapshotChain() {
    # Recursive function. Walks through the snapshots chain and creates
    # comma-separated list of all unique snapshots to SNAPSHOT_EXPORT_LIST
    # Args: $1 - domain name, $2 - snapshot name
    if [ "${CURRENT_SNAPSHOT}" = "${2}" ]; then
        echo "First snapshot should be the tip"\
             " of the exported snapshot chain" >&2
        exit ${INVALIDSNAPSHOTORDER_ERR}
    fi
    echo "${SNAPSHOT_EXPORT_LIST}" | grep -q "\(^\|,\)${2}\(,\|$\)"  || \
        SNAPSHOT_EXPORT_LIST="${SNAPSHOT_EXPORT_LIST},${2}"
    parent=$(SnapshotGetParent "${1}" "${2}") || return 0
    ProcessSnapshotChain "${1}" "${parent}"
}

ProcessVolumeChain() {
    # Recursive function. Walks through the volumes chain and creates
    # comma-separated list of all volumes ids to VOLUME_EXPORT_LIST
    # Args: $1 - volume id
    backingStore=$(awk -v id="${1}" '
                    { if (($1 == id) && ($6 != "\\N")) { print $6 }}
                    ' "${FUELDEVOPS_EXPORT_DIR}/volumes_all.psql")
    [ -z "${backingStore}" ] && return
    echo "${VOLUME_EXPORT_LIST}" | grep -q "\<${backingStore}\>"  || \
        VOLUME_EXPORT_LIST="${VOLUME_EXPORT_LIST},${backingStore}"
    ProcessVolumeChain "${backingStore}"
}

ProcessDomains() {
    mkdir -p "${LIBVIRT_EXPORT_DEFS_DIR}"
    OLDIFS="${IFS}"
    IFS=","
    EMPTY_VOLUME_LIST=""
    # Create comma-separated list of volume ids for disks of cdrom type
    VOLUME_CDROM_EXPORT_LIST=$(awk 'BEGIN { resStr = "" }
                       { if ($2 == "cdrom") { resStr = resStr","$7 }}
                       END { print resStr }' \
                       "${FUELDEVOPS_EXPORT_DIR}/diskdevices.psql")
    VOLUME_EXPORT_LIST="${VOLUME_CDROM_EXPORT_LIST}"
    # Iterate over comma-separated list of domains names
    for domain in ${domain_names}; do
        unset CURRENT_SNAPSHOT
        HEAD_VOLUME_IDS=""
        SNAPSHOT_EXPORT_LIST=""
        DomainGetXML "${domain}" "${LIBVIRT_EXPORT_DEFS_DIR}"
        # Set to 1 if using host-passthrough cpu mode
        HOST_PASSTHROUGH_CPU_MODE=$(\
            grep -c "cpu mode=\('\|\"\)host-passthrough\('\|\"\)" \
                "${LIBVIRT_EXPORT_DEFS_DIR}/${domain}.xml")
        # Iterate over list of requested snapshots to export
        for SNAPSHOT_NAME in ${SNAPSHOT_NAMES}; do
            if [ "$(SnapshotGetCurrent "${domain}")" != "${SNAPSHOT_NAME}" ] &&\
                    [ -z "${CURRENT_SNAPSHOT}" ]; then
                # If requested snapshot is not set as a current on exported
                # environment and it is the first in the list to export
                # we set VM state to the state from this snapshot
                echo "=== Changing ${domain} VM state" >&4
                NEW_CURRENT_VOLUME_IDS=$(SetCurrentVMState "${domain}"\
                                            "${SNAPSHOT_NAME}")
                HEAD_VOLUME_IDS="${HEAD_VOLUME_IDS}${NEW_CURRENT_VOLUME_IDS}"
            else
                # Otherwise we collect volumes ids to export in
                # HEAD_VOLUME_IDS variable
                diskdevices=$(GetDiskDevicesFromSnapshot "${domain}"\
                                "${SNAPSHOT_NAME}" | \
                                awk 'BEGIN {RS="|"; ORS=","} { print $2 }')
                for disk in ${diskdevices%%,}; do
                    new_volid=$(awk -v uuid="${disk}" '
                                { if ($3 == uuid) { print $1 }}
                                ' "${FUELDEVOPS_EXPORT_DIR}/volumes_all.psql")
                    HEAD_VOLUME_IDS="${HEAD_VOLUME_IDS},${new_volid}"
                done
            fi
            # Get snapshot names to export from the chain
            ProcessSnapshotChain "${domain}" "${SNAPSHOT_NAME}"
            # We do not export volumes of upper levels if it is not requested,
            # as these volumes does not relate to the state from snapshot
            if [ -n "${CURRENT_SNAPSHOT}" ] || [ "${EXPORT_CHANGES}" -eq 0 ];
            then
                EMPTY_VOLUME_LIST="${EMPTY_VOLUME_LIST}${HEAD_VOLUME_IDS}"
            else
                VOLUME_EXPORT_LIST="${VOLUME_EXPORT_LIST}${HEAD_VOLUME_IDS}"
            fi
            CURRENT_SNAPSHOT="${CURRENT_SNAPSHOT:-${SNAPSHOT_NAME}}"
        done
        # Get volumes ids to export from the chain
        for volume in ${HEAD_VOLUME_IDS##,}; do
            ProcessVolumeChain "${volume}"
        done
    done
    IFS="${OLDIFS}"
}

ExportStoragePoolDefinition() {
    echo "=== Export definition of storage pool" >&4
    StoragePoolGetXML "${STORAGE_POOL}" >\
        "${LIBVIRT_EXPORT_DEFS_DIR}/pool-${STORAGE_POOL}.xml"
}

ExportNetworksDefinitions() {
    echo "=== Export definitions of networks" >&4
    awk -v env="${SYSTEST_ENV}" '{ print env"_"$2 }' \
        "${FUELDEVOPS_EXPORT_DIR}/networks.psql" | while read network; do
        NetworkGetXML "${network}" "${LIBVIRT_EXPORT_DEFS_DIR}"
    done
}

ExportVolumesDefinitions() {
    echo "=== Export definitions of volumes" >&4
    # Get volumes XML definitions
    awk -v env="${SYSTEST_ENV}" '{ print env"_"$2 }' \
        "${FUELDEVOPS_EXPORT_DIR}/volumes.psql" |
    while read -r volume; do
        VolumeGetXML "${volume}" "${LIBVIRT_EXPORT_DEFS_DIR}" "${STORAGE_POOL}"
    done
    # Create |-separated list of volumes ids as this list can act as a regexp
    VOLUME_CDROM_LIST_REGEX=$(echo "${VOLUME_CDROM_EXPORT_LIST##,}" | \
                                sed 's/,/|/g')
    # Get volumes names for the volumes of cdrom type
    cdrom_volumes=$(awk -v env="${SYSTEST_ENV}"\
                        -v id="^(${VOLUME_CDROM_LIST_REGEX})$" '
                        { if ($1 ~ id) {print env"_"$2} }' \
                        "${FUELDEVOPS_EXPORT_DIR}/volumes.psql")
    # Correct type for volumes of cdrom type in XML definition
    # It must be 'raw' but in the exported XML we have 'iso'
    for volume in ${cdrom_volumes}; do
        sed "s/type='iso'/type='raw'/g" \
            "${LIBVIRT_EXPORT_DEFS_DIR}/vol-${volume}.xml" > \
            "${LIBVIRT_EXPORT_DEFS_DIR}/vol-${volume}.xml.new"
        mv "${LIBVIRT_EXPORT_DEFS_DIR}/vol-${volume}.xml.new"\
           "${LIBVIRT_EXPORT_DEFS_DIR}/vol-${volume}.xml"
    done
    # Create file with names of volumes for which we do not export
    # content
    echo > "${FUELDEVOPS_EXPORT_DIR}/volumes_empty.txt"
    if [ -n "${EMPTY_VOLUME_LIST}" ]; then
        VOLUMES_EMPTY_SQL="select concat('${SYSTEST_ENV}_', name)\
                             from ${DEVOPS_VOLUME_TABLE} \
                             where id in (${EMPTY_VOLUME_LIST##,});"
        RunPSQL "${VOLUMES_EMPTY_SQL}" > \
            "${FUELDEVOPS_EXPORT_DIR}/volumes_empty.txt"
    fi
}

ExportVolumesContents() {
    mkdir -p "${LIBVIRT_EXPORT_VOLUMES_DIR}"
    echo "=== Download volumes" >&4
    VOLUMES_DOWNLOAD_SQL="select name from ${DEVOPS_VOLUME_TABLE} \
                          where id in (${VOLUME_EXPORT_LIST##,});"
    volume_names=$(RunPSQL "${VOLUMES_DOWNLOAD_SQL}")
    for volume in ${volume_names}; do
        if [ "${WORKAROUND}" -eq 0 ]; then
            VolumeDownload "${SYSTEST_ENV}_${volume}"\
                "${LIBVIRT_EXPORT_VOLUMES_DIR}" "${STORAGE_POOL}"
        else
            # Workaround for case when libvirt vol-download shows poor
            # performance. It has 2 options: run w/ sudo and w/o sudo.
            # bug: https://bugzilla.redhat.com/show_bug.cgi?id=1026136
            volpath=$(awk -v vol="${volume}" '{
                        if ($2 == vol) { print $3 } }' \
                        "${FUELDEVOPS_EXPORT_DIR}/volumes.psql")
            if [ "${WORKAROUND}" -eq 1 ]; then
                if [ "${DEFS_ONLY}" -eq 1 ] || [ "${DEBUG}" -eq 1 ]; then
                    echo "  cp -f ${volpath} ${LIBVIRT_EXPORT_VOLUMES_DIR}"
                fi
                if [ "${DEFS_ONLY}" -eq 0 ]; then
                    cp -f "${volpath}" "${LIBVIRT_EXPORT_VOLUMES_DIR}"
                fi
            else
                if [ "${DEFS_ONLY}" -eq 1 ] || [ "${DEBUG}" -eq 1 ]; then
                    echo "  sudo cp -f ${volpath} ${LIBVIRT_EXPORT_VOLUMES_DIR}"
                fi
                if [ "${DEFS_ONLY}" -eq 0 ]; then
                    sudo cp -f "${volpath}" "${LIBVIRT_EXPORT_VOLUMES_DIR}"
                fi
            fi
        fi
    done
}

ExportSnapshotsDefinitions() {
    echo "=== Export definitions of snapshots and memory state files" >&4
    OLDIFS="${IFS}"
    IFS=","
    mkdir -p "${LIBVIRT_EXPORT_MEMSTATE_DIR}"
    for domain in ${domain_names}; do
        domain_dir="${LIBVIRT_EXPORT_SNAPSHOTS_DEFS_DIR}/${domain}"
        mkdir -p "${domain_dir}"
        SNAPSHOT_ACTIVE=1
        if [ "${HOST_PASSTHROUGH_CPU_MODE}" -eq 1 ]; then
            # Get CPU configuration from domain definitions in case of
            # host-passthrough cpu mode and change all new lines to
            # \n symbols to be able to use this in sed.
            DOMAIN_CPU_NEWLINE=""
            while IFS='' read -r line; do
                DOMAIN_CPU_NEWLINE="${DOMAIN_CPU_NEWLINE}${line}\n"
            done < <(sed -n "/^\s*<cpu mode/,/^\s*<\/cpu>/p"\
                "${LIBVIRT_EXPORT_DEFS_DIR}/${domain}.xml")
        fi
        for snapshot in ${SNAPSHOT_EXPORT_LIST##,}; do
            SnapshotGetXML "${domain}" "${snapshot}" >\
                "${domain_dir}/${snapshot}.xml"
            # Add active XML node to snapshot definition and set it to 1
            # if snapshot is current (first in the list), otherwise to 0
            sed "s/<\/domainsnapshot>/  <active>${SNAPSHOT_ACTIVE}<\/active>\n<\/domainsnapshot>/g"\
                "${domain_dir}/${snapshot}.xml" > \
                "${domain_dir}/${snapshot}.xml.new"
            if [ "${HOST_PASSTHROUGH_CPU_MODE}" -eq 1 ]; then
                # Replace CPU configuration in snapshot definition with one
                # from domain definition.
                # First, we have to escape all forward slashes
                SEDREADY_DOMAIN_CPU="${DOMAIN_CPU_NEWLINE//\//\\/}"
                sed -n '/\s*<cpu mode/{:loop;N;/\s*<\/cpu>/!bloop;N;s/.*\n/'"${SEDREADY_DOMAIN_CPU}"'/};p' \
                    "${domain_dir}/${snapshot}.xml.new" > "${domain_dir}/${snapshot}.xml"
                rm "${domain_dir}/${snapshot}.xml.new"
            else
                mv "${domain_dir}/${snapshot}.xml.new"\
                    "${domain_dir}/${snapshot}.xml"
            fi
            memstate_file=$(sed -ne\
                "s/\s\+<memory\s\+snapshot=\('\|\"\)external\('\|\"\)\s\+\(file=\('\|\"\)\(.*\)\('\|\"\)\/>\)\?/\5/gp"\
                "${domain_dir}/${snapshot}.xml")
            if [ -n "${memstate_file}" ]; then
                if [ "${DEFS_ONLY}" -eq 1 ] || [ "${DEBUG}" -eq 1 ]; then
                    echo "  sudo cp --no-preserve=mode ${memstate_file}"\
                         " ${LIBVIRT_EXPORT_MEMSTATE_DIR}"
                fi
                if [ "${DEFS_ONLY}" -eq 0 ]; then
                    sudo cp --no-preserve=mode "${memstate_file}"\
                        "${LIBVIRT_EXPORT_MEMSTATE_DIR}" || \
                        exit ${MEMORYSTATEEXPORT_ERR}
                fi
            fi
            SNAPSHOT_ACTIVE=0
        done
    done
    IFS="${OLDIFS}"
}


GetoptsVariables "${@}"
GlobalVariables
. "${baseDir}/libvirt_functions.sh"
echo "=== Check environment" >&4
CheckEnvironmentExists
CheckSnapshotExists
ExportEnvironmentRecords
ExportNetworksRecords
ExportDomainsRecords
ExportInterfacesRecords
ExportAddressesRecords
ExportDiskDevicesRecords
ExportAllVolumesRecords
ProcessDomains
VOLUME_EXPORT_FULL_LIST="${EMPTY_VOLUME_LIST}${VOLUME_EXPORT_LIST}"
ExportVolumesRecords "${VOLUME_EXPORT_FULL_LIST##,}"
ExportStoragePoolDefinition
ExportNetworksDefinitions
ExportVolumesDefinitions
ExportVolumesContents
ExportSnapshotsDefinitions

