#!/usr/bin/env python3
# streamlit_app.py

import json
from datetime import datetime

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import pandas as pd

# --- Tus credenciales de Firebase directamente en el código ---
firebase_config = {
  "type": "service_account",
  "project_id": "pesito-d79d3",
  "private_key_id": "adcbda96f20fd2560f1df4c72de7992aa2a73f5a",
  "private_key": """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDolMwWetC8fiwq
ahBH067zEjFlRiIc1CqnRRvSU91U7g3sRiO6CciQu9NEk5R8kf9dBWDCJhaP/c5P
/NVR8qjdVu8Z6TzdTM08ZOVpzktHbyeXGhNGcI9eNUA6P+GfLm4jorqiW90Hhyr2
PA3xLvssz2zigGNjf5gbWKyc1KxPpWyxr7Av383qgznblmCVfFeDaSXGlZ75Ca5U
hQ+YaXoCiNsElRT7857fsfijahQmumK4bmW8OOBuZi+2dGFUc/JxCatJv9KRKfZV
tvKwEqn2/BRNJqnUT+tiq2xifCiJ0PKg9Swq5dDEHAt0y4bNvxAg9dIExL8XHgM6
VlQdCBOdAgMBAAECggEAD5ysBcGbu7Nfz+m2YGPqD/XuK+VPyo3xXltfY+MY7dJc
S+UPZosGlAnk7hWr93VYu2FDiUoY5J8oV1UvlTnL3QOwtsAMblxxQGG+G+KVn1zA
6b3TLRIcMDo0g/8gFtkn2oDaCfukSWo+LNuDd2eXGP8Zc4DOaxzi/x7uLfQsAYfb
54aOSgJdN+Q3G63T7Ea+42swboKYXAvZlCfP+yfuoBvNlWv6tNTDst+fplpqvFrd
yAQU8nTRhY14XoOL9v6MeVZdpaFlA39ixR9b0U86r5JD+V0kXCD8Fms3XlvDP8Gc
LS+TheQQdaJhMGXUbvghPQmGPcoggJYkG4URUWcrLwKBgQD3KhfuNGHCGIgUfqVM
EeCNqyCtiaz4JWAQDGvRw4KrUTyVgeIGBpmcQsJ5QZvoYcbjDrJ3H61qaq6Q2wrg
glOwXeN6EgFdT6+/hX8bnwX1qpF8EAdFJPltHzAwG5VbfJ67kInVF+++cOsRQW0r
oJYt0P722AqQLDAvyfkvh89kMwKBgQDw5T8t/AlJ1EiUzH3Ny0Xd6W0SbXqWZgPb
wJpYFpFLyRBtq3+oMPFZQQ8zncdlYkKGvYSXxCOlcIJecr9buHFaBxzS+YOWbBmM
yHiSy+7mbvxa+7eBjVy+/UYAWndTizYUQd5WICCKqnh1SCHzvZmwP0HhLe2KdkXr
KZxNIChY7wKBgQCnFUaOGc0IF+tN53s4nFEvk8KIbayHJ0T0NGFisQcRZt5Mtzuj
FS0cbCjpLYgGpKp9bb8JNlnVuX5+oASPVqraa+3N5IQVnzvQfZ86fdrags7Mjk1L
2b3fnZjGvK7P5MOtSf1TF1ZTaCQQSylQt8Mt/72MAunJIoYEmEWicu2o7wKBgQDE
kArxlsptd86RvBqbJdaosKPTeYmh1zQmyA4o+qEsWbASDPJpZyZIUhH5aDEfxQHL
uDDNNbpwcFGwh6klSmcTsuIONJLu1t4yRhI8ljMlzEIWa3bdO2AGZ9wKxcbAYMOL
3ANz+1sSSu9no6gwnvEdI0C6YSOG6+M5dAaZ2DeT+QKBgQDFnX5I1hNjNdlHUTDW
6rVt7Lg0wfJfr6ry70UEDacLAdhValZ5rnBeuOt5RKL1peOncYYJX9aOytyBeVz1
tfZovps9cBpQYECaLuqwVdK2PctbdhEIMPYOr3ETK4AlXnnUW37uyOjszTaYXcqM
VMGidiJgyH9TGDQDfQ+VCBkp5w==
-----END PRIVATE KEY-----
""",
  "client_email": "firebase-adminsdk-fbsvc@pesito-d79d3.iam.gserviceaccount.com",
  "client_id": "110865967361220166660",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40pesito-d79d3.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

# --- Inicializar Firestore usando esas credenciales ---
if "db" not in st.session_state:
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)
    st.session_state.db = firestore.client()
