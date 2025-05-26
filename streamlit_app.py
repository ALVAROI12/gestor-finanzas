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
FIXED_MONTHLY_META = 2600.0      # según tabla expenses
UPSTART_MONTHLY_LIMIT = 275.0    # tope mensual para Upstart
MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
# pesos sobre el 70% sobrante
SAVINGS_WEIGHTS = {
    "RENT":     0.40,  # hasta target
    "CAR":      0.30,  # hasta target
    "Savings":  0.20,  # sin límite
    "INVEST":   0.10,  # sin límite
}

def get_connection():
    return sqlite3.connect(DB_PATH)

def format_money(x):
    return f"${x:,.2f}"

def allocate_income(conn, income_amount):
    cur = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # 1) Registrar ingreso
    cur.execute(
        "INSERT INTO incomes (date, amount, source) VALUES (?, ?, ?)",
        (today, income_amount, "Real")
    )
    inc_id = cur.lastrowid

    # 2) Gasto fijo acumulado
    spent_fixed = cur.execute(
        "SELECT COALESCE(SUM(to_expenses),0) FROM allocations"
    ).fetchone()[0]

    # Cubrir gasto fijo hasta 2600
    if spent_fixed < FIXED_MONTHLY_META:
        to_expenses = min(income_amount, FIXED_MONTHLY_META - spent_fixed)
    else:
        to_expenses = 0.0
    remainder = income_amount - to_expenses

    # 3) Ahorros: 70% del sobrante
    to_savings = remainder * 0.70
    sav_deposits = {}
    for name, weight in SAVINGS_WEIGHTS.items():
        pid, bal, tgt = cur.execute(
            "SELECT id, current_balance, target_amount FROM savings_pockets WHERE name = ?",
            (name,)
        ).fetchone()
        alloc = to_savings * weight
        if name in ("Savings", "INVEST"):
            # sin límite: siempre recibe su parte
            pay = alloc
        else:
            # respeta target
            needed = max((tgt or 0.0) - bal, 0.0)
            pay = min(alloc, needed)
        if pay > 0:
            cur.execute(
                "UPDATE savings_pockets SET current_balance = current_balance + ? WHERE id = ?",
                (pay, pid)
            )
        sav_deposits[name] = pay

    used_sav = sum(sav_deposits.values())
    debt_pool = remainder * 0.30 + (to_savings - used_sav)

    # 4) Deudas: Upstart mensual hasta 275, luego proporcional
    paid_up_month = cur.execute(
        "SELECT COALESCE(SUM(to_upstart),0) FROM allocations"
    ).fetchone()[0]
    avail_up = max(UPSTART_MONTHLY_LIMIT - paid_up_month, 0.0)
    up_pay = min(avail_up, debt_pool)
    cur.execute(
        "UPDATE debts SET min_payment = ?, total_balance = total_balance - ? WHERE name = 'Upstart'",
        (up_pay, up_pay)
    )
    debt_left = debt_pool - up_pay

    rows = cur.execute(
        "SELECT id, name, total_balance FROM debts WHERE name != 'Upstart' AND total_balance > 0"
    ).fetchall()
    total_bal = sum(r[2] for r in rows)
    debt_deposits = {"Upstart": up_pay}
    for did, name, bal in rows:
        pay = min((bal / total_bal) * debt_left if total_bal > 0 else 0.0, bal)
        if pay > 0:
            cur.execute(
                "UPDATE debts SET min_payment = ?, total_balance = total_balance - ? WHERE id = ?",
                (pay, pay, did)
            )
        debt_deposits[name] = pay

    # 5) Guardar allocation
    car_pay    = sav_deposits.get("CAR", 0.0)
    rent_pay   = sav_deposits.get("RENT", 0.0)
    inv_pay    = sav_deposits.get("INVEST", 0.0)
    other_sav  = sav_deposits.get("Savings", 0.0)

    cur.execute("""
        INSERT INTO allocations (
            income_id, to_expenses, to_upstart, to_debts,
            to_savings_car, to_savings_rent, to_savings_invest, to_other
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inc_id,
        to_expenses,
        up_pay,
        sum(v for k, v in debt_deposits.items() if k != "Upstart"),
        car_pay,
        rent_pay,
        inv_pay,
        other_sav
    ))
    conn.commit()

    return {
        "Gasto Fijo": to_expenses,
        **sav_deposits,
        "Pago Deudas": up_pay + sum(v for k, v in debt_deposits.items() if k != "Upstart"),
        "Detalles Deudas": debt_deposits
    }

def main():
    # Estado de mes (inicia en mes actual)
    if "month_idx" not in st.session_state:
        st.session_state.month_idx = datetime.now().month

    conn = get_connection()
    st.title("🗂️ Gestor de Finanzas Semanales")

    # Mostrar mes
    mes = MONTH_NAMES[(st.session_state.month_idx - 1) % 12]
    st.markdown(f"## Mes: **{mes}**")

    # Iniciar Nuevo Mes
    if st.sidebar.button("Iniciar Nuevo Mes"):
        st.session_state.month_idx = (st.session_state.month_idx % 12) + 1
        conn.execute("DELETE FROM allocations")
        conn.commit()
        st.sidebar.success(f"✅ Reiniciado a {MONTH_NAMES[st.session_state.month_idx-1]}")

    # Ingreso semanal
    income_amt = st.sidebar.number_input("Monto recibido esta semana", min_value=0.0, step=10.0)
    if st.sidebar.button("Distribuir Ingreso"):
        res = allocate_income(conn, income_amt)
        st.sidebar.success("🔄 Distribución ejecutada:")
        for k, v in res.items():
            if k != "Detalles Deudas":
                st.sidebar.write(f"- **{k}**: {format_money(v)}")
        st.sidebar.write("**Por Tarjeta:**")
        for nm, pay in res["Detalles Deudas"].items():
            st.sidebar.write(f"  - {nm}: {format_money(pay)}")

    # 📌 Gastos Fijos
    st.subheader("📌 Gastos Fijos")
    spent = conn.execute("SELECT COALESCE(SUM(to_expenses),0) FROM allocations").fetchone()[0]
    last = conn.execute("SELECT to_expenses FROM allocations ORDER BY id DESC LIMIT 1").fetchone()
    last_exp = last[0] if last else 0.0
    falt = max(FIXED_MONTHLY_META - spent, 0.0)
    df_fixed = pd.DataFrame([{
        "Descripción":       "Gasto Fijo Mensual",
        "Monto Meta":        FIXED_MONTHLY_META,
        "Dinero Actual":     spent,
        "Último Depósito":   last_exp,
        "Faltante":          falt
    }])
    for c in df_fixed.columns[1:]:
        df_fixed[c] = df_fixed[c].map(format_money)
    st.table(df_fixed)

    # 💰 Ahorros
    st.subheader("💰 Ahorros")
    last_vals = conn.execute(
        "SELECT to_savings_car, to_savings_rent, to_savings_invest, to_other "
        "FROM allocations ORDER BY id DESC LIMIT 1"
    ).fetchone() or (0.0, 0.0, 0.0, 0.0)

    rows = []
    for idx, (name, cur_bal, tgt) in enumerate(conn.execute(
        "SELECT name, current_balance, target_amount FROM savings_pockets"
    )):
        last_dep = last_vals[idx] if idx < len(last_vals) else 0.0
        falt_sav = "" if tgt is None else format_money(max(tgt - cur_bal, 0.0))
        rows.append({
            "Descripción":     name,
            "Monto Meta":      "" if tgt is None else format_money(tgt),
            "Dinero Actual":   format_money(cur_bal),
            "Último Depósito": format_money(last_dep),
            "Faltante":        falt_sav
        })

    df_sav = pd.DataFrame(rows)
    st.table(df_sav)

    # 💳 Tarjetas de Crédito
    st.subheader("💳 Tarjetas de Crédito")
    rows = []
    for name, bal, pay in conn.execute("SELECT name, total_balance, min_payment FROM debts"):
        rows.append({
            "Descripción":     name,
            "Monto Deuda":     format_money(bal),
            "Dinero Actual":   format_money(pay),
            "Último Depósito": format_money(pay),
            "Faltante":        format_money(bal)
        })
    df_deb = pd.DataFrame(rows)
    st.table(df_deb)

    conn.close()

if __name__ == "__main__":
    main()
