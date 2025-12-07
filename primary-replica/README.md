# MySQL Primary-Replica Replication Setup

Primary-Replica MySQL dengan arsitektur 1 Primary dan 3 Replica menggunakan Docker.

## Arsitektur

![Primary-Replica Architecture](/assets/primary-replica.jpeg)

## Cara Menggunakan

### 1. Start Services

```bash
cd primary-replica
docker-compose up -d
```

### 2. Setup Replication

Jalankan script setup setelah semua container berjalan:

```bash
chmod +x setup.sh
./setup.sh
```

### 3. Verifikasi Replication

Cek status replikasi pada setiap replica:

```bash
# Replica 1
docker exec -i mysql-replica1 mysql -uroot -ppassword -e "SHOW REPLICA STATUS\G"

# Replica 2
docker exec -i mysql-replica2 mysql -uroot -ppassword -e "SHOW REPLICA STATUS\G"

# Replica 3
docker exec -i mysql-replica3 mysql -uroot -ppassword -e "SHOW REPLICA STATUS\G"
```

**Indikator Sukses:**
- `Replica_IO_Running: Yes`
- `Replica_SQL_Running: Yes`
- `Seconds_Behind_Source: 0` (semakin kecil semakin baik)

### 4. Testing Replication

**Insert data pada Primary:**

```bash
docker exec -i mysql-primary mysql -uroot -prootpassword -e "USE testdb; INSERT INTO users (username, email) VALUES ('testuser', 'test@example.com');"
```

**Cek data pada Replica:**

```bash
docker exec -i mysql-replica1 mysql -uroot -prootpassword -e "USE testdb; SELECT * FROM users;"
```

## Konfigurasi my.cnf

### Primary Configuration (`config/primary/my.cnf`)

**Konfigurasi Penting:**

```ini
server-id = 1                    # ID unik untuk server
log-bin = mysql-bin             # Enable binary logging
binlog-format = ROW             # Format replikasi
gtid-mode = ON                  # Enable GTID untuk replikasi otomatis
enforce-gtid-consistency = ON    # Enforce GTID consistency
```

**Penjelasan Parameter:**

- **server-id**: Identifier unik untuk setiap MySQL instance dalam cluster
- **log-bin**: Binary log untuk menyimpan perubahan database
- **binlog-format**:
  - `ROW`: Mencatat perubahan pada level baris
  - `STATEMENT`: Mencatat SQL statements
  - `MIXED`: Kombinasi keduanya
- **gtid-mode**: Global Transaction ID untuk tracking transaksi
- **binlog-do-db**: Database yang akan direplikasi
- **sync_binlog**: Sinkronisasi binary log ke disk (1 = setiap transaksi)

### Replica Configuration (`config/replica*/my.cnf`)

**Konfigurasi Penting:**

```ini
server-id = 2/3/4               # ID (berbeda untuk tiap replica)
relay-log = relay-log-replica*   # Relay log untuk menerima perubahan
read-only = ON                   # Mode read-only untuk replica (diset setelah docker jalan lewat setup.sh)
super-read-only = ON             # Mencegah perubahan oleh superuser (diset setelah docker jalan lewat setup.sh)
gtid-mode = ON                   # Enable GTID
```

**Penjelasan Parameter:**

- **relay-log**: Log sementara untuk menyimpan perubahan dari primary sebelum diaplikasikan
- **read-only**: Mencegah write operations (kecuali dari replication thread)
- **super-read-only**: Mencegah write bahkan dari user dengan privileges tinggi
- **slave_parallel_workers**: Jumlah thread untuk parallel replication
- **slave_parallel_type**:
  - `LOGICAL_CLOCK`: Paralel berdasarkan logical clock (lebih efisien)
  - `DATABASE`: Paralel per database
- **relay_log_recovery**: Otomatis recovery relay log jika crash

## Connection Details

| Node | Host | Port | Username | Password | Access |
|------|------|------|----------|----------|--------|
| Primary | localhost | 3306 | root | rootpassword | Read/Write |
| Replica 1 | localhost | 3307 | root | rootpassword | Read Only |
| Replica 2 | localhost | 3308 | root | rootpassword | Read Only |
| Replica 3 | localhost | 3309 | root | rootpassword | Read Only |

## Performance Tuning

Beberapa parameter dalam `my.cnf` untuk optimasi:

- **innodb_buffer_pool_size**: Cache untuk data dan index
- **max_connections**: Maksimal koneksi
- **innodb_flush_log_at_trx_commit**:
  - `1`: Flush setiap transaksi (paling aman, lambat)
  - `2`: Flush setiap detik (balance)
  - `0`: OS yang kontrol (tercepat, kurang aman)
