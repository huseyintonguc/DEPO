import time
import schedule
import requests
import json
import base64
import os
import toml
import html
from pathlib import Path
from datetime import datetime

# --- Ayarlar ve Sabitler ---
SECRETS_PATH = Path(".streamlit/secrets.toml")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "trendyol_telegram_cache.json"

def load_secrets():
    # Streamlit secrets.toml kullanıyorsanız
    if SECRETS_PATH.exists():
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            return toml.load(f)
    # Proje ana dizinindeki secrets.toml'i dene
    elif Path("secrets.toml").exists():
        with open("secrets.toml", "r", encoding="utf-8") as f:
            return toml.load(f)
    return {}

secrets = load_secrets()
ty_secrets = secrets.get("trendyol", {})
# Cloud ortamları için os.environ desteği eklendi
SELLER_ID = os.environ.get("TRENDYOL_SELLER_ID") or ty_secrets.get("seller_id", "")
API_KEY = os.environ.get("TRENDYOL_API_KEY") or ty_secrets.get("api_key", "")
API_SECRET = os.environ.get("TRENDYOL_API_SECRET") or ty_secrets.get("api_secret", "")

tg_secrets = secrets.get("telegram", {})
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or tg_secrets.get("bot_token", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or tg_secrets.get("chat_id", "")
REPORT_TIME = os.environ.get("REPORT_TIME") or tg_secrets.get("report_time", "20:00") # Her gün saat kaçta çalışacağı

# --- Telegram Bot API İşlevleri ---
def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Uyarı: Telegram BOT_TOKEN veya CHAT_ID bulunamadı.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram mesajı gönderilirken hata oluştu: {e}")

def send_telegram_photo(photo_url, caption):
    if not BOT_TOKEN or not CHAT_ID:
        print("Uyarı: Telegram BOT_TOKEN veya CHAT_ID bulunamadı.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload)
        # Eğer resim url'si geçersiz veya erişilemezse normal mesaj olarak atmayı dener
        if resp.status_code != 200:
            send_telegram_message(caption + f"\n\n[Görsel Yüklenemedi: {photo_url}]")
    except Exception as e:
        print(f"Telegram resmi gönderilirken hata oluştu: {e}")

# --- Trendyol API İşlevleri ---
def get_auth_header(api_key, api_secret):
    credentials = f"{api_key}:{api_secret}"
    encoded = base64.b64encode(credentials.encode()).decode('utf-8')
    return {"Authorization": f"Basic {encoded}"}

def fetch_trendyol_products():
    if not SELLER_ID or not API_KEY or not API_SECRET:
        print("Trendyol API bilgileri eksik. Kontrol ediliyor...")
        return None

    url = f"https://apigw.trendyol.com/integration/product/sellers/{SELLER_ID}/products"
    headers = get_auth_header(API_KEY, API_SECRET)
    headers["User-Agent"] = f"{SELLER_ID} - SelfIntegration"

    all_products = []
    page = 0
    size = 100

    try:
        while True:
            params = {
                "page": page,
                "size": size,
                "approved": "true",
                "archived": "false"
            }
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Trendyol API Hatası: {response.status_code} - {response.text}")
                return None

            data = response.json()
            content = data.get("content", [])
            all_products.extend(content)

            total_pages = data.get("totalPages", 1)

            if page + 1 >= total_pages or len(content) == 0:
                break

            page += 1

        return all_products
    except Exception as e:
        print(f"Trendyol bağlantı hatası: {str(e)}")
        return None

# --- Karşılaştırma ve Kayıt İşlevleri ---
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

def extract_image_url(product):
    images = product.get("images", [])
    if images and isinstance(images, list) and len(images) > 0:
        return images[0].get("url", "")
    return ""

def process_and_report():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Günlük Trendyol stok kontrolü başlatılıyor...")

    raw_products = fetch_trendyol_products()
    if raw_products is None:
        print("Trendyol verisi çekilemediği için raporlama atlandı.")
        return

    # Güncel veriyi düzenle
    current_data = {}
    for p in raw_products:
        bcode = str(p.get("barcode", ""))
        current_data[bcode] = {
            "title": p.get("title", "Bilinmeyen Ürün"),
            "quantity": p.get("quantity", 0),
            "productCode": p.get("productCode", ""),
            "stockCode": p.get("stockCode", ""),
            "image_url": extract_image_url(p)
        }

    previous_data = load_previous_data()

    if not previous_data:
        print("Önceki veri bulunamadı. Referans için güncel veriler kaydediliyor.")
        save_current_data(current_data)
        send_telegram_message("✅ <b>Trendyol Stok Botu Devrede!</b>\nŞu anki ürünlerin listesi kaydedildi. İlk karşılaştırma yarın belirlenen saatte yapılacak.")
        return

    closed_products = []

    # Karşılaştırma yap
    for barcode, prev_info in previous_data.items():
        prev_qty = prev_info.get("quantity", 0)

        # Eğer dün (önceki çalışmada) stok 0'dan büyükse (ürün açıksa)
        if prev_qty > 0:
            curr_info = current_data.get(barcode)

            # Ürün artık dönmüyor (arşive alınmış vb.)
            if not curr_info:
                closed_products.append({
                    "type": "removed",
                    "barcode": barcode,
                    "title": prev_info.get("title"),
                    "productCode": prev_info.get("productCode", "Bilinmiyor"),
                    "image_url": prev_info.get("image_url", ""),
                    "prev_qty": prev_qty
                })
            else:
                curr_qty = curr_info.get("quantity", 0)
                # Ürünün stoğu 0 olmuş
                if curr_qty <= 0:
                     closed_products.append({
                        "type": "out_of_stock",
                        "barcode": barcode,
                        "title": curr_info.get("title", prev_info.get("title")),
                        "productCode": curr_info.get("productCode", "Bilinmiyor"),
                        "image_url": curr_info.get("image_url", ""),
                        "prev_qty": prev_qty
                    })

    # Sonuçları bildir
    if not closed_products:
        print("Kapanan (stoğu sıfırlanan) ürün bulunamadı.")
        # İsteğe bağlı olarak "Bugün kapanan ürün yok" mesajı atılabilir.
        # send_telegram_message("✅ Bugün Trendyol'da stoğu bitip kapanan ürün bulunmuyor.")
    else:
        print(f"{len(closed_products)} adet kapanan ürün bulundu. Telegram üzerinden gönderiliyor...")
        send_telegram_message(f"⚠️ <b>Trendyol'da Stoğu Biten Ürünler</b>\n\nBugün {len(closed_products)} adet ürünün listelemesi (stok bittiği için) kapandı:")

        for p in closed_products:
            safe_title = html.escape(p['title'])
            caption = (
                f"📦 <b>Ürün Adı:</b> {safe_title}\n"
                f"🏷️ <b>Ürün Kodu:</b> {p['productCode']}\n"
                f"🆔 <b>Barkod:</b> {p['barcode']}\n"
                f"📉 <b>Durum:</b> {'Arşivlendi/Listeden Kalktı' if p['type'] == 'removed' else 'Stoğu Tükendi'}"
            )

            if p.get("image_url"):
                send_telegram_photo(p["image_url"], caption)
            else:
                send_telegram_message(caption)

            # Rate limit yememek için kısa bir bekleme
            time.sleep(1)

    # Güncel durumu yarın için kaydet
    save_current_data(current_data)
    print("Karşılaştırma tamamlandı, veriler güncellendi.")

# --- Health Check Sunucusu (Cloud İçin) ---
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Health check sunucusu {port} portunda başlatıldı.")
    server.serve_forever()

# --- Zamanlayıcı (Scheduler) Akışı ---
if __name__ == "__main__":
    print(f"Trendyol Stok Botu başlatıldı. Raporlanma saati: {REPORT_TIME}")
    print("Mevcut durumu hemen kontrol etmek isterseniz (Test amaçlı), 'process_and_report()' fonksiyonunu manuel olarak çağırabilirsiniz.")

    # Cloud platformlarında (Render vb.) botun uyumaması için HTTP sunucusunu arka planda başlat
    threading.Thread(target=run_health_server, daemon=True).start()

    # İsteğe bağlı: Program ilk başladığında mevcut durumu veritabanına almasını isterseniz
    # process_and_report()

    # Her gün belirlenen saatte (örneğin 20:00) çalışması için zamanla
    schedule.every().day.at(REPORT_TIME).do(process_and_report)

    # Sürekli çalışmasını sağlayacak döngü
    while True:
        schedule.run_pending()
        time.sleep(60) # 1 dakikada bir kontrol et
