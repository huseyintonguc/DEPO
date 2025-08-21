"""
Depo Yönetimi v5 (Drive Ürün Dosyası + Anlık Yedek)
---------------------------------------------------
- Ürün listesi Google Drive'daki Excel dosyasından okunur (urunler sheet).
- Hareketler (giriş/çıkış) kaydedilir ve anında aynı Excel dosyasına yazılır.
- Her hareket saat/dakika damgası içerir (Europe/Istanbul saat dilimi).
- Tek tablo: hareketler (urun kodu, adı, miktar, açıklama, işlem, zaman).

Kurulum:
    pip install streamlit pandas openpyxl google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib pytz

Çalıştırma:
    streamlit run depo_app_v5.py
"""

import io
from datetime import datetime
import pytz
import pandas as pd
import streamlit as st

# Google Drive API
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# ---------------- Drive servis ----------------
def _get_drive_service():
    if "gdrive" not in st.secrets or "service_account" not in st.secrets["gdrive"]:
        return None, "Drive servisi yok"
    sa_info = dict(st.secrets["gdrive"]["service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=creds)
    return service, None

# ---------------- Dosya işlemleri ----------------
def download_excel(file_id: str, local_path: str):
    service, err = _get_drive_service()
    if err:
        st.error(err)
        return None
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    with open(local_path, "wb") as f:
        f.write(fh.read())
    return local_path


def upload_excel(file_id: str, local_path: str):
    service, err = _get_drive_service()
    if err:
        st.error(err)
        return
    media = MediaFileUpload(local_path, resumable=True)
    service.files().update(fileId=file_id, media_body=media).execute()
    st.success("Drive dosyası güncellendi")

# ---------------- UI ----------------
st.set_page_config(page_title="Depo Yönetimi v5", page_icon="📦", layout="wide")
st.title("📦 Depo Yönetimi v5")

# Drive dosya ID
FILE_ID = st.secrets.get("gdrive", {}).get("file_id", "").strip()
LOCAL_FILE = "data/depo_drive.xlsx"

if not FILE_ID:
    st.error("Lütfen secrets içine gdrive.file_id ekleyin.")
    st.stop()

# Dosya indir
path = download_excel(FILE_ID, LOCAL_FILE)
if not path:
    st.stop()

# Excel oku
xls = pd.ExcelFile(LOCAL_FILE)
urunler_df = pd.read_excel(xls, "urunler") if "urunler" in xls.sheet_names else pd.DataFrame(columns=["urun_kodu","urun_adi"])
hareket_df = pd.read_excel(xls, "hareketler") if "hareketler" in xls.sheet_names else pd.DataFrame(columns=["tarih","islem_turu","urun_kodu","urun_adi","miktar","aciklama"])

with st.sidebar:
    page = st.radio("Menü", ["Giriş/Çıkış", "Ürünler", "Rapor"])

# Ürünler
if page == "Ürünler":
    st.subheader("🧾 Ürünler (Drive)")
    st.dataframe(urunler_df, use_container_width=True, hide_index=True)

# Giriş/Çıkış
elif page == "Giriş/Çıkış":
    st.subheader("🔁 Giriş / Çıkış")
    if urunler_df.empty:
        st.warning("Drive Excel'de ürün yok")
    else:
        # Arama kutulu ürün seçici
        urunler_df["urun"] = urunler_df["urun_kodu"].astype(str) + " - " + urunler_df["urun_adi"]
        urun_map = dict(zip(urunler_df["urun"], zip(urunler_df["urun_kodu"], urunler_df["urun_adi"])))
        with st.form("move_form"):
            islem = st.selectbox("İşlem", ["Giriş", "Çıkış"])
            urun = st.selectbox("Ürün", urunler_df["urun"].tolist())
            urun_kodu, urun_adi = urun_map[urun]
            miktar = st.number_input("Miktar", min_value=0.0, step=1.0)
            aciklama = st.text_area("Açıklama")
            submitted = st.form_submit_button("Kaydet")
        if submitted:
            tz = st.secrets.get("app", {}).get("timezone", "Europe/Istanbul")
            now = datetime.now(pytz.timezone(tz)).strftime("%Y-%m-%d %H:%M")
            yeni = {"tarih": now, "islem_turu": islem, "urun_kodu": urun_kodu, "urun_adi": urun_adi, "miktar": miktar, "aciklama": aciklama}
            hareket_df = pd.concat([hareket_df, pd.DataFrame([yeni])], ignore_index=True)
            with pd.ExcelWriter(LOCAL_FILE) as writer:
                urunler_df.drop(columns=["urun"], errors="ignore").to_excel(writer, sheet_name="urunler", index=False)
                hareket_df.to_excel(writer, sheet_name="hareketler", index=False)
            upload_excel(FILE_ID, LOCAL_FILE)
            st.success("Kayıt eklendi ve Drive'a yedeklendi")
    st.subheader("Son Hareketler")
    st.dataframe(hareket_df.sort_values("tarih", ascending=False), use_container_width=True, hide_index=True)

# Rapor
elif page == "Rapor":
    st.subheader("📅 Rapor")
    if not hareket_df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            start_date = st.date_input("Başlangıç Tarihi", value=datetime.now().date())
        with col2:
            end_date = st.date_input("Bitiş Tarihi")
        with col3:
            urun_filter = st.selectbox("Ürün (Opsiyonel)", ["Hepsi"] + urunler_df["urun_adi"].tolist())
        
        filt = (pd.to_datetime(hareket_df["tarih"]) >= pd.to_datetime(start_date)) & (pd.to_datetime(hareket_df["tarih"]) <= pd.to_datetime(end_date))
        if urun_filter != "Hepsi":
            filt &= (hareket_df["urun_adi"] == urun_filter)
        rapor_df = hareket_df.loc[filt]

        st.dataframe(rapor_df.sort_values("tarih", ascending=False), use_container_width=True, hide_index=True)
        buf = io.BytesIO()
        rapor_df.to_excel(buf, index=False)
        st.download_button("Excel İndir", data=buf.getvalue(), file_name="rapor.xlsx")
    else:
        st.info("Henüz hareket yok")
