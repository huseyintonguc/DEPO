"""
Depo Yönetimi v6 — Ürün Adına/Koduna Göre Arama + Rapor Tarih Filtresi
---------------------------------------------------------------------
- Giriş/Çıkış formunda **Ürün Ara** kutusu (ad veya kod ile filtreleyip seç)
- Rapor sayfasında **Başlangıç / Bitiş** tarih filtresi + özet metrikler
- Drive (Google Sheets/XLSX) ile iki yönlü: ürünler okunur, hareketler yazılır

Gereken paketler:
    pip install streamlit pandas openpyxl google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib

Çalıştırma:
    streamlit run depo_app_v6.py

Secrets (.streamlit/secrets.toml):
[gdrive]
file_id = "<Drive dosya ID veya link>"

[gdrive.service_account]
# Service account JSON alanlarınız (Drive API yetkili)
# ...
"""

import io
from io import BytesIO
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import re

import pandas as pd
import streamlit as st

# Saat dilimi (secrets'tan ayarlanabilir)
DEFAULT_TZ = "Europe/Istanbul"
TZ = st.secrets.get("app", {}).get("timezone", DEFAULT_TZ)

# Google Drive API
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# -------------------------------------------------
# Sabitler
# -------------------------------------------------
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
LOCAL_FILE = DATA_DIR / "depo_drive_cache.xlsx"  # geçici yerel kopya
SHEET_PRODUCTS = "urunler"
SHEET_MOVES = "hareketler"

PRODUCT_COLUMNS = ["urun_kodu", "urun_adi"]
MOVE_COLUMNS = ["tarih", "kayit_zamani", "islem_turu", "urun_kodu", "urun_adi", "miktar", "birim", "aciklama"]

# -------------------------------------------------
# Drive yardımcıları
# -------------------------------------------------

def _get_service():
    if "gdrive" not in st.secrets or "service_account" not in st.secrets["gdrive"]:
        return None, "Google Drive servis hesabı (gdrive.service_account) eksik."
    sa_info = dict(st.secrets["gdrive"]["service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=[
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive",
    ])
    service = build("drive", "v3", credentials=creds)
    return service, None


def _extract_id(s: str) -> str:
    s = (s or "").strip()
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", s) or re.search(r"id=([a-zA-Z0-9_-]+)", s)
    return m.group(1) if m else s


def download_drive_excel(file_id: str, out_path: Path) -> bool:
    service, err = _get_service()
    if err:
        st.error(err); return False
    meta = service.files().get(fileId=file_id, fields="id,name,mimeType").execute()
    mime = meta.get("mimeType", "")
    buf = BytesIO()
    if mime == "application/vnd.google-apps.spreadsheet":
        req = service.files().export(fileId=file_id, mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        buf.write(req.execute()); buf.seek(0)
    else:
        req = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        buf.seek(0)
    with open(out_path, "wb") as f:
        f.write(buf.read())
    return True


def upload_drive_excel(file_id: str, src_path: Path) -> bool:
    service, err = _get_service()
    if err:
        st.error(err); return False
    media = MediaFileUpload(str(src_path), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", resumable=True)
    service.files().update(fileId=file_id, media_body=media).execute()
    return True

# -------------------------------------------------
# Excel yardımcıları
# -------------------------------------------------

def load_book(xlsx_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not xlsx_path.exists():
        return pd.DataFrame(columns=PRODUCT_COLUMNS), pd.DataFrame(columns=MOVE_COLUMNS)
    xls = pd.ExcelFile(xlsx_path)
    urunler = pd.read_excel(xls, SHEET_PRODUCTS) if SHEET_PRODUCTS in xls.sheet_names else pd.DataFrame(columns=PRODUCT_COLUMNS)
    hareketler = pd.read_excel(xls, SHEET_MOVES) if SHEET_MOVES in xls.sheet_names else pd.DataFrame(columns=MOVE_COLUMNS)
    for c in PRODUCT_COLUMNS:
        if c not in urunler.columns:
            urunler[c] = pd.Series(dtype=object)
    for c in MOVE_COLUMNS:
        if c not in hareketler.columns:
            hareketler[c] = pd.Series(dtype=object)
    return urunler[PRODUCT_COLUMNS], hareketler[MOVE_COLUMNS]


def save_book(xlsx_path: Path, urunler: pd.DataFrame, hareketler: pd.DataFrame):
    with pd.ExcelWriter(xlsx_path) as w:
        urunler.to_excel(w, sheet_name=SHEET_PRODUCTS, index=False)
        hareketler.to_excel(w, sheet_name=SHEET_MOVES, index=False)

# -------------------------------------------------
# Stok hesaplama (net)
# -------------------------------------------------

def hesapla_stok(moves: pd.DataFrame) -> pd.DataFrame:
    if moves.empty:
        return pd.DataFrame(columns=["urun_kodu", "urun_adi", "stok_miktar", "birim"])
    t = moves.copy()
    t["sign"] = t["islem_turu"].astype(str).str.lower().str.startswith("giriş").astype(int).replace({1:1,0:-1})
    t["net"] = pd.to_numeric(t["miktar"], errors="coerce").fillna(0.0) * t["sign"]
    grp = t.groupby(["urun_kodu", "urun_adi", "birim"], as_index=False)["net"].sum().rename(columns={"net":"stok_miktar"})
    return grp

# -------------------------------------------------
# UI
# -------------------------------------------------

st.set_page_config(page_title="Depo Yönetimi v6", page_icon="📦", layout="wide")
st.title("📦 Depo Yönetimi v6 — Drive Üzerinden")

FILE_ID_RAW = st.secrets.get("gdrive", {}).get("file_id", "").strip()
FILE_ID = _extract_id(FILE_ID_RAW)
if not FILE_ID:
    st.error("Lütfen .streamlit/secrets.toml içine [gdrive] file_id =  ekleyin (Drive dosya ID veya link).")
    st.stop()

with st.sidebar:
    page = st.radio("Menü", ["Giriş/Çıkış", "Ürünler (Drive)", "Stok", "Rapor"], index=0)
    st.caption("Ürün arama ve rapor tarih filtresi eklendi.")

# En güncel defteri indir
if not download_drive_excel(FILE_ID, LOCAL_FILE):
    st.stop()

urunler_df, hareket_df = load_book(LOCAL_FILE)

# ---------------- Ürünler ----------------
if page == "Ürünler (Drive)":
    st.subheader("🧾 Ürünler (Drive)")
    st.dataframe(urunler_df, use_container_width=True, hide_index=True)

# ---------------- Giriş/Çıkış ----------------
elif page == "Giriş/Çıkış":
    st.subheader("🔁 Giriş / Çıkış")
    if urunler_df.empty:
        st.warning("Drive Excel'de ürün bulunamadı. 'urunler' sayfasında 'urun_kodu' ve 'urun_adi' kolonları olduğundan emin olun.")
    else:
        # Ürün arama filtresi (ad/kod)
        search = st.text_input("🔎 Ürün Ara (Ad veya Kod)", placeholder="ör. vida, 1002, filtre...")
        fdf = urunler_df.copy()
        if search:
            s = search.strip().lower()
            fdf = fdf[fdf.apply(lambda r: s in str(r["urun_kodu"]).lower() or s in str(r["urun_adi"]).lower(), axis=1)]
            if fdf.empty:
                st.info("Aramanızla eşleşen ürün yok, tüm ürünler listelendi.")
                fdf = urunler_df
        # Seçim etiketlerini "kod — ad" yap
        fdf = fdf.assign(label=fdf["urun_kodu"].astype(str) + " — " + fdf["urun_adi"].astype(str))
        code_from_label = dict(zip(fdf["label"], fdf["urun_kodu"].astype(str)))
        name_from_code = dict(zip(urunler_df["urun_kodu"].astype(str), urunler_df["urun_adi"].astype(str)))

        with st.form("move_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                islem = st.selectbox("İşlem Türü", ["Giriş", "Çıkış"], index=0)
                sel = st.selectbox("Ürün", options=fdf["label"].tolist())
                urun_kodu = code_from_label.get(sel, "")
                urun_adi = name_from_code.get(urun_kodu, "")
                miktar = st.number_input("Miktar *", min_value=0.0, step=1.0)
                birim = st.selectbox("Birim", ["Adet", "Kutu", "Kg", "Metre", "Litre", "Paket"], index=0)
            with c2:
                aciklama = st.text_area("Açıklama", placeholder="Opsiyonel")
                tarih_val = st.date_input("Tarih", value=date.today(), format="DD.MM.YYYY")
                st.caption("Kaydet dediğiniz anda dakika zaman damgası eklenip Drive'a yazılır.")
            submitted = st.form_submit_button("Kaydet ve Drive'a Yaz")

        if submitted:
            stok = hesapla_stok(hareket_df)
            mevcut_map = dict(zip(stok["urun_kodu"].astype(str), stok["stok_miktar"].astype(float)))
            if islem == "Çıkış":
                mevcut = float(mevcut_map.get(urun_kodu, 0.0))
                if miktar > mevcut:
                    st.error(f"Yetersiz stok. Mevcut: {mevcut}")
                    st.stop()
            now_str = datetime.now(ZoneInfo(TZ)).strftime("%Y-%m-%d %H:%M")
            yeni = {
                "tarih": pd.to_datetime(tarih_val),
                "kayit_zamani": now_str,
                "islem_turu": islem,
                "urun_kodu": urun_kodu,
                "urun_adi": urun_adi,
                "miktar": float(miktar),
                "birim": birim,
                "aciklama": aciklama.strip(),
            }
            hareket_df = pd.concat([hareket_df, pd.DataFrame([yeni])], ignore_index=True)
            save_book(LOCAL_FILE, urunler_df, hareket_df)
            ok = upload_drive_excel(FILE_ID, LOCAL_FILE)
            if ok:
                st.success("Kayıt eklendi ve Drive Excel güncellendi. ⛅")
            else:
                st.warning("Drive güncellenemedi, daha sonra tekrar deneyin.")

    st.divider()
    st.subheader("Son Hareketler")
    st.dataframe(hareket_df.sort_values(["tarih", "kayit_zamani"], ascending=False), use_container_width=True, hide_index=True)

# ---------------- Stok ----------------
elif page == "Stok":
    st.subheader("📊 Net Stok (Giriş − Çıkış)")
    stok_df = hesapla_stok(hareket_df)
    if stok_df.empty:
        z = urunler_df.copy(); z["stok_miktar"] = 0.0; z["birim"] = "Adet"
        goster = z[["urun_kodu", "urun_adi", "stok_miktar", "birim"]]
    else:
        goster = stok_df
    st.dataframe(goster, use_container_width=True, hide_index=True)
    b = io.BytesIO(); goster.to_excel(b, index=False)
    st.download_button("Stok Excel İndir", data=b.getvalue(), file_name="stok_listesi.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------- Rapor ----------------
elif page == "Rapor":
    st.subheader("📅 Rapor")
    df = hareket_df.copy()
    if not df.empty:
        # Tarih filtreleri
        df["tarih_only"] = pd.to_datetime(df["tarih"], errors="coerce").dt.date
        today = date.today()
        vars_start = (df["tarih_only"].min() or today.replace(day=1))
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Başlangıç", value=vars_start)
        with c2:
            end = st.date_input("Bitiş", value=today)

        # Ürün filtresi (opsiyonel): "Tümü" + "kod — ad"
        prod_labels = (urunler_df.assign(label=urunler_df["urun_kodu"].astype(str) + " — " + urunler_df["urun_adi"].astype(str))
                                   if not urunler_df.empty else
                                   df.assign(label=df["urun_kodu"].astype(str) + " — " + df["urun_adi"].astype(str)))
        label_to_code = dict(zip(prod_labels["label"], prod_labels["urun_kodu"].astype(str)))
        options = ["Tümü"] + list(prod_labels["label"].unique())
        selected_label = st.selectbox("Ürün (opsiyonel)", options)
        selected_code = label_to_code.get(selected_label, None)

        # Filtre uygula
        mask = (df["tarih_only"] >= start) & (df["tarih_only"] <= end)
        if selected_code:
            mask = mask & (df["urun_kodu"].astype(str) == str(selected_code))
        rapor = df.loc[mask].drop(columns=["tarih_only"]) if "tarih_only" in df else df.loc[mask]

        # Sonuçlar
        st.write(f"Seçili aralıkta {len(rapor)} hareket")
        st.dataframe(rapor.sort_values(["tarih", "kayit_zamani"], ascending=False), use_container_width=True, hide_index=True)

        # Özet metrikler (seçime göre)
        giris_top = pd.to_numeric(rapor.loc[rapor["islem_turu"]=="Giriş", "miktar"], errors="coerce").sum()
        cikis_top = pd.to_numeric(rapor.loc[rapor["islem_turu"]=="Çıkış", "miktar"], errors="coerce").sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Toplam Giriş", f"{giris_top}")
        m2.metric("Toplam Çıkış", f"{cikis_top}")
        m3.metric("Net", f"{giris_top - cikis_top}")

        # İndir
        buf = io.BytesIO(); rapor.to_excel(buf, index=False)
        st.download_button("Raporu Excel İndir", data=buf.getvalue(), file_name="depo_raporu.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.caption("Hareket kaydı yok.")
