#!/bin/bash

echo "Setup mysql primary-replica"

echo "Tunggu mysql replica (20s)"
sleep 20

# Replication source dirubah ke primary dan set read only di replica
echo "Penambahan Source dan Set Read Only Replica 1"
docker exec -i mysql-replica1 mysql -uroot -ppassword <<EOF
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST='mysql-primary',
    SOURCE_USER='repl_user',
    SOURCE_PASSWORD='repl_password',
    SOURCE_AUTO_POSITION=1;
START REPLICA;
SET GLOBAL read_only = ON;
SET GLOBAL super_read_only = ON;
EOF

echo "Penambahan Source dan Set Read Only Replica 2"
docker exec -i mysql-replica2 mysql -uroot -ppassword <<EOF
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST='mysql-primary',
    SOURCE_USER='repl_user',
    SOURCE_PASSWORD='repl_password',
    SOURCE_AUTO_POSITION=1;
START REPLICA;
SET GLOBAL read_only = ON;
SET GLOBAL super_read_only = ON;
EOF

echo "Penambahan Source dan Set Read Only Replica 3"
docker exec -i mysql-replica3 mysql -uroot -ppassword <<EOF
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST='mysql-primary',
    SOURCE_USER='repl_user',
    SOURCE_PASSWORD='repl_password',
    SOURCE_AUTO_POSITION=1;
START REPLICA;
SET GLOBAL read_only = ON;
SET GLOBAL super_read_only = ON;
EOF

echo "Setup Done"

# Cek Status dulu
echo "Cek Status Replica 1"
docker exec -i mysql-replica1 mysql -uroot -ppassword -e "SHOW REPLICA STATUS\G" | grep -E "Replica_IO_Running|Replica_SQL_Running|Seconds_Behind_Source"

echo "Cek Status Replica 2"
docker exec -i mysql-replica2 mysql -uroot -ppassword -e "SHOW REPLICA STATUS\G" | grep -E "Replica_IO_Running|Replica_SQL_Running|Seconds_Behind_Source"

echo "Cek Status Replica 3"
docker exec -i mysql-replica3 mysql -uroot -ppassword -e "SHOW REPLICA STATUS\G" | grep -E "Replica_IO_Running|Replica_SQL_Running|Seconds_Behind_Source"

echo "Replica Jalan"
