#!/bin/bash

#Function for execution with/without SUDO
run() {
    if [ $(id -u) -eq 0 ]; then
        /bin/bash -c "${1}" > /dev/null
    else
        sudo /bin/bash -c "${1}" >/dev/null
    fi
}

#Function for checking exit code
check_exit() {
    if [ "${?}" -ne 0 ]; then
        echo -e "${1} ----- ERR\nExiting..."
        exit 1
    fi
}

#Function check whether user has sudo or run script as root.
get_pass() {
    if [ $(id -u) -eq 0 ]; then
        echo -e "You are running script with root permissions, be careful!\n"
    else
        read -sp "Please enter your SUDO password:" PASSWD
        sudo -S -l <<< "${PASSWD}" 2>&1 >/dev/null
        if [ "${?}" -ne 0 ]; then
            echo -e "Sudo password (${PASSWD}) is incorrect. ----- ERR\nExiting..."
            exit 1
        fi
    fi
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
                        echo -e "Couldn't get any package manager. ----- ERR\nExiting"
                        exit 1
                    fi
                fi
            else
                echo "Unknown Linux Distro! ----- ERR\nExiting..."
                exit 1
            fi
            ;;
    esac
}

usage() {
cat << EOF
Usage $0 [OPTIONS]...VALUE

########################################################################################################################################################################
# -H/-h (--help)                      - Show this help.                                                                                                                #
# -V    (--vebose)                    - Option that is increase verbosity level (bash -x).                                                                             #
# -I    (--interactive)               - Option makes script to ask questions.                                                                                          #
# -A    (--pgsql-auth-trust)          - Change auth method to trust insteacd of peer (required --pgsql).                                                               #
# -P    (--pgsql)                     - Use pgsql db instead of sqlite3.                                                                                               #
# -F    (--force-yes)                 - Yes to all additional changes (required SUDO PASSWD or run by root).                                                           #
# -U    (--pg-user)                   - User for devops database (required --pgsql) DEFAULT value "fuel_devops".                                                       #
# -p    (--pg_password)               - User password for potgreSQL (required --pgsql) DEFAULT value "fuel_devops" .                                                   #
# -D    (--pg_database)               - Name of PostgreSQL database (required --pgsql) DEFAULT value "fuel_devops".                                                    #
# -S    (--sqlite_database)           - Path to the sqlite database with the name (e.g. /path/somewhere/database_name) DEFAULT $HOME/devops_${devops_version}.sqlite3. #
########################################################################################################################################################################
EOF
}

opts() {
    opt=$(getopt -o HhVIAPFU:p:D:S: --long "${longopts}" -n "$0" -- "$@")
    if [ $? -ne 0 ]; then
        usage
        exit 1
    elif [[ $@ =~ ^\-\-$ ]]; then
#    elif [[ ! $@ =~ ^\-.+ ]] || [[ $@ =~ ^\-\-$ ]]; then
        usage
        exit 0
#    elif [[ ! $@ =~ ^\-.+ ]]; then
    fi
    eval set -- "$opt"
    while true; do
        case "${1}" in
            -H|-h|--help)
                usage
                shift
                exit 0
                ;;
            -V|--verbose )
                VERBOSE="VERBOSE"
                echo "Verbose mode ON"
                set -x
                shift
                ;;
            -I|--interactive )
                INTERACTIVE="INTERACTIVE"
                shift
                echo "Interactive mode ON"
                ;;
            -F|--force-yes)
                FORCE_YES="FORCE_YES"
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
            -U|--pg-user)
                PG_USER="${2}"
                shift 2
                ;;
            -D|--pg-database)
                PG_DATABASE="${2}"
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
            -- )
                shift
                break
                ;;
            * )
                break
                ;;
        esac
    done

    if  [ "${INTERACTIVE}" == "INTERACTIVE" -a "${FORCE_YES}" == "FORCE_YES" ]; then
        echo -e "Impossible to use both interactive and force-yes modes at the same time. ----- ERR\nExiting..."
        exit 1
    fi

    if [ ! -z "${PGSQL}" -a ! -z "${SQLITE_DB_PATH}" ]; then
        echo "Impossible to use both database engines at the same time. ----- ERR\nExiting..."
        exit 1
    fi

    if ! [ "${PG_TRUST}" != "PG_TRUST" ]||[ "${PG_USER}" != "" ]||[ "${PG_DATABASE}" != "" ]||[ "${PG_PASS}" != "" ]&&[ "${PGSQL}" != "PGSQL" ]; then
        echo -e "PGSQL option is not enabled. ----- ERR\nExiting."
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
