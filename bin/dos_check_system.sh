#!/bin/bash

location=$(dirname $0)

#Body of script which check what CPU are in use.
cpu_check() {
    case $(awk '/vendor_id/ {print $3}' /proc/cpuinfo|sort -u)  in
        GenuineIntel*)
            cpu_type="intel"
            cpu_virtualization_check "vmx"
            ;;
        AuthenticAMD*)
            cpu_type="amd"
            cpu_virtualization_check "svm"
            ;;
        *)
            echo -e "Unknown CPU vendor. ----- ERR\nExiting..."
            exit 1
            ;;
    esac
}

#Check if hardware virtualization disabled.
cpu_virtualization_check() {
    if $(grep -qom1 "${1}" /proc/cpuinfo); then
        echo -e "Hardware virtualization enabled in BIOS. ----- OK\n"
        echo  -e "Checking kernel module \"kvm_${cpu_type}\" loaded or not.\n"
        sleep 1
        kvm_kernel_check
    else
        echo -e "Hardware virtualization doesn't enabled. ----- ERR\nExiting..."
        exit 1
    fi
}

#Check if KVM kernel module lodaded according to detected CPU(AMD/INTEL).
kvm_kernel_check() {
    if $(lsmod|grep -qom1 "kvm_${cpu_type}"); then
        echo -e "Kernel module \"kvm_${cpu_type}\" loaded. ----- OK\n"
        echo  -e "Checking \"Nested Paging\" enabled or not.\n"
        nested_pagging_check
    else
        if [ ${INTERACTIVE} == "INTERACTIVE" ]; then
            ask "Would you like to load kvm_${cpu_type} module till the reboot?"
            if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                run "/sbin/modprobe kvm_${cpu_type}"
                check_exit "Something has happened while loading kernel module kvm_${cpu_type}."
            fi
        elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
            run "/sbin/modprobe kvm_${cpu_type}"
            check_exit "Something has happened while loading kernel module kvm_${cpu_type}."
        else
            echo -e "Kernel Module \"kvm_${cpu_type}\" isn't loaded. ----- ERR\nExiting..."
            exit 1
        fi
    fi
}

#Check whether nested pagging enabled of not.
nested_pagging_check() {
    if $(grep -q "^Y$" "/sys/module/kvm_${cpu_type}/parameters/nested"); then
        echo -e "Nested pagging is enabled. ----- OK\n"
        ip_filters
    else
        echo -e "Nested Pagging is not enabled. ----- ERR\nExiting..."
        exit 1
    fi
}

#Check whether bridge filtration rules enbled in kernel or not.
ip_filters() {
    ORIG_IFS="${IFS}"
    IFS=$'\n'
    for filter in $(sysctl -a 2>&1|grep -P "net.bridge.bridge-nf-call-(arp|ip|ip6)tables"); do
        if [ "${filter: -1}" == "1" ]; then
            echo -e "${filter:26: -4} filter is enabled"
            if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                ask "Would you like to permanently deactivate ${filter:26: -4} filter?"
                if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                    if ! $(grep -q "${filter:: -1}0" "/etc/sysctl.d/net-bridge-filters.conf"); then
                        echo "Filter ${filter:26: -4} will be disabled"
                            run "echo ${filter:: -1}0 >> /etc/sysctl.d/net-bridge-filters.conf"
                    else
                        echo -e "${filter:: -1}0 already in /etc/sysctl.d/net-bridge-filters.conf\n"
                    fi
                fi
            elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                if ! $(grep -q "${filter:: -1}0" "/etc/sysctl.d/net-bridge-filters.conf"); then
                    echo "Filter ${filter:26: -4} will be disabled"
                    run "echo ${filter:: -1}0 >> /etc/sysctl.d/net-bridge-filters.conf"
                    check_exit "Something has happened while addind ${filter:26: -4} to /etc/sysctl.d/net-bridge-filters.conf."
                else
                    echo -e "${filter:: -1}0 already in /etc/sysctl.d/net-bridge-filters.conf\n"
                    echo "Will apply changes in the end"
                fi
            fi
        else
            echo "Filter ${filter:26: -4} not enabled. ----- OK"
            disabled_filters+="${filter:26: -4}\n"
        fi
    done
    if [ -s /etc/sysctl.d/net-bridge-filters.conf ]&&[ $(echo -e "${disabled_filters}" |wc -l) -lt "4" ]; then
        echo -e "Applying changes to the kernel.\n"
        run "sysctl -p /etc/sysctl.d/net-bridge-filters.conf"
    fi
    IFS="${ORIG_IFS}"
}

. "${location}/dos_functions.sh"

if [ $(basename -- "$0") ==  "dos_check_system.sh" ]; then
    set -ex
    cpu_check
fi