#!/bin/bash 

location=$(dirname $0)

db_opts() {
    if [ "${PGSQL}" == "PGSQL" ]; then
        if $(dpkg -l|grep -q postgresql); then
            if [ "${VERBOSE}" == "VERBOSE" ]; then
                echo "PostgreSQL package installed. ----- OK"
                sleep 1
            fi
        else
            if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                ask "PostgreSQL wasn't installed, would you like to install it?"
                if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                    echo "Installing PostgreSQL..."
                    run "apt-get install postgresql --yes"
                    echo -e "Installation of PostgreSQL successfull. ----- OK\n"

                else
                    echo -e "You've chosen PostgreSQL as backend.\n"\
"PostgreSQL is not installed and your answer is "NO".\nExiting..."
                    exit 2
                fi
            elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                echo "PostgreSQL wasn't installed.\nInstalling PostgreSQL..."
                run "apt-get install postgresql --yes"
                echo -e "Installation of PostgreSQL successfull. ----- OK\n"
            else
                echo -e "PostgreSQL is not installed. ----- ERR\nExiting..."
                exit 1
            fi
            if $(apt-cache policy libpq-dev|grep -q "Installed: (none)"); then
                if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                    ask "libpq-dev wasn't installed, would you like to install it?"
                    if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                        echo "Installing \"libpq-dev\"..."
                        run "apt-get install libpq-dev --yes"
                        echo -e "Installation of libpq-dev successfull. ----- OK\n"
                    else
                        echo -e "You've chosen PostgreSQL as backend.\n"\
"libpq-dev is not installed and your answer is "NO" devops cannot interact with postgreSQL.\nExiting..."
                    exit 2
                    fi
                elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                    echo "\"libpq-dev\" wasn't installed.\nInstalling \"libpq-dev\"..."
                    run "apt-get install libpq-dev --yes"
                    echo -e "Installation of libpq-dev successfull. ----- OK\n"
                else
                    echo -e "\"libpq-dev\" is not installed. ----- ERR\nExiting..."
                    exit 1
                fi
            fi
        fi
        if [ "${PG_TRUST}" == "PG_TRUST" ]; then
            echo "Replacing peer auth to trust"
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
                fi
            else
                echo -e "Auth method \"peer\" can't be used. ----- ERR\nExiting..."
                exit 1
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
    else
        if [ -z "${SQLITE_DB_PATH}" ]; then
            echo "SQLite database path wasn't set using default ${SQLITE_DB_PATH:=$(readlink -f ~/devops_$(dos.py version).sqlite3)}"
        fi
        if [ -s "${SQLITE_DB_PATH}" ]; then
            if [ "${INTERACTIVE}" == "INTERACTIVE" -a -s "${SQLITE_DB_PATH}" ]; then
                ask "SQLite database \"${SQLITE_DB_PATH}\" already exist would you like to rewrite it with the new content?"
                if [[ ${YESNO} == [Yy][Ee][sS] ]]; then
                    echo -e "SQLite database wil be rewritten"
                fi
            elif [ "${FORCE_YES}" == "FORCE_YES"]; then
                echo -e "SQLite database exists but force mode set so it will be rewritten"
            else
                echo -e "SQLite database \"${SQLITE_DB_PATH}\" already exists. ----- ERR\nExiting..."
                exit 1
            fi
        fi
    fi
}


create_db_user() {
    if [[ "$(psql -U postgres -tAc 'SELECT 1 FROM pg_roles WHERE rolname='\'${PG_USER}\''')" == "1" ]]; then
        echo -e "User with the name ${PG_USER} already exists. ----- ERR\nExiting..."
        exit 1
    else
        psql -U postgres -c 'CREATE ROLE '${PG_USER}' PASSWORD '\'${PG_PASS}\'' LOGIN'
    fi
}

create_db() {
    if ! $(createdb -U postgres ${PG_DATABASE} -O "${PG_USER}"); then
        echo "Database with the name \"${PG_DATABASE}\" already exists. ----- ERR\nExiting..."
        exit 1
    fi
}


