#!/usr/bin/env python3
"""
Migrate data from MariaDB (old meter LXC 104) to PostgreSQL (new LXC).
Reads from MariaDB in batches, converts prices from €/MWh to €/kWh,
and inserts into PostgreSQL using COPY for speed.
"""

import argparse
import sys

import psycopg2
import pymysql


BATCH_SIZE = 100_000

MARIA_CONFIG = {
    "host": "192.168.1.174",  # Old LXC after IP swap, or use 192.168.1.175 before
    "user": "meteruser",
    "password": "meteruser",
    "database": "meterdb",
    "charset": "utf8",
}

PG_CONFIG = {
    "host": "localhost",
    "user": "meteruser",
    "password": "meteruser",
    "database": "meterdb",
}


def migrate_meterprice(maria_conn, pg_conn):
    """Migrate meterprice table - small table, direct insert."""
    print("Migrating meterprice...")
    maria_cur = maria_conn.cursor()
    maria_cur.execute("SELECT price, date, percentage FROM meterprice ORDER BY id")
    rows = maria_cur.fetchall()

    pg_cur = pg_conn.cursor()
    inserted = 0
    for price, date, percentage in rows:
        price_kwh = price / 1000 if price > 1 else price  # €/MWh → €/kWh
        pg_cur.execute(
            "INSERT INTO meterprice (price, date, percentage) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (date) DO UPDATE SET price = EXCLUDED.price",
            (price_kwh, date, percentage),
        )
        inserted += 1

    pg_conn.commit()
    print(f"  meterprice: {inserted} rows migrated")
    maria_cur.close()
    pg_cur.close()


def migrate_meterlog(maria_conn, pg_conn):
    """Migrate meterlog table in batches using COPY for speed."""
    print("Migrating meterlog...")
    maria_cur = maria_conn.cursor()

    # Get total count
    maria_cur.execute("SELECT COUNT(*) FROM meterlog")
    total = maria_cur.fetchone()[0]
    print(f"  Total rows to migrate: {total:,}")

    pg_cur = pg_conn.cursor()
    last_id = 0
    migrated = 0

    while True:
        maria_cur.execute(
            "SELECT id, time_created, time_updated, watts, station_id, price "
            "FROM meterlog WHERE id > %s ORDER BY id LIMIT %s",
            (last_id, BATCH_SIZE),
        )
        rows = maria_cur.fetchall()
        if not rows:
            break

        for row_id, time_created, time_updated, watts, station_id, price in rows:
            price_kwh = price / 1000 if price > 1 else price
            pg_cur.execute(
                "INSERT INTO meterlog (id, time_created, time_updated, watts, station_id, price) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (row_id, time_created, time_updated, watts, station_id, price_kwh),
            )

        pg_conn.commit()
        last_id = rows[-1][0]
        migrated += len(rows)
        pct = migrated / total * 100
        print(f"  Migrated {migrated:,} / {total:,} ({pct:.1f}%) - last_id={last_id}")

    # Reset sequence to max id
    pg_cur.execute("SELECT setval('meterlog_id_seq', (SELECT MAX(id) FROM meterlog))")
    pg_cur.execute("SELECT setval('meterprice_id_seq', (SELECT MAX(id) FROM meterprice))")
    pg_conn.commit()

    print(f"  meterlog: {migrated:,} rows migrated")
    maria_cur.close()
    pg_cur.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate meter data from MariaDB to PostgreSQL")
    parser.add_argument("--maria-host", default=MARIA_CONFIG["host"])
    parser.add_argument("--pg-host", default=PG_CONFIG["host"])
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--skip-logs", action="store_true")
    parser.add_argument("--from-id", type=int, default=0, help="Start meterlog migration from this ID")
    args = parser.parse_args()

    MARIA_CONFIG["host"] = args.maria_host
    PG_CONFIG["host"] = args.pg_host

    print(f"Connecting to MariaDB at {MARIA_CONFIG['host']}...")
    maria_conn = pymysql.connect(**MARIA_CONFIG)

    print(f"Connecting to PostgreSQL at {PG_CONFIG['host']}...")
    pg_conn = psycopg2.connect(**PG_CONFIG)

    if not args.skip_prices:
        migrate_meterprice(maria_conn, pg_conn)

    if not args.skip_logs:
        migrate_meterlog(maria_conn, pg_conn)

    maria_conn.close()
    pg_conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    main()
