import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Google Sheets Bağlantısı ---
scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(credentials)

# Google Sheets
SPREADSHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
sh = client.open_by_url(SPREADSHEET_URL)
worksheet_products = sh.worksheet("Ürünler")
worksheet_logs = sh.worksheet("Günlük İşlemler")

# --- Yan Menü Logo ---
with st.sidebar:
    st.image("Artboard 3.png", width=120)
    st.markdown("### Depo Yönetimi")

# --- Üst Başlık Logo + Başlık ---
col1, col2 = st.columns([1,4])
with col1:
    st.image("Artboard 3.png", width=100)
with col2:
    st.markdown("## 📦 Depo Yönetimi v6 — Drive Üzerinden")

# --- Menü ---
menu = st.sidebar.radio("Menü", ["Giriş/Çıkış", "Rapor"])

# --- Ürünleri Yükle ---
def load_products():
    data = worksheet_products.get_all_records()
    return pd.DataFrame(data)

# --- Logları Yükle ---
def load_logs():
    data = worksheet_logs.get_all_records()
    return pd.DataFrame(data)

# --- Log Ekle ---
def add_log(product_code, product_name, hareket, miktar):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet_logs.append_row([now, product_code, product_name, hareket, miktar])

# --- Giriş / Çıkış Bölümü ---
if menu == "Giriş/Çıkış":
    st.subheader("Mal Girişi / Çıkışı")

    products_df = load_products()
    search = st.text_input("Ürün Ara (Kod veya İsim)")

    if search:
        filtered = products_df[products_df.apply(lambda row: search.lower() in str(row["Ürün Kodu"]).lower() or search.lower() in str(row["Ürün Adı"]).lower(), axis=1)]
    else:
        filtered = products_df

    product = st.selectbox("Ürün Seç", filtered["Ürün Adı"] + " (" + filtered["Ürün Kodu"] + ")")
    hareket = st.radio("Hareket Türü", ["Giriş", "Çıkış"])
    miktar = st.number_input("Miktar", min_value=1, step=1)

    if st.button("Kaydet"):
        selected_row = filtered.iloc[filtered["Ürün Adı"] + " (" + filtered["Ürün Kodu"] + ")" == product]
        product_code = selected_row["Ürün Kodu"].values[0]
        product_name = selected_row["Ürün Adı"].values[0]
        add_log(product_code, product_name, hareket, miktar)
        st.success("✅ İşlem kaydedildi ve Google Drive'a yedeklendi!")

# --- Rapor Bölümü ---
elif menu == "Rapor":
    st.subheader("📊 Raporlama")

    logs_df = load_logs()

    if not logs_df.empty:
        logs_df["Tarih"] = pd.to_datetime(logs_df["Tarih"])

        # Tarih filtresi
        start_date = st.date_input("Başlangıç Tarihi", value=datetime.today().date())
        end_date = st.date_input("Bitiş Tarihi", value=datetime.today().date())

        filtered_logs = logs_df[(logs_df["Tarih"].dt.date >= start_date) & (logs_df["Tarih"].dt.date <= end_date)]

        # Ürün filtresi
        urunler = filtered_logs["Ürün Adı"].unique().tolist()
        selected_urun = st.selectbox("Ürün Filtrele", ["Tümü"] + urunler)

        if selected_urun != "Tümü":
            filtered_logs = filtered_logs[filtered_logs["Ürün Adı"] == selected_urun]

        st.dataframe(filtered_logs)

        if not filtered_logs.empty:
            summary = filtered_logs.groupby(["Ürün Adı", "Hareket"]).agg({"Miktar": "sum"}).reset_index()
            st.write("### Özet")
            st.dataframe(summary)
    else:
        st.info("Henüz kayıt bulunmamaktadır.")