env_check() {
    if [ ! -z ${VIRTUAL_ENV} ]; then
        echo -e "Adding necessary ENV variables into \"${VIRTUAL_ENV}/bin/activate\""
        devops_env_vars "${VIRTUAL_ENV}/bin/activate"
    else
        echo -e "Adding necessary ENV variables into \"$(readlink -f ~/.bashrc_devops)\""
        devops_env_vars ~/.bashrc_devops
    fi
}

devops_env_vars() {
    if [ ! -z "${SQLITE_DB_PATH}" ]; then
        echo "Adding \"export DEVOPS_DB_ENGINE='django.db.backends.sqlite3'\" to ${1} ----- OK"
        echo "export DEVOPS_DB_ENGINE='django.db.backends.sqlite3'" >> "${1}"
        echo "Adding \"export DEVOPS_DB_NAME=\"${SQLITE_DB_PATH}\"\" to ${1} ----- OK"
        echo "export DEVOPS_DB_NAME=\"${SQLITE_DB_PATH}\"" >> "${1}"
        if [ ! -z "${VIRTUAL_ENV}" ]; then
            echo "Adding ability for VIRTUAL_ENV to remove DB variables with deactivate function ----- OK"
            sed -i "s/\(unset VIRTUAL_ENV\)/\1 DEVOPS_DB_ENGINE DEVOPS_DB_NAME/" "${1}"
        fi
    else
        echo "Adding \"export DEVOPS_DB_ENGINE='django.db.backends.postgresql_psycopg2'\" to ${1} ----- OK"
        echo "export DEVOPS_DB_ENGINE='django.db.backends.postgresql_psycopg2'" >> "${1}"
        echo "Adding \"export DEVOPS_DB_NAME=\"${PG_DATABASE}\"\" to ${1} ----- OK"
        echo "export DEVOPS_DB_NAME=\"${PG_DATABASE}\"" >> "${1}"
        echo "Adding \"export DEVOPS_DB_USER=\"${PG_USER}\"\" to ${1} ----- OK"
        echo "export DEVOPS_DB_USER=\"${PG_USER}\"" >> "${1}"
        echo "Adding \"export DEVOPS_DB_PASSWORD=\"${PG_PASS}\"\" to ${1} ----- OK"
        echo "export DEVOPS_DB_PASSWORD=\"${PG_PASS}\"" >> "${1}"
        if [ ! -z "${VIRTUAL_ENV}" ]; then
            echo "Adding ability for VIRTUAL_ENV to remove DB variables with deactivate function ----- OK"
            sed -i "s/\(unset VIRTUAL_ENV\)/\1 DEVOPS_DB_ENGINE DEVOPS_DB_NAME DEVOPS_DB_PASSWORD DEVOPS_DB_USER/" "${1}"
        fi
    fi
    source "${1}"
    dos-manage.py migrate
    echo "Please activate virtual env or run  \"source ~/.bashrc_devops\" (in case if fuel-devops was installed into system) so database variables get in your user env and you could use dos.py"
}

alter_db_owner() {
    echo -e "Creating user \"${PG_USER}\"..."
    psql -U postgres -c 'CREATE ROLE '${PG_USER}' PASSWORD '\'${PG_PASS}\'' LOGIN'
    echo -e "Making user \"${PG_USER}\" owner of \"${PG_DATABASE}\""
    psql -U postgres -c "ALTER DATABASE ${PG_DATABASE} OWNER TO ${PG_USER}"
}

drop_db() {
    echo -e "Dropping database \"${PG_DATABASE}\"..."
    dropdb -U "${PG_USER}" "${PG_DATABASE}" 2>&1 >/dev/null
    check_exit "Something has happened while terminating database \"${PG_DATABASE}\"."
}

drop_db_user() {
    echo -e "Dropping user \"${PG_USER}\""
    dropuser -U postgres "${PG_USER}"
    check_exit "Something has happened while terminating \"${PG_USER}\"."
}



install_func() {
    if [ ! -z "${PGSQL}" ]; then
        if [ ! -z "${PG_DATABASE}" ] && $(psql -Upostgres -lqAt|grep -Eq "^${PG_DATABASE}\|"); then
            if [[ "$(psql -U postgres -tAc 'SELECT 1 FROM pg_roles WHERE rolname='\'${PG_USER}\''')" == "1" ]]; then
                echo -e "Database \"${PG_DATABASE}\" and user \" ${PG_USER}\" exists. ----- OK"
                if [ $(psql -U ${PG_USER} -tc "select datdba from pg_database where datname='${PG_DATABASE}';") == $(psql -U ${PG_USER} -tc "select usesysid from  pg_user where usename='${PG_USER}';") ]; then
                    echo -e "User \"${PG_USER}\" is owner of \"${PG_DATABASE}\""
                    if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                        ask "Would you like to re-create database and user?"
                        if [[ "${YESNO}" == [Yy][Ee][sS] ]]; then
                            drop_db
                            drop_db_user
                            echo -e "Creating user \"${PG_USER}\" and database \"${PG_DATABASE}\"."
                            create_db_user
                            create_db
                        fi
                    elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                        drop_db
                        drop_db_user
                        echo -e "Creating user \"${PG_USER}\" and database \"${PG_DATABASE}\"."
                        create_db_user
                        create_db
                    else
                        echo -e "User \"${PG_USER}\" is owner of \"${PG_DATABASE}\" continue checking. ----- OK"
                    fi
                else
                    echo -e "User \"${PG_USER}\" is not owner of database \"${PG_DATABASE}\" cannot continue configuration of database. ----- ERR\nExiting..."
                    exit 1
                fi
            else
                echo -e "User with the name \"${PG_USER}\" doesn't exist."
                if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                    ask "Would you like to create user \"${PG_USER}\" and make it owner of \"${PG_DATABASE}\"?"
                    if [[ "${YESNO}" == [Yy][Ee][sS] ]]; then
                        alter_db_owner
                    fi
                elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                    alter_db_owner
                else
                    echo -e "User doesn't exist. ----- ERR\nExiting..."
                    exit 1
                fi
            fi
        else
            if [[ "$(psql -U postgres -tAc 'SELECT 1 FROM pg_roles WHERE rolname='\'${PG_USER}\''')" == "1" ]]; then
                if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                    ask "User \"${PG_USER}\" already exist, would you like to create Database \"${PG_DATABASE}\" and set owner to \"${PG_USER}\"?"
                    if [[ "${YESNO}" == [Yy][Ee][sS] ]]; then
                        echo -e "Creating database \"${PG_DATABASE}\""
                        create_db
                    fi
                elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                    echo -e "Creating database \"${PG_DATABASE}\""
                    create_db
                else
                    echo -e "User \"${PG_USER}\" already exist, but database \"${PG_DATABASE}\" doesn't exist. ----- ERR\nExiting..."
                    exit 1
                fi
            else
                if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
                    ask "No user and database were found, would you like to create them?"
                    if [[ "${YESNO}" == [Yy][Ee][sS] ]]; then
                        echo -e "Creating database \"${PG_DATABASE}\" and user \"${PG_USER}\""
                        create_db_user
                        create_db
                    fi
                elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
                    echo -e "Creating database \"${PG_DATABASE}\" and user \"${PG_USER}\""
                    create_db_user
                    create_db
                else
                    echo -e "No database \"${PG_DATABASE}\" and user \"${PG_USER}\" were found. ----- ERR\nExiting..."
                    exit 1
                fi
            fi
        fi
        if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
            ask "Would you like to add database variables into env variables?"
            if [[ "${YESNO}" == [Yy][Ee][sS] ]]; then
                env_check
            fi
        elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
            env_check
        else
            echo "Neither \"interacitve\" nor \"force-yes\" modes were set check is successfully complete without any changes to system. ----- OK"
            exit 0
        fi
    else
        if [ "${INTERACTIVE}" == "INTERACTIVE" ]; then
            ask "Would you like to add database variables into env variables?"
            if [[ "${YESNO}" == [Yy][Ee][sS] ]]; then
                env_check
            fi
        elif [ "${FORCE_YES}" == "FORCE_YES" ]; then
            env_check
        else
            echo "Neither \"interactive\" nor \"force-yes\" modes were set check is successfully complete without any changes to system. ----- OK"
            exit 0
        fi

    fi
}

. "${location}/dos_functions.sh"

if [ $(basename -- "$0") ==  "dos_check_db.sh" ]; then
    set -ex
    opts $@
    db_opts
    install_func
fi
