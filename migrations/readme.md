Make backup:
pg_dump -U postgres -Fc postgres > postgres_backup_file

params:
-U {database user}                - specify user
-Fc                               - sprecify backup file format. In this case format is "custom" (c)
{database name} > {backup file}

see: http://www.postgresql.org/docs/9.2/interactive/app-pgdump.html



Restore:
pg_restore -U postgres -c -d postgres postgres_backup_file

params:
-U {database user}    - specify user
-c                    - clean database before restoring
-d {database name}    - specify database name
{backup file}

see: http://www.postgresql.org/docs/9.2/static/app-pgrestore.html



Applying SQL script:
psql -U postgres postgres < migration.sql

params:
-U {database user}    - specify user
{database name} < {SQL script}