#!/bin/bash
#    Copyright 2013 - 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

set -ex

package_list="git,libyaml-dev,libffi-dev,python-dev,python-pip,qemu,libvirt-bin,libvirt-dev,vlan,bridge-utils,genisoimage"
longopts="interactive,help,no-venv,clean-install,pgsql-auth-trust,force-yes,pgsql,pg-user:,pg-password:,pg-database:,sqlite-database:,install-repo-requirements:,venv-name:,devops-tag:"
venv_packs="python-virtualenv,libpq-dev,libgmp-dev,pkg-config"



#Description of all possible options
usage() {
cat << EOF
Usage $0 [OPTIONS]...VALUE

########################################################################################################################################################################
# -I    (--interactive)               - Option makes script to ask questions.                                                                                          #
# -H/-h (--help)                      - Show this help.                                                                                                                #
# -E    (--no-venv)                   - Install devops into the system (without venv) OPTIONAL.                                                                        #
# -C    (--clean-install)             - Remove all previous installed devops packages/databases.                                                                       #
# -A    (--pgsql-auth-trust)          - Change auth method to trust insteacd of peer (required --pgsql).                                                               #
# -P    (--pgsql)                     - Use pgsql db instead of sqlite3.                                                                                               #
# -U    (--pg-user)                   - User for devops database (required --pgsql) DEFAULT value "fuel_devops".                                                       #
# -p    (--pg_password)               - User password for potgreSQL (required --pgsql) DEFAULT value "fuel_devops" .                                                   #
# -D    (--pg_database)               - Name of PostgreSQL database (required --pgsql) DEFAULT value "fuel_devops".                                                    #
# -S    (--sqlite_database)           - Path to the sqlite database with the name (e.g. /path/somewhere/database_name) DEFAULT $HOME/devops_${DEVOPS_TAG}.sqlite3.     #
# -R    (--install-repo-requirements) - URL to the file with requirements for additional packages (for now fuel-qa only) NOT working for now.                          #
# -N    (--venv-name)                 - Name with path to python venv (example: ~/devops_venv) required.                                                               #
# -T    (--devops-tag)                - Tag that will be used as source of devopsa package DEFAULT is master branch without tag.                                       #
# -F    (--force-yes)                 - Yes to all additional changes (required SUDO PASSWD or run by root).                                                           #
########################################################################################################################################################################
EOF
}

#Options parser function.
opts() {
    opt=$(getopt -o IHhECAPFU:p:D:S:R:N:T: --long "${longopts}" -n "$0" -- "$@")
    if [ $? -ne 0 ]; then
        usage
        exit 1
    elif [[ ! $@ =~ ^\-.+ ]] || [[  $@ =~ ^\-\-$ ]]; then
        usage
        exit 0
    fi

    eval set -- "$opt"

    while true; do
        case "${1}" in
            -N|--venv-name)
                VENV_NAME="${2}"
                shift 2
                ;;
            -I|--interactive )
                INTERACTIVE="INTERACTIVE"
                shift
                echo "Interactive mode ON"
                ;;
            -H|-h|--help)
                usage
                shift
                exit 0
                ;;
            -F|--force-yes)
                FORCE_YES="FORCE_YES"
                shift
                ;;
            -E|--no-venv)
                NO_VENV="NO_VENV"
                shift
                ;;
            -P|--pgsql)
                PGSQL="PGSQL"
                shift
                ;;
            -A|--pgsql-auth-trust)
                PG_TRUST="PG_TRUST"
                shift
                ;;
            -C|--clean-install)
                CLEAN_INSTALL="CLEAN_INSTALL"
                shift
                ;;
            -U|--pg-user)
                PG_USER="${2}"
                shift 2
                ;;
            -D|--pg-database)
                PG_DATABASE="${2}"
                shift 2
                ;;
            -T|--devops-tag)
                DEVOPS_TAG="${2}"
                shift 2
                ;;
            -p|--pg-password)
                PG_PASS="${2}"
                shift 2
                ;;
            -S|--sqlite-database)
                SQLITE_DB_PATH=$(readlink -f "${2}".sqlite3)
                shift 2
                ;;
            -L|--install-repo-requirements)
                REQ_LIST="${2}"
                shift 2
                ;;
            -- )
                shift
                break
                ;;
            * )
                break
                ;;
        esac
    done

    if [ "${INTERACTIVE}" == "INTERACTIVE" -a "${FORCE_YES}" == "FORCE_YES" ]; then
        echo -e "Impossible to use both interactive and force mods at the same time.\nExiting..."
        sleep 1
        exit 1
    fi

    if [ ! -z "${NO_VENV}" -a ! -z "${VENV_NAME}" ]; then
        echo "Impossible to use both --venv-name and --no-venv at the same time.\nExiting..."
        sleep 1
        exit 1
    fi
    if [ -z "${NO_VENV}" -a -z "${VENV_NAME}" ]; then
        echo "At least --venv-name should be set"
        sleep 1
        exit 1
#            echo "Venv-name was not set using default ${VENV_NAME:=$(readlink -f ~/fuel-devops)}"
    fi

    if [ ! -z "${PGSQL}" -a ! -z "${SQLITE_DB_PATH}" ]; then
        echo "Impossible to use both database engines at the same time.\nExiting..."
        sleep 1
        exit 1
    fi

    if ! [ "x${PG_TRUST}" != "xPG_TRUST" ]||[ "${PG_USER}" != "" ]||[ "${PG_DATABASE}" != "" ]||[ "${PG_PASS}" != "" ]&&[ "x${PGSQL}" != "xPGSQL" ]; then
    echo -e "PGSQL option is not enabled.\nExiting."
    sleep 1
    exit 1
    fi


}


#Function determines whether user root or have SUDO permissions
get_pass() {
    if [ $(id -u) -eq 0 ]; then
        echo -e "You are running script with root permissions, be careful!\n"
    else
        read -sp "Please enter your SUDO password:" PASSWD
        sudo -S -l <<< "${PASSWD}" 2>&1 >/dev/null
        if [ "${?}" -ne 0 ]; then
            echo -e "Sudo password (${PASSWD}) is incorrect.\nExiting..."
            exit 1
        fi
    fi
}

#Function for execution with/without SUDO
run() {
    if [ $(id -u) -eq 0 ]; then
        /bin/bash -c "${1}" 2>&1 > /dev/null
    else
        sudo /bin/bash -c "${1}" 2>&1 >/dev/null
    fi
}

check_exit() {
    if [ "${?}" -ne 0 ]; then
        echo -e "${1}\nExiting..."
        sleep 2
        exit 1
    fi
}

#Question function which will ask questions.
ask() {
    read -p "${1} [YES/no]: " YESNO
    while ! $(grep -Eqi '(yes|no)' <<< "${YESNO}"); do
        echo "Incorrect input please use only [YES/no]: "
        sleep 1
        read -p "${1} [YES/no]: " YESNO
    done
}


#Determines which Linux Distro is on the host.
where_am_i() {
    case $(lsb_release -is) in
        Gentoo*)
            echo -e "Gentoo Linux Detected.\n"
            pkg_mng=$(which emerge)
            ;;
        Ubuntu*)
            echo -e "Ubuntu Linux detected.\n"
            pkg_mng=$(which apt-get)
            if [ -z "${pkg_mng}" ]; then
                alt_pkg_mng=$(which dpkg)
            fi
            ;;
        Debian*)
            echo -e "Debian Linux detected.\n"
            pkg_mng=$(which apt-get)
            if [ -z "${pkg_mng}" ]; then
                alt_pkg_mng=$(which dpkg)
            fi
            ;;
        Fedora*)
            echo -e "Fedora Linux detected.\n"
            pkg_mng=$(which yum)
            if [ -z "${pkg_mng}" ]; then
                alt_pkg_mng=$(which rpm)
            fi
            ;;
        SUSE*)
            echo -e "Suse Linux detected.\n"
            pkg_mng=$(which zypper)
            if [ -z "${pkg_mng}" ]; then
                alt_pkg_mng=$(which rpm)
            fi
            ;;
        *)
            if [ -s /etc/redhat-release ]; then
                if $(grep -qo "el7" /proc/version); then
                    echo -e "CentOS 7 detected.\n"
                    pkg_mng=$(which yum)
                    if [ -z "${pkg_mng}" ]; then
                        alt_pkg_mng=$(which rpm)
                    fi
                elif $(grep -qo "el6" /proc/version); then
                    echo -e "CentOS 6 detected.\n"
                    pkg_mng=$(which yum)
                    if [ -z "${pkg_mng}" ]; then
                        alt_pkg_mng=$(which rpm)
                    fi
                else
                    echo "Unknown RedHat distro."
                    pkg_mng=$(which yum)
                    if [ -z "${pkg_mng}" ]; then
                        alt_pkg_mng=$(which rpm)
                    fi
                    if [ -z "${pkg_mng}" -o -z "${alt_pkg_mng}" ]; then
                        echo -e "Couldn't get any package manager.\nExiting"
                        exit 1
                    fi
                fi
            else
                echo "Unknown Linux Distro!\nExiting..."
                exit 1
            fi
            ;;
    esac
}

create_db_user() {
    if [[ "$(psql -U postgres -tAc 'SELECT 1 FROM pg_roles WHERE rolname='\'${PG_USER}\''')" == "1" ]]; then
        echo -e "User with the name ${PG_USER} already exists.\nExiting..."
        exit 1
    else
        psql -U postgres -c 'CREATE ROLE '${PG_USER}' PASSWORD '\'${PG_PASS}\'' LOGIN'
    fi
    if ! $(createdb -U postgres ${PG_DATABASE} -O "${PG_USER}"); then
        echo "database with the name \"${PG_DATABASE}\" already exists.\nExiting..."
        exit 1
    fi
}

#Definition of options for install_func().
def_opts() {
    if [ -z "${DEVOPS_TAG}" ]; then
        echo "Devops tag doesn't set using master branch ${DEVOPS_TAG:=master}"
    fi

    if [ "${PGSQL}" == "PGSQL" ]; then
        if $(dpkg -l|grep -q postgresql); then
            echo "PostgreSQL package installed"
            sleep 1
        else
            if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                ask "PostgreSQL wasn't installed, would you like to install it?"
                if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                    echo "Installing PostgreSQL..."
                    sleep 1
                    run "apt-get install postgresql --yes"
                    check_exit "Something has happened, PostgreSQL wasn't installed."
                    echo -e "Installation of PostgreSQL successfull.\n"
                else
                    echo -e "You've chosen PostgreSQL as backend.\n"\
"PostgreSQL is not installed and your answer is "NO".\nExiting..."
                    sleep 1
                    exit 2
                fi
            elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                echo "PostgreSQL wasn't installed.\nInstalling PostgreSQL..."
                run "apt-get install postgresql --yes"
            else
                echo -e "PostgreSQL is not installed.\nExiting..."
                exit 1
            fi
        fi

        if [ "${PG_TRUST}" == "PG_TRUST" ]; then
            echo "Replacing peer auth to trust"
            sleep 2
            run "sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf"
            check_exit "Can't change peer auth to trust in PostgreSQL settings."
            echo "Restarting PostgreSQL service..."
            run "service postgresql restart >>/dev/null"
            check_exit "PostgreSQL wasn't restarted properly."
        else
            if [ "${FORCE_YES}" == "FORCE_YES" ]; then
                echo "Replacing peer auth to trust"
                run "sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf"
                check_exit "Can't change peer auth to trust in PostgreSQL settings."
                echo "Restarting PostgreSQL service..."
                sleep 1
                run "service postgresql restart >>/dev/null"
                check_exit "PostgreSQL wasn't restarted properly."
            elif (run "grep -q peer /etc/postgresql/9.*/main/pg_hba.conf"); then
            ask "Would you like to change auth method from "peer" to "trust"?"
                if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                    echo "Replacing peer auth to trust"
                    run "sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf"
                    check_exit "Can't change peer auth to trust in PostgreSQL settings."
                    echo "Restarting PostgreSQL service..."
                    run "service postgresql restart >>/dev/null"
                else
                    echo -e "Auth method is peer can't be used.\nExiting..."
                fi
            fi
        fi
        if [ -z "${PG_USER}" ]; then
            echo "Postgresql database user wasn't set using default ${PG_USER:=fuel_devops}"
        fi

        if [ -z "${PG_PASS}" ]; then
            echo "Password for user ${PG_USER} wasn't set using default ${PG_PASS:=fuel_devops}"
        fi
        if [ -z "${PG_DATABASE}" ];then
            echo "Name for Postgresql database wasn't set using default ${PG_DATABASE:=fuel_devops}"
        fi

        if [ "${CLEAN_INSTALL}" == "CLEAN_INSTALL" ]; then
            install_func
        fi
    else
        if [ -z "${SQLITE_DB_PATH}" ]; then
            echo "Sqlite database path wasn't set using default ${SQLITE_DB_PATH:=$(readlink -f ~/devops_${DEVOPS_TAG}.sqlite3)}"
            if [ "${CLEAN_INSTALL}" == "CLEAN_INSTALL" ]; then
                install_func
            elif [ -s "${SQLITE_DB_PATH}" ]; then
            echo -e "SQLite database (${SQLITE_DB_PATH}) already exists.\nExiting..."
            sleep 1
            exit 1
            fi
        fi
    fi

}

#Check if hardware virtualization disabled.
cpu_virtualization_check() {
    if $(grep -qom1 "${1}" /proc/cpuinfo); then
        echo -e "Hardware virtualization enabled in BIOS.\n"
        echo  -e "Checking kernel module \"kvm_${cpu_type}\" loaded or not.\n"
        sleep 1
        kvm_kernel_check
    else
        echo -e "Hardware virtualization doesn't enabled.\nExiting..."
        sleep 1
        exit 1
    fi
}

#Check if KVM kernel module lodaded according to detected CPU(AMD/INTEL).
kvm_kernel_check() {
    if $(lsmod|grep -qom1 "kvm_${cpu_type}"); then
        echo -e "Kernel module \"kvm_${cpu_type}\" loaded.\n"
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
            echo "TBD force-yes for kvm_kernel_check"
            run "/sbin/modprobe kvm_${cpu_type}"
            check_exit "Something has happened while loading kernel module kvm_${cpu_type}."
        else
            echo -e "Kernel Module \"kvm_${cpu_type}\" isn't loaded.\nExiting..."
            sleep 1
            exit 1
        fi
    fi
}

#Check whether nested pagging enabled of not.
nested_pagging_check() {
    if $(grep -q "^Y$" "/sys/module/kvm_${cpu_type}/parameters/nested"); then
        echo -e "Nested pagging is enabled.\n"
        ip_filters
    else
        echo -e "Nested Pagging is not enabled.\nExiting..."
        sleep 1
        exit 1
    fi
}

#Check whether bridge filtration rules enbled in kernel or not.
ip_filters() {
    ORIG_IFS="${IFS}"
    IFS=$'\n'
    for filter in $(sysctl -a 2>&1|grep -P "net.bridge.bridge-nf-call-(arp|ip|ip6)tables"); do
        if [ "${filter: -1}" == "1" ]; then
            echo "${filter:26: -4} filter is enabled"
#Check if interactive mode on.
            if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                ask "Would you like to permanently deactivate ${filter:26: -4} filter?"
                if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                    if ! $(grep -q "${filter:: -1}0" "/etc/sysctl.d/net-bridge-filters.conf"); then
                        echo "Filter ${filter:26: -4} will be disabled"
                            run "echo ${filter:: -1}0 >> /etc/sysctl.d/net-bridge-filters.conf"
                    else
                        echo -e "${filter:: -1}0 already in /etc/sysctl.d/net-bridge-filters.conf\n"
#                        echo "Will apply changes in the end"
                    fi
                fi
            elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                echo "TBD for force ip_filters"
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
            echo "filter ${filter:26 -4} not enabled"
            disabled_filters+="${filter:26: -4}\n"
        fi
    done
    if [ -s /etc/sysctl.d/net-bridge-filters.conf ]&&[ $(echo -e "${disabled_filters}" |wc -l) -lt "4" ]; then
        echo -e "Applying changes to the kernel.\n"
        run "sysctl -p /etc/sysctl.d/net-bridge-filters.conf"
    fi
    IFS="${ORIG_IFS}"
}

#Check if all necessary packages are installed.
check_packages() {
    OLD_IFS="${IFS}"
    IFS=","
    if [ "${N}" ==  "" ]; then
    run "apt-get update"
    N+="1"
    fi
    for package in ${1}; do

#        where_am_i
#        case 

        if $(apt-cache policy ${package}|grep -q "Installed: (none)"); then
            echo "Package ${package} doesn't installed"
            sleep 1
            instalation_packages+="${package} "
        else
            echo -e "Package ${package} is already installed.\n"
            sleep 1
        fi
    done
    if [ "${INTERACTIVE}" == "INTERACTIVE" -a -n "${instalation_packages}" ]; then
        ask  "Would you like to install followig package\(s\): [ ${instalation_packages}]"
        if [[ "${YESNO}" == [Yy][Ee][Ss] ]]; then
            run "apt-get install --yes ${instalation_packages}"
        fi
    elif [ -n "${instalation_packages}" ]; then
        if [ "${FORCE_YES}" == "FORCE_YES" ]; then
            echo "TBD force-yes for check_packages"
            run "apt-get install --yes ${instalation_packages}"
            check_exit "Something has happened while installing necessary packages\n[ ${instalation_packages}]."
        else
            echo -e "Following pakage\(s\) are not installed [ ${instalation_packages}].\nExiting..."
            sleep 1
            exit 1
        fi
    fi
    IFS="${OLD_IFS}"
}

#Body of script which check what CPU are in use.
cpu_check() {
    case $(awk '/vendor_id/ {print $3}' /proc/cpuinfo|sort -u)  in
        GenuineIntel*)
            cpu_type="intel"
            cpu_virtualization_check "vmx"
            check_packages "${package_list}"
            unset instalation_packages
            ;;
        AuthenticAMD*)
            cpu_type="amd"
            cpu_virtualization_check "svm"
            check_packages "${package_list}"
            unset instalation_packages
            ;;
        *)
            echo -e "Unknown CPU vendor.\nExiting..."
            sleep 2
            exit 1
            ;;
    esac
}


devops_env_vars() {
    if [ ! -z "${SQLITE_DB_PATH}" ]; then
        echo "export DEVOPS_DB_ENGINE='django.db.backends.sqlite3'" >> "${1}"
        echo "export DEVOPS_DB_NAME=\"${SQLITE_DB_PATH}\"" >> "${1}"
# Ability to unset custom variables to avoid confusion with variables in case of manual check of job results.
        if [[ "${1}" == *"/bin/activate" ]]; then
          sed -i "s/\(unset VIRTUAL_ENV\)/\1 DEVOPS_DB_ENGINE DEVOPS_DB_NAME/" "${1}"
        fi
    else
        echo "export DEVOPS_DB_ENGINE='django.db.backends.postgresql_psycopg2'" >> "${1}"
        echo "export DEVOPS_DB_NAME=\"${PG_DATABASE}\"" >> "${1}"
        echo "export DEVOPS_DB_USER=\"${PG_USER}\"" >> "${1}"
        echo "export DEVOPS_DB_PASSWORD=\"${PG_PASS}\"" >> "${1}"
# Ability to unset custom variables to avoid confusion with variables in case of manual check of job results.
        if [[ "${1}" == *"/bin/activate" ]]; then
            sed -i "s/\(unset VIRTUAL_ENV\)/\1 DEVOPS_DB_ENGINE DEVOPS_DB_NAME DEVOPS_DB_PASSWORD DEVOPS_DB_USER/" "${1}"
        fi
    fi
    source "${1}"
    /bin/rm -rf ./fuel-devops-source
    git clone https://github.com/openstack/fuel-devops ./fuel-devops-source
    check_exit "Something has happened while cloning fuel-devops."
    cd ./fuel-devops-source
    if [ "${DEVOPS_TAG}" == "master" ]; then
        pip install ./ --upgrade
        ./manage.py migrate
    else
        git checkout tags/"${DEVOPS_TAG}"
        pip install ./ --upgrade
        django-admin.py syncdb --settings=devops.settings
        django-admin.py migrate devops --settings=devops.settings
    fi
}


#Function which will install Devops and if set install-repo-requirements(TBD)
install_func() {
    if [ "${CLEAN_INSTALL}" == "CLEAN_INSTALL" ]; then
        if [ ! -z "${PGSQL}" ]; then
            if [ ! -z "${PG_DATABASE}" ] && $(psql -Upostgres -lqAt|grep -Eq "^${PG_DATABASE}\|"); then
                echo -e "Dropping existing database with the name \"${PG_DATABASE}\"."
                dropdb -U postgres "${PG_DATABASE}" 2>&1 >/dev/null
                check_exit "Database wasn\'t terminated."
            fi
            if [[ "$(psql -U postgres -tAc 'SELECT 1 FROM pg_roles WHERE rolname='\'${PG_USER}\''')" == "1" ]]; then
                echo -e "User with the name ${PG_USER} exists.\nTerminating ${PG_USER}..."
                dropuser -U postgres "${PG_USER}"
                check_exit "User wasn\'t terminated."
            fi
        else
            /bin/rm -f "${SQLITE_DB_PATH}"
        fi

        if [ -n "${VENV_NAME}" ]; then
            source "${VENV_NAME}/bin/activate"
            if $(pip freeze|grep -q fuel-devops);then
                pip uninstall -y fuel-devops
                check_exit "Something has hapenned while uninstalling devops"
            else
                echo -e "No fuel-devops was found, continue with the fresh installation."
            fi
            deactivate
        elif [ ! -z "${NO_VEVN}" ]; then
            if $(pip freeze|grep -q fuel-devops); then
                run "pip uninstall -y fuel-devops"
                check_exit "Something has hapenned while uninstalling devops"
            else
                echo -e "No fuel-devops was found, continue with the fresh installation."
            fi
        fi
    fi

    if [ -n "${VENV_NAME}" ]; then
        check_packages "${venv_packs}"
        unset instalation_packages
        if [ ! -z "${PGSQL}" ]; then
            create_db_user
        fi
        virtualenv "${VENV_NAME}"
        cd "${VENV_NAME}"
        devops_env_vars "${VENV_NAME}/bin/activate"
    else
        if [ ! -z "${PGSQL}" ]; then
            create_db_user
        fi
        devops_env_vars "~/.bashrc_devops"
    fi
}


opts $@
if [[ "${PASSWD}" == "" ]]; then
    get_pass
fi
cpu_check
def_opts
if [ -z ${CLEAN_INSTALL} ]; then
    install_func
fi