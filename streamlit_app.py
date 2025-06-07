#!/usr/bin/env python3
# streamlit_app.py

import os
from datetime import datetime

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import pandas as pd

# --- Inicializar Firestore ---
if "db" not in st.session_state:
    # En producción: usamos la clave en st.secrets
    if "FIREBASE_KEY" in st.secrets:
        cred = credentials.Certificate(st.secrets["FIREBASE_KEY"])
    else:
        # Para desarrollo local - asegúrate de ignorar este archivo en git
        key_path = os.path.join(os.getcwd(), "serviceAccount.json")
        cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    st.session_state.db = firestore.client()
db = st.session_state.db

# --- Configuración de la página ---
st.set_page_config(page_title="Gestor de Finanzas Semanales", layout="wide")

# Constantes
FIXED_MONTHLY_META    = 2600.0
UPSTART_MONTHLY_LIMIT = 275.0
MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
SAVINGS_WEIGHTS = {
    "RENT":    0.40,
    "CAR":     0.30,
    "Savings": 0.20,
    "INVEST":  0.10
}

def format_money(x):
    """Formatea un número o string como moneda."""
    try:
        n = float(x)
    except:
        return ""
    return f"${n:,.2f}"

def allocate_income(amount: float):
    """
    Registra un ingreso y reparte:
      1) Gastos fijos hasta FIXED_MONTHLY_META
      2) Ahorros 70% sobrante según SAVINGS_WEIGHTS
      3) Deudas: Upstart hasta 275/mes, resto proporcional
    Guarda además 'debt_details' en allocations.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # 1) Registrar ingreso
    inc_ref = db.collection("incomes").add({
        "date": today,
        "amount": amount,
        "source": "Real"
    })
    inc_id = inc_ref[1].id

    # 2) Cubrir gastos fijos
    spent_fixed = sum(a.to_dict().get("to_expenses", 0.0)
                      for a in db.collection("allocations").stream())
    to_exp = min(amount, FIXED_MONTHLY_META - spent_fixed) \
             if spent_fixed < FIXED_MONTHLY_META else 0.0
    rem = amount - to_exp

    # 3) Ahorros (70% del sobrante)
    to_sav = rem * 0.70
    sav_dep = {}
    for name, weight in SAVINGS_WEIGHTS.items():
        alloc = to_sav * weight
        docs = list(db.collection("savings_pockets")
                    .where(filter=FieldFilter("name", "==", name))
                    .stream())
        if not docs:
            continue
        ref = docs[0]
        data = ref.to_dict()
        bal = float(data.get("current_balance", 0.0))
        tgt = data.get("target_amount")
        if name in ("Savings", "INVEST"):
            pay = alloc
        else:
            need = max((tgt or 0.0) - bal, 0.0)
            pay = min(alloc, need)
        if pay > 0:
            db.collection("savings_pockets").document(ref.id).update({
                "current_balance": firestore.Increment(pay)
            })
        sav_dep[name] = pay

    used_sav = sum(sav_dep.values())
    debt_pool = rem * 0.30 + (to_sav - used_sav)

    # 4) Pago a Upstart (límite mensual)
    paid_up = sum(a.to_dict().get("to_upstart", 0.0)
                  for a in db.collection("allocations").stream())
    avail_up = max(UPSTART_MONTHLY_LIMIT - paid_up, 0.0)
    up_pay = min(avail_up, debt_pool)
    up_docs = list(db.collection("debts")
                   .where(filter=FieldFilter("name", "==", "Upstart"))
                   .stream())
    if up_docs:
        db.collection("debts").document(up_docs[0].id).update({
            "total_balance": firestore.Increment(-up_pay)
        })
    debt_left = debt_pool - up_pay

    # 5) Resto de deudas (filtrado en Python)
    all_debts = db.collection("debts").stream()
    debt_docs = [
        d for d in all_debts
        if d.to_dict().get("name") != "Upstart"
           and float(d.to_dict().get("total_balance", 0.0)) > 0.0
    ]
    total_bal = sum(float(d.to_dict().get("total_balance", 0.0)) for d in debt_docs)
    debt_dep = {"Upstart": up_pay}
    for ref in debt_docs:
        data = ref.to_dict()
        bal = float(data["total_balance"])
        pay = min((bal / total_bal) * debt_left if total_bal > 0 else 0.0, bal)
        if pay > 0:
            db.collection("debts").document(ref.id).update({
                "total_balance": firestore.Increment(-pay)
            })
        debt_dep[data["name"]] = pay

    # 6) Guardar allocation con detalles
    db.collection("allocations").add({
        "income_id":        inc_id,
        "to_expenses":      to_exp,
        "to_upstart":       up_pay,
        "to_debts":         sum(v for k, v in debt_dep.items() if k != "Upstart"),
        "to_savings_car":    sav_dep.get("CAR", 0.0),
        "to_savings_rent":   sav_dep.get("RENT", 0.0),
        "to_savings_invest": sav_dep.get("INVEST", 0.0),
        "to_other":          sav_dep.get("Savings", 0.0),
        "debt_details":     debt_dep
    })

    return to_exp, sav_dep, debt_dep

def main():
    # Control de mes actual
    if "month_idx" not in st.session_state:
        st.session_state.month_idx = datetime.now().month

    st.title("🗂️ Gestor de Finanzas Semanales")
    mes = MONTH_NAMES[(st.session_state.month_idx - 1) % 12]
    st.markdown(f"## Mes: **{mes}**")

    # Botón: iniciar nuevo mes
    if st.sidebar.button("Iniciar Nuevo Mes"):
        for a in db.collection("allocations").stream():
            db.collection("allocations").document(a.id).delete()
        st.session_state.month_idx = (st.session_state.month_idx % 12) + 1
        st.sidebar.success(f"✅ Mes reiniciado a {MONTH_NAMES[st.session_state.month_idx-1]}")

    # Input y distribución
    inc = st.sidebar.number_input("Monto recibido esta semana", min_value=0.0, step=10.0)
    if st.sidebar.button("Distribuir Ingreso"):
        to_exp, sav_dep, debt_dep = allocate_income(inc)
        st.sidebar.write(f"- **Gasto Fijo**: {format_money(to_exp)}")
        for k, v in sav_dep.items():
            st.sidebar.write(f"- **Ahorro {k}**: {format_money(v)}")
        st.sidebar.write(f"- **Pago Deudas Total**: {format_money(sum(v for k, v in debt_dep.items() if k!='Upstart'))}")
        st.sidebar.write("**Detalle Deudas:**")
        for k, v in debt_dep.items():
            st.sidebar.write(f"  - {k}: {format_money(v)}")

    # 📌 GASTOS FIJOS
    st.subheader("📌 GASTOS FIJOS")
    allocs = list(db.collection("allocations").stream())
    spent = sum(a.to_dict().get("to_expenses", 0.0) for a in allocs)
    last_exp = allocs[-1].to_dict().get("to_expenses", 0.0) if allocs else 0.0
    falt = max(FIXED_MONTHLY_META - spent, 0.0)
    df_fixed = pd.DataFrame([{
        "Descripción":     "Gasto Fijo Mensual",
        "Monto Meta":      FIXED_MONTHLY_META,
        "Dinero Actual":   spent,
        "Último Depósito": last_exp,
        "Faltante":        falt
    }])
    for col in df_fixed.columns[1:]:
        df_fixed[col] = df_fixed[col].map(format_money)
    st.table(df_fixed)

    # 💰 AHORROS
    st.subheader("💰 AHORROS")
    last_vals = allocs[-1].to_dict() if allocs else {}
    rows = []
    for s in db.collection("savings_pockets").stream():
        d = s.to_dict()
        name, bal, tgt = d["name"], float(d["current_balance"]), d.get("target_amount")
        key = f"to_savings_{name.lower()}"
        last_dep = last_vals.get(key, 0.0)
        falt_sav = "" if tgt is None else format_money(max(tgt - bal, 0.0))
        rows.append({
            "Descripción":     name,
            "Monto Meta":      "" if tgt is None else format_money(tgt),
            "Dinero Actual":   format_money(bal),
            "Último Depósito": format_money(last_dep),
            "Faltante":        falt_sav
        })
    st.table(pd.DataFrame(rows))

    # 💳 TARJETAS DE CRÉDITO
    st.subheader("💳 TARJETAS DE CRÉDITO")
    last_details = allocs[-1].to_dict().get("debt_details", {}) if allocs else {}
    rows = []
    for dref in db.collection("debts").stream():
        d = dref.to_dict()
        name, bal = d["name"], float(d["total_balance"])
        paid_total = sum(
            a.to_dict().get("debt_details", {}).get(name, 0.0)
            for a in allocs
        )
        last_dep = last_details.get(name, 0.0)
        initial = paid_total + bal
        rows.append({
            "Descripción":     name,
            "Monto Meta":      format_money(initial),
            "Dinero Actual":   format_money(paid_total),
            "Último Depósito": format_money(last_dep),
            "Faltante":        format_money(bal)
        })
    st.table(pd.DataFrame(rows))

if __name__ == "__main__":
    main()