db = st.session_state.db

# --- Configuración de la página ---
st.set_page_config(page_title="Gestor de Finanzas Semanales", layout="wide")

# Constantes y funciones de formato
FIXED_MONTHLY_META    = 2600.0
UPSTART_MONTHLY_LIMIT = 275.0
MONTH_NAMES = [
    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"
]
SAVINGS_WEIGHTS = {"RENT":0.40, "CAR":0.30, "Savings":0.20, "INVEST":0.10}

def format_money(x):
    try: n = float(x)
    except: return ""
    return f"${n:,.2f}"

def allocate_income(amount: float):
    today = datetime.now().strftime("%Y-%m-%d")
    # 1) Registrar ingreso
    inc_ref = db.collection("incomes").add({
        "date": today, "amount": amount, "source": "Real"
    })
    inc_id = inc_ref[1].id

    # 2) Cubrir gastos fijos
    spent_fixed = sum(a.to_dict().get("to_expenses",0.0)
                      for a in db.collection("allocations").stream())
    to_exp = min(amount, FIXED_MONTHLY_META - spent_fixed) \
             if spent_fixed < FIXED_MONTHLY_META else 0.0
    rem = amount - to_exp

    # 3) Ahorros (70%)
    to_sav = rem * 0.70
    sav_dep = {}
    for name,w in SAVINGS_WEIGHTS.items():
        alloc = to_sav * w
        docs = list(db.collection("savings_pockets")
                    .where(filter=FieldFilter("name","==",name))
                    .stream())
        if not docs: continue
        ref = docs[0]; d = ref.to_dict()
        bal = float(d.get("current_balance",0.0)); tgt = d.get("target_amount")
        if name in ("Savings","INVEST"):
            pay = alloc
        else:
            need = max((tgt or 0.0) - bal, 0.0)
            pay = min(alloc, need)
        if pay>0:
            db.collection("savings_pockets").document(ref.id).update({
                "current_balance": firestore.Increment(pay)
            })
        sav_dep[name] = pay

    used_sav = sum(sav_dep.values())
    debt_pool = rem * 0.30 + (to_sav - used_sav)

    # 4) Deuda Upstart
    paid_up = sum(a.to_dict().get("to_upstart",0.0)
                  for a in db.collection("allocations").stream())
    avail_up = max(UPSTART_MONTHLY_LIMIT - paid_up, 0.0)
    up_pay = min(avail_up, debt_pool)
    up_docs = list(db.collection("debts")
                   .where(filter=FieldFilter("name","==","Upstart"))
                   .stream())
    if up_docs:
        db.collection("debts").document(up_docs[0].id).update({
            "total_balance": firestore.Increment(-up_pay)
        })
    debt_left = debt_pool - up_pay

    # 5) Resto de deudas
    all_debts = db.collection("debts").stream()
    debt_docs = [
        d for d in all_debts
        if d.to_dict().get("name")!="Upstart"
           and float(d.to_dict().get("total_balance",0.0))>0.0
    ]
    total_bal = sum(float(d.to_dict().get("total_balance",0.0)) for d in debt_docs)
    debt_dep = {"Upstart": up_pay}
    for ref in debt_docs:
        data = ref.to_dict(); bal = float(data["total_balance"])
        pay = min((bal/total_bal)*debt_left if total_bal>0 else 0.0, bal)
        if pay>0:
            db.collection("debts").document(ref.id).update({
                "total_balance": firestore.Increment(-pay)
            })
        debt_dep[data["name"]] = pay

    # 6) Guardar asignación
    db.collection("allocations").add({
        "income_id":        inc_id,
        "to_expenses":      to_exp,
        "to_upstart":       up_pay,
        "to_debts":         sum(v for k,v in debt_dep.items() if k!="Upstart"),
        "to_savings_car":    sav_dep.get("CAR",0.0),
        "to_savings_rent":   sav_dep.get("RENT",0.0),
        "to_savings_invest": sav_dep.get("INVEST",0.0),
        "to_other":          sav_dep.get("Savings",0.0),
        "debt_details":     debt_dep
    })
    return to_exp, sav_dep, debt_dep

