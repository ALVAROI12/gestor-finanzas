#!/usr/bin/env python3
# streamlit_app.py

import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

# --- Configuración página ---
st.set_page_config(page_title="Gestor de Finanzas Semanales", layout="wide")
DB_PATH = os.path.join(os.getcwd(), "gestor_finanzas.db")
FIXED_MONTHLY_META = 4450.0      # Gasto fijo mensual
UPSTART_MONTHLY_LIMIT = 275.0   # Límite mensual Upstart

def get_connection():
    return sqlite3.connect(DB_PATH)

def format_money(x):
    return f"${x:,.2f}"

def allocate_income(conn, income_amount):
    cur = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1) Insertar ingreso
    cur.execute(
        "INSERT INTO incomes (date, amount, source) VALUES (?, ?, ?)",
        (today, income_amount, "Real")
    )
    inc_id = cur.lastrowid

    # 2) ¿Cuánto ya se pagó de Gasto Fijo?
    spent_fixed = cur.execute(
        "SELECT COALESCE(SUM(to_expenses),0) FROM allocations"
    ).fetchone()[0]
    # Cubrir hasta la meta
    to_expenses = 0.0
    if spent_fixed < FIXED_MONTHLY_META:
        to_expenses = min(income_amount, FIXED_MONTHLY_META - spent_fixed)
    remainder = income_amount - to_expenses

    # 3) Ahorros (70% del sobrante)
    to_savings = remainder * 0.70
    each_sav = to_savings / 3
    sav_deposits = {}
    for name in ["CAR", "RENT", "INVEST"]:
        pid, bal, tgt = cur.execute(
            "SELECT id, current_balance, target_amount FROM savings_pockets WHERE name=?",
            (name,)
        ).fetchone()
        needed = max((tgt or 0.0) - bal, 0.0)
        pay = min(each_sav, needed)
        if pay > 0:
            cur.execute(
                "UPDATE savings_pockets "
                "SET current_balance = current_balance + ? "
                "WHERE id = ?",
                (pay, pid)
            )
        sav_deposits[name] = pay

    used_sav = sum(sav_deposits.values())
    # 4) Deudas recibe 30% + sobrante de ahorros no usado
    debt_pool = remainder * 0.30 + (to_savings - used_sav)

    # 5) Upstart: límite mensual
    paid_up_month = cur.execute(
        "SELECT COALESCE(SUM(to_upstart),0) FROM allocations"
    ).fetchone()[0]
    avail_up = max(UPSTART_MONTHLY_LIMIT - paid_up_month, 0.0)
    up_pay = min(avail_up, debt_pool)
    # Aplicar pago Upstart
    cur.execute(
        "UPDATE debts SET min_payment = ?, total_balance = total_balance - ? WHERE name = 'Upstart'",
        (up_pay, up_pay)
    )
    debt_left = debt_pool - up_pay

    # 6) Resto de tarjetas proporcional
    rows = cur.execute(
        "SELECT id, name, total_balance FROM debts WHERE name!='Upstart' AND total_balance>0"
    ).fetchall()
    total_bal = sum(r[2] for r in rows)
    debt_deposits = {"Upstart": up_pay}
    for did, name, bal in rows:
        pay = min((bal/total_bal)*debt_left if total_bal>0 else 0.0, bal)
        if pay > 0:
            cur.execute(
                "UPDATE debts "
                "SET min_payment = ?, total_balance = total_balance - ? "
                "WHERE id = ?",
                (pay, pay, did)
            )
        debt_deposits[name] = pay

    # 7) Guardar allocation con columna to_upstart
    cur.execute("""
        INSERT INTO allocations (
          income_id, to_expenses, to_upstart, to_debts,
          to_savings_car, to_savings_rent, to_savings_invest, to_other
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inc_id,
        to_expenses,
        up_pay,
        sum(v for k,v in debt_deposits.items() if k!="Upstart"),
        sav_deposits["CAR"],
        sav_deposits["RENT"],
        sav_deposits["INVEST"],
        0.0
    ))
    conn.commit()

    return {
        "Gasto Fijo": to_expenses,
        **sav_deposits,
        "Pago Deudas": up_pay + sum(v for k,v in debt_deposits.items() if k!="Upstart"),
        "Detalles Deudas": debt_deposits
    }

def main():
    conn = get_connection()
    st.title("🗂️ Gestor de Finanzas Semanales")

    # Sidebar: reinicio mensual
    if st.sidebar.button("Iniciar Nuevo Mes"):
        conn.execute("DELETE FROM allocations")
        conn.commit()
        st.sidebar.success("✅ Mes reiniciado (Upstart a 0)")

    income_amt = st.sidebar.number_input(
        "Monto recibido esta semana", min_value=0.0, step=10.0
    )
    if st.sidebar.button("Distribuir Ingreso"):
        res = allocate_income(conn, income_amt)
        st.sidebar.success("🔄 Distribución ejecutada:")
        for k,v in res.items():
            if k!="Detalles Deudas":
                st.sidebar.write(f"- **{k}**: {format_money(v)}")
        st.sidebar.write("**Por Tarjeta:**")
        for nm,pay in res["Detalles Deudas"].items():
            st.sidebar.write(f"  - {nm}: {format_money(pay)}")

    # 📌 Gastos Fijos
    st.subheader("📌 Gastos Fijos")
    spent = conn.execute("SELECT COALESCE(SUM(to_expenses),0) FROM allocations").fetchone()[0]
    last = conn.execute("SELECT to_expenses FROM allocations ORDER BY id DESC LIMIT 1").fetchone()
    last_val = last[0] if last else 0.0
    falt = max(FIXED_MONTHLY_META - spent, 0.0)
    df_fixed = pd.DataFrame([{
        "Descripción": "Gasto Fijo Mensual",
        "Monto Meta": FIXED_MONTHLY_META,
        "Dinero Actual": spent,
        "Último Depósito": last_val,
        "Faltante": falt
    }])
    for col in df_fixed.columns[1:]:
        df_fixed[col] = df_fixed[col].map(format_money)
    st.table(df_fixed)

    # 💰 Ahorros
    st.subheader("💰 Ahorros")
    last_vals = conn.execute(
        "SELECT to_savings_car,to_savings_rent,to_savings_invest FROM allocations ORDER BY id DESC LIMIT 1"
    ).fetchone() or (0.0,0.0,0.0)
    rows=[]
    for name,cur_bal,tgt in conn.execute(
        "SELECT name,current_balance,target_amount FROM savings_pockets"
    ):
        idx = ["CAR","RENT","INVEST"].index(name)
        last_dep = last_vals[idx]
        falt_sav = max((tgt or 0.0)-cur_bal,0.0)
        rows.append({
            "Descripción":name,
            "Monto Meta":tgt or 0.0,
            "Dinero Actual":cur_bal,
            "Último Depósito":last_dep,
            "Faltante":falt_sav
        })
    df_sav=pd.DataFrame(rows)
    for col in df_sav.columns[1:]:
        df_sav[col] = df_sav[col].map(format_money)
    st.table(df_sav)

    # 💳 Tarjetas de Crédito
    st.subheader("💳 Tarjetas de Crédito")
    rows=[]
    for name,bal,pay in conn.execute(
        "SELECT name,total_balance,min_payment FROM debts"
    ):
        rows.append({
            "Descripción":name,
            "Monto Deuda":bal,
            "Dinero Actual":pay,
            "Último Depósito":pay,
            "Faltante":bal
        })
    df_deb=pd.DataFrame(rows)
    for col in df_deb.columns[1:]:
        df_deb[col] = df_deb[col].map(format_money)
    st.table(df_deb)

    conn.close()

if __name__=="__main__":
    main()
