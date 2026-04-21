import streamlit as st
import pandas as pd
import json
import base64
import requests
import os
from datetime import datetime
from pathlib import Path

# --- Sabitler ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "trendyol_products_cache.json"

st.set_page_config(page_title="Trendyol Stok Kapananlar Raporu", page_icon="🛍️", layout="wide")

# --- UI ve Kimlik Bilgileri ---
st.title("🛍️ Trendyol Stok Kapananlar Raporu")
st.markdown("Bir önceki gün ile karşılaştırma yaparak **stoğu biten (kapanan)** ürünleri listeler.")

# Secrets veya form üzerinden bilgileri al
if "trendyol" in st.secrets:
    ty_secrets = st.secrets["trendyol"]
    DEFAULT_SELLER_ID = ty_secrets.get("seller_id", "")
    DEFAULT_API_KEY = ty_secrets.get("api_key", "")
    DEFAULT_API_SECRET = ty_secrets.get("api_secret", "")
else:
    DEFAULT_SELLER_ID = ""
    DEFAULT_API_KEY = ""
    DEFAULT_API_SECRET = ""

with st.sidebar:
    st.header("🔑 API Bilgileri")
    seller_id = st.text_input("Satıcı ID (Seller ID)", value=DEFAULT_SELLER_ID)
    api_key = st.text_input("API Key", value=DEFAULT_API_KEY, type="password")
    api_secret = st.text_input("API Secret", value=DEFAULT_API_SECRET, type="password")

if not seller_id or not api_key or not api_secret:
    st.warning("Devam etmek için sol menüden Trendyol API bilgilerini giriniz.")
    st.stop()

# --- API Yardımcı Fonksiyonlar ---
def get_auth_header(api_key, api_secret):
    credentials = f"{api_key}:{api_secret}"
    encoded = base64.b64encode(credentials.encode()).decode('utf-8')
    return {"Authorization": f"Basic {encoded}"}

def fetch_trendyol_products(seller_id, api_key, api_secret):
    url = f"https://apigw.trendyol.com/integration/product/sellers/{seller_id}/products"
    headers = get_auth_header(api_key, api_secret)
    # User-Agent is strictly required by Trendyol API
    headers["User-Agent"] = f"{seller_id} - SelfIntegration"

    all_products = []
    page = 0
    size = 100 # Maksimum 100 veya daha fazla destekliyor olabilir, 100 güvenli

    progress_text = "Trendyol'dan ürünler çekiliyor..."
    bar = st.progress(0, text=progress_text)

    try:
        while True:
            params = {
                "page": page,
                "size": size,
                "approved": "true", # Sadece onaylı ürünler
                "archived": "false" # Arşivlenmiş olanları dahil etme
            }
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                st.error(f"API Hatası: {response.status_code} - {response.text}")
                return None

            data = response.json()
            content = data.get("content", [])
            all_products.extend(content)

            total_pages = data.get("totalPages", 1)

            # Progress bar'ı güncelle
            current_progress = min((page + 1) / total_pages, 1.0) if total_pages > 0 else 1.0
            bar.progress(current_progress, text=f"Sayfa {page+1} / {total_pages} çekildi...")

            if page + 1 >= total_pages or len(content) == 0:
                break

            page += 1

        bar.empty()
        return all_products
    except Exception as e:
        st.error(f"Bağlantı hatası: {str(e)}")
        return None

# --- Kıyaslama ve Rapor Mantığı ---
def load_previous_data():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_current_data(data_dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)

def compare_and_report(previous_data, current_data):
    """
    Önceki günde stoğu > 0 olan ama bugün stoğu 0 olan (veya artık listede olmayan) ürünleri bulur.
    """
    closed_products = []

    # previous_data: { barcode: { "title": ..., "quantity": ... }, ... }
    for barcode, prev_info in previous_data.items():
        prev_qty = prev_info.get("quantity", 0)

        # Sadece daha önce stoğu olan (açık olan) ürünleri kontrol et
        if prev_qty > 0:
            curr_info = current_data.get(barcode)

            # Ürün artık listede yoksa (arşive alınmış veya reddedilmiş olabilir)
            if not curr_info:
                closed_products.append({
                    "Barkod": barcode,
                    "Ürün Adı": prev_info.get("title", "Bilinmiyor"),
                    "Önceki Stok": prev_qty,
                    "Şu Anki Stok": 0,
                    "Durum": "Listeden Kaldırıldı / Arşivlendi"
                })
            else:
                curr_qty = curr_info.get("quantity", 0)
                # Ürün var ama stoğu sıfırlanmış (kapanmış)
                if curr_qty <= 0:
                     closed_products.append({
                        "Barkod": barcode,
                        "Ürün Adı": curr_info.get("title", prev_info.get("title")),
                        "Önceki Stok": prev_qty,
                        "Şu Anki Stok": curr_qty,
                        "Durum": "Stoğu Tükendi (Kapandı)"
                    })

    return closed_products


# --- Ana Uygulama Akışı ---
st.divider()

if st.button("🚀 Raporu Çalıştır ve Getir", type="primary"):
    with st.spinner("İşlem yapılıyor, lütfen bekleyin..."):
        # 1. Trendyol'dan güncel veriyi çek
        raw_products = fetch_trendyol_products(seller_id, api_key, api_secret)

        if raw_products is not None:
            # 2. Güncel veriyi sözlüğe (dictionary) çevir (hızlı arama için)
            current_data = {}
            for p in raw_products:
                bcode = str(p.get("barcode", ""))
                current_data[bcode] = {
                    "title": p.get("title", ""),
                    "quantity": p.get("quantity", 0)
                }

            # 3. Önceki günün (bir önceki çalışmanın) verisini yükle
            previous_data = load_previous_data()

            # 4. Eğer önceki veri boşsa, ilk kez çalışıyordur
            if not previous_data:
                st.info("📌 Önceki güne ait veri bulunamadı. Şu anki durum kaydedildi, bir sonraki çalıştırmada karşılaştırma yapılabilecektir.")
                save_current_data(current_data)
            else:
                # 5. Karşılaştırma yap
                closed_items = compare_and_report(previous_data, current_data)

                # 6. Sonuçları ekrana bas
                st.subheader("📋 Kapanan (Stoğu Biten) Ürünler")
                if not closed_items:
                    st.success("🎉 Harika! Dünden bugüne stoğu biten/kapanan ürün bulunmuyor.")
                else:
                    df_closed = pd.DataFrame(closed_items)
                    st.warning(f"⚠️ {len(closed_items)} adet ürünün stoğu bitmiş veya listelemesi kapanmış!")
                    st.dataframe(df_closed, use_container_width=True, hide_index=True)

                # 7. Sonucu (güncel durumu) diske kaydet ki yarın için referans olsun
                save_current_data(current_data)
                st.success("✅ Güncel stok durumları, bir sonraki karşılaştırma için kaydedildi.")
