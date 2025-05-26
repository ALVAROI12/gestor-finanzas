#!/usr/bin/env python3
# gestor_finanzas.py

import os
import sqlite3

# Ruta de la base de datos en el directorio actual
DB_PATH = os.path.join(os.getcwd(), "gestor_finanzas.db")

def create_schema(conn):
    conn.executescript("""
    DROP TABLE IF EXISTS incomes;
    DROP TABLE IF EXISTS expenses;
    DROP TABLE IF EXISTS debts;
    DROP TABLE IF EXISTS savings_pockets;
    DROP TABLE IF EXISTS allocations;

    CREATE TABLE incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        amount REAL NOT NULL,
        source TEXT
    );

    CREATE TABLE expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        amount REAL NOT NULL
    );

    CREATE TABLE debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        total_balance REAL NOT NULL,
        min_payment REAL NOT NULL
    );

    CREATE TABLE savings_pockets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        current_balance REAL NOT NULL,
        target_amount REAL
    );

    CREATE TABLE allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        income_id INTEGER NOT NULL,
        to_expenses REAL,
        to_upstart REAL,
        to_debts REAL,
        to_savings_car REAL,
        to_savings_rent REAL,
        to_savings_invest REAL,
        to_other REAL,
        FOREIGN KEY (income_id) REFERENCES incomes(id)
    );
    """)
    conn.commit()

def populate_base_data(conn):
    cur = conn.cursor()

    # Gastos fijos
    cur.execute(
        "INSERT INTO expenses (category, amount) VALUES (?, ?)",
        ("Gasto Fijo Mensual", 4450.0)
    )

    # Deudas
    debts = [
        ("Discover 2", 1533.0, 0.0),
        ("Apple 1",    210.0,  0.0),
        ("Apple 2",   1565.0,  0.0),
        ("Capital 1",   40.6,  0.0),
        ("Chase 1",   6240.0,  0.0),
        ("Chase 2",   1607.0,  0.0),
        ("Upstart",   8250.0,  0.0),
        ("Affirm",    2900.0,  0.0),
        ("Paypal",     324.0,  0.0),
    ]
    cur.executemany(
        "INSERT INTO debts (name, total_balance, min_payment) VALUES (?, ?, ?)",
        debts
    )

    # Bolsillos de ahorro
    savings = [
        ("CAR",    570.0,  3840.0),
        ("RENT",   800.0,  9600.0),
        ("INVEST",1276.0,     None),
    ]
    cur.executemany(
        "INSERT INTO savings_pockets (name, current_balance, target_amount) VALUES (?, ?, ?)",
        savings
    )

    conn.commit()

def main():
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    populate_base_data(conn)
    conn.close()
    print(f"✅ Base de datos inicializada en {DB_PATH}")

if __name__ == "__main__":
    main()