def main():
    if "month_idx" not in st.session_state:
        st.session_state.month_idx = datetime.now().month
    st.title("🗂️ Gestor de Finanzas Semanales")
    mes = MONTH_NAMES[(st.session_state.month_idx-1)%12]
    st.markdown(f"## Mes: **{mes}**")

    if st.sidebar.button("Iniciar Nuevo Mes"):
        for a in db.collection("allocations").stream():
            db.collection("allocations").document(a.id).delete()
        st.session_state.month_idx = (st.session_state.month_idx%12)+1
        st.sidebar.success(f"✅ Reiniciado a {MONTH_NAMES[st.session_state.month_idx-1]}")

    inc = st.sidebar.number_input("Monto recibido esta semana", min_value=0.0, step=10.0)
    if st.sidebar.button("Distribuir Ingreso"):
        to_exp, sav_dep, debt_dep = allocate_income(inc)
        st.sidebar.write(f"- **Gasto Fijo**: {format_money(to_exp)}")
        for k,v in sav_dep.items():
            st.sidebar.write(f"- **Ahorro {k}**: {format_money(v)}")
        st.sidebar.write(f"- **Pago Deudas Total**: {format_money(sum(v for k,v in debt_dep.items() if k!='Upstart'))}")
        st.sidebar.write("**Detalle Deudas:**")
        for k,v in debt_dep.items():
            st.sidebar.write(f"  - {k}: {format_money(v)}")

    st.subheader("📌 GASTOS FIJOS")
    allocs = list(db.collection("allocations").stream())
    spent = sum(a.to_dict().get("to_expenses",0.0) for a in allocs)
    last_exp = allocs[-1].to_dict().get("to_expenses",0.0) if allocs else 0.0
    falt = max(FIXED_MONTHLY_META - spent,0.0)
    df_fixed = pd.DataFrame([{
        "Descripción":"Gasto Fijo Mensual",
        "Monto Meta":FIXED_MONTHLY_META,
        "Dinero Actual":spent,
        "Último Depósito":last_exp,
        "Faltante":falt
    }])
    for col in df_fixed.columns[1:]:
        df_fixed[col] = df_fixed[col].map(format_money)
    st.table(df_fixed)

    st.subheader("💰 AHORROS")
    last_vals = allocs[-1].to_dict() if allocs else {}
    rows = []
    for s in db.collection("savings_pockets").stream():
        d = s.to_dict()
        name, bal, tgt = d["name"], float(d["current_balance"]), d.get("target_amount")
        key = f"to_savings_{name.lower()}"
        last_dep = last_vals.get(key,0.0)
        falt_sav = "" if tgt is None else format_money(max(tgt-bal,0.0))
        rows.append({
            "Descripción":name,
            "Monto Meta":"" if tgt is None else format_money(tgt),
            "Dinero Actual":format_money(bal),
            "Último Depósito":format_money(last_dep),
            "Faltante":falt_sav
        })
    st.table(pd.DataFrame(rows))

    st.subheader("💳 TARJETAS DE CRÉDITO")
    last_details = allocs[-1].to_dict().get("debt_details",{}) if allocs else {}
    rows = []
    for dref in db.collection("debts").stream():
        d = dref.to_dict()
        name, bal = d["name"], float(d["total_balance"])
        paid_total = sum(a.to_dict().get("debt_details",{}).get(name,0.0) for a in allocs)
        last_dep = last_details.get(name,0.0)
        initial = paid_total + bal
        rows.append({
            "Descripción":name,
            "Monto Meta":format_money(initial),
            "Dinero Actual":format_money(paid_total),
            "Último Depósito":format_money(last_dep),
            "Faltante":format_money(bal)
        })
    st.table(pd.DataFrame(rows))

if __name__ == "__main__":
    main()
