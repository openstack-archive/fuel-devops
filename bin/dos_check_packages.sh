#!/bin/bash

location=$(dirname $0)
package_list="git,libyaml-dev,libffi-dev,python-dev,python-pip,qemu,libvirt-bin,libvirt-dev,vlan,bridge-utils,genisoimage"

#Check if all necessary packages are installed.
check_packages() {
    OLD_IFS="${IFS}"
    IFS=","
    if [ "${N}" ==  "" ]; then
    echo "Running apt-get update before checking"
    run "apt-get update"
    N+="1"
    fi
    for package in ${1}; do
        if $(apt-cache policy ${package}|grep -q "Installed: (none)"); then
            if [ "${VERBOSE}" == "VERBOSE" ]; then
                echo "Package ${package} doesn't installed"
                sleep 1
            fi
            instalation_packages+="${package} "
        else
            if [ "${VERBOSE}" == "VERBOSE" ]; then
            echo -e "Package ${package} is already installed. ----- OK\n"
            sleep 1
            fi
        fi
    done
    IFS="${OLD_IFS}"
    if [ "${INTERACTIVE}" == "INTERACTIVE" -a -n "${instalation_packages}" ]; then
        ask  "Would you like to install followig package\(s\): [ ${instalation_packages}]"
        if [[ "${YESNO}" == [Yy][Ee][Ss] ]]; then
            run "apt-get install --yes ${instalation_packages}"
        fi
    elif [ -n "${instalation_packages}" ]; then
        if [ "${FORCE_YES}" == "FORCE_YES" ]; then
            run "apt-get install --yes ${instalation_packages}"
        else
            echo -e "Following pakage(s) are not installed [ ${instalation_packages}]. ----- ERR\nExiting..."
            exit 1
        fi
    fi
    unset instalation_packages
}

. "${location}/dos_functions.sh"

if [ $(basename -- "$0") ==  "dos_check_packages.sh" ]; then
set -ex
check_packages "${package_list}"
fi