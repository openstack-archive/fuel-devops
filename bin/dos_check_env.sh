#!/bin/bash

set -e

longopts="help,verbose,interactive,pgsql-auth-trust,force-yes,pgsql,pg-user:,pg-password:,pg-database:,sqlite-database:"
package_list="git,libyaml-dev,libffi-dev,python-dev,python-pip,qemu,libvirt-bin,libvirt-dev,vlan,bridge-utils,genisoimage"
location=$(dirname $0)

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
# -p    (--pg-password)               - User password for potgreSQL (required --pgsql) DEFAULT value "fuel_devops" .                                                   #
# -D    (--pg-database)               - Name of PostgreSQL database (required --pgsql) DEFAULT value "fuel_devops".                                                    #
# -S    (--sqlite-database)           - Path to the sqlite database with the name (e.g. /path/somewhere/database_name) DEFAULT $HOME/devops.sqlite3.                   #
########################################################################################################################################################################
EOF
}


. "${location}/dos_functions.sh"
. "${location}/dos_check_system.sh"
. "${location}/dos_check_packages.sh"
. "${location}/dos_check_db.sh"

opts $@
cpu_check
check_packages "${package_list}"
db_opts
install_func