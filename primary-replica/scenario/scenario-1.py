import pymysql
import time
import threading
from datetime import datetime
from typing import Dict, Tuple, Optional

cfg = {
    'primary': {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'password',
        'database': 'db'
    },
    'replicas': {
        'replica1': {
            'host': 'localhost',
            'port': 3307,
            'user': 'root',
            'password': 'password',
            'database': 'db'
        },
        'replica2': {
            'host': 'localhost',
            'port': 3308,
            'user': 'root',
            'password': 'password',
            'database': 'db'
        },
        'replica3': {
            'host': 'localhost',
            'port': 3309,
            'user': 'root',
            'password': 'password',
            'database': 'db'
        }
    }
}

TOTAL_ROWS = 1000
BATCH_SIZE = 1000
POLL_INTERVAL = 1  # ms
MX_WAIT = 30  # s

def cleanupData(conn):
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM test_replication")
    conn.commit()
    print("Test data cleaned\n")


def insertData(conn, batchNum: int, batchSize: int) -> Tuple[int, datetime]:
    with conn.cursor() as cursor:
        values = []
        for i in range(batchSize):
            values.append(f"('Batch {batchNum} - Row {i+1}', {batchNum})")

        sql = f"INSERT INTO test_replication (data, batch) VALUES {','.join(values)}"
        cursor.execute(sql)
        lastID = cursor.lastrowid + batchSize - 1

    conn.commit()
    commitTime = datetime.now()

    return lastID, commitTime


def getLastRow(nodeName: str, nodeCfg: Dict, targetID: int = None, commitTime: datetime = None) -> Dict:
    result = {
        'node_name': nodeName,
        'last_id': None,
        'data': None,
        'batch': None,
        'row_count': 0,
        'lag_ms': None,
        'found_immediately': False,
        'error': None
    }

    try:
        conn = pymysql.connect(
            host=nodeCfg['host'],
            port=nodeCfg['port'],
            user=nodeCfg['user'],
            password=nodeCfg['password'],
            database=nodeCfg['database'],
            autocommit=True
        )

        with conn:
            with conn.cursor() as cursor:
                if targetID is None:
                    cursor.execute("SELECT id, data, batch FROM test_replication ORDER BY id DESC LIMIT 1")
                    row = cursor.fetchone()

                    if row:
                        result['last_id'] = row[0]
                        result['data'] = row[1]
                        result['batch'] = row[2]

                    cursor.execute("SELECT COUNT(*) FROM test_replication")
                    count = cursor.fetchone()
                    result['row_count'] = count[0] if count else 0
                else:
                    cursor.execute("SELECT id, data, batch FROM test_replication WHERE id = %s", (targetID,))
                    row = cursor.fetchone()

                    if row:
                        result['found_immediately'] = True
                        result['last_id'] = row[0]
                        result['data'] = row[1]
                        result['batch'] = row[2]
                        result['lag_ms'] = 0
                    else:
                        poll_interval = POLL_INTERVAL / 1000.0
                        max_polls = int((MX_WAIT * 1000) / POLL_INTERVAL)

                        for poll_count in range(max_polls):
                            time.sleep(poll_interval)

                            cursor.execute("SELECT id, data, batch FROM test_replication WHERE id = %s", (targetID,))
                            row = cursor.fetchone()

                            if row:
                                found_time = datetime.now()
                                result['last_id'] = row[0]
                                result['data'] = row[1]
                                result['batch'] = row[2]
                                result['lag_ms'] = round((found_time - commitTime).total_seconds() * 1000, 2)
                                break
                        else:
                            result['error'] = f"Timeout after {MX_WAIT}s"
                            result['lag_ms'] = -1

                    cursor.execute("SELECT COUNT(*) FROM test_replication")
                    count = cursor.fetchone()
                    result['row_count'] = count[0] if count else 0

    except Exception as e:
        result['error'] = str(e)

    return result


def runScenario1():
    print("SCENARIO 1: READ-AFTER-WRITE CONSISTENCY & REPLICATION LAG")
    print(f"- Total Rows: {TOTAL_ROWS}")
    print(f"- Batch Size: {BATCH_SIZE}")
    print(f"- Poll Interval: {POLL_INTERVAL} ms")
    print(f"- Primary: localhost:{cfg['primary']['port']}")
    print(f"- Replicas: {len(cfg['replicas'])} containers\n")

    try:
        primary_conn = pymysql.connect(
            host=cfg['primary']['host'],
            port=cfg['primary']['port'],
            user=cfg['primary']['user'],
            password=cfg['primary']['password'],
            database=cfg['primary']['database']
        )
        print("Connected to Primary\n")
    except Exception as e:
        print(f"{e}")
        return

    try:
        cleanupData(primary_conn)

        numBatches = TOTAL_ROWS // BATCH_SIZE
        lastID = None
        commitTime = None

        print(f"Inserting {TOTAL_ROWS} datas into Primary...")

        for num in range(1, numBatches + 1):
            lastID, commitTime = insertData(primary_conn, num, BATCH_SIZE)
            print(f"Batch {num}/{numBatches} inserted (last ID: {lastID})")

        print(f"Commit timestamp: {commitTime.strftime('%Y-%m-%d %H:%M:%S.%f')}\n")

        print("=" * 80)
        print("QUERY LAST ROW (PRIMARY & REPLICA)")
        print("=" * 80)

        primary_result = getLastRow('primary', cfg['primary'])
        print(f"\nPRIMARY:")
        if primary_result['error']:
            print(f"  Error: {primary_result['error']}")
        else:
            print(f"  Last ID:    {primary_result['last_id']}")
            print(f"  Data:       {primary_result['data']}")
            print(f"  Batch:      {primary_result['batch']}")
            print(f"  Row Count:  {primary_result['row_count']}")

        threads = []
        replica_results = []
        resLock = threading.Lock()

        def query_replica(replName, replCfg):
            result = getLastRow(replName, replCfg, lastID, commitTime)
            with resLock:
                replica_results.append(result)

        for replName, replCfg in cfg['replicas'].items():
            thread = threading.Thread(target=query_replica, args=(replName, replCfg))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for replica_result in replica_results:
            print(f"\n{replica_result['node_name'].upper()}:")
            if replica_result['error']:
                print(f"  Error: {replica_result['error']}")
            else:
                print(f"  Last ID:    {replica_result['last_id']}")
                print(f"  Data:       {replica_result['data']}")
                print(f"  Batch:      {replica_result['batch']}")
                print(f"  Row Count:  {replica_result['row_count']}")
                if replica_result['lag_ms'] is not None:
                    if replica_result['lag_ms'] == 0:
                        print(f"  Lag:        0.00 ms (Found immediately)")
                    elif replica_result['lag_ms'] > 0:
                        print(f"  Lag:        {replica_result['lag_ms']} ms")
                    else:
                        print(f"  Lag:        TIMEOUT")

        print("\n" + "=" * 80 + "\n")

        successLag = [r['lag_ms'] for r in replica_results if r['lag_ms'] is not None and r['lag_ms'] >= 0]
        if successLag:
            avg_lag = sum(successLag) / len(successLag)
            min_lag = min(successLag)
            max_lag = max(successLag)
            print("[ REPLICATION LAG SUMMARY ]")
            print(f"Average Lag:  {avg_lag:.2f} ms")
            print(f"Min Lag:      {min_lag:.2f} ms")
            print(f"Max Lag:      {max_lag:.2f} ms")
            print(f"Success Rate: {len(successLag)}/{len(replica_results)} replicas")

    finally:
        primary_conn.close()


if __name__ == "__main__":
    try:
        runScenario1()
    except KeyboardInterrupt:
        print("\n\n Test interrupted by user")
    except Exception as e:
        print(f"\n {e}")
        import traceback
        traceback.print_exc()
