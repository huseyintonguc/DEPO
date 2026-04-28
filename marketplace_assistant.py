import streamlit as st
import json
import requests
import base64
from datetime import datetime, date
from openai import OpenAI
import os

# Set Streamlit page config
st.set_page_config(page_title="Marketplace AI Assistant", page_icon="🤖", layout="wide")

st.title("🤖 Marketplace AI Assistant")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Merhaba! Ben pazar yeri asistanınızım. 'Trendyol'da bugün gecikene girecek sipariş kaldı mı?' gibi sorular sorabilirsiniz."}
    ]

# Sidebar for credentials
with st.sidebar:
    st.header("🔑 API Credentials")

    st.subheader("OpenAI")
    openai_api_key = st.text_input("OpenAI API Key", type="password", key="openai_key")

    st.subheader("Trendyol")
    trendyol_seller_id = st.text_input("Trendyol Seller ID", key="ty_seller_id")
    trendyol_api_key = st.text_input("Trendyol API Key", type="password", key="ty_api_key")
    trendyol_api_secret = st.text_input("Trendyol API Secret", type="password", key="ty_api_secret")

    st.markdown("---")
    st.markdown("""
    **İpucu:** Sol taraftan API bilgilerinizi giriniz.
    Bilgileriniz sadece bu oturumda kullanılır.
    """)

# Helper function to get Trendyol auth header
def get_trendyol_auth_header(api_key, api_secret):
    credentials = f"{api_key}:{api_secret}"
    encoded = base64.b64encode(credentials.encode()).decode('utf-8')
    return {"Authorization": f"Basic {encoded}"}

# Tool function: Get all order statistics from Trendyol
def get_trendyol_order_stats():
    """
    Trendyol API'ye bağlanıp siparişleri çeker. Anlık sipariş adeti,
    gecikmeye düşecek/düşmüş siparişleri ve hangi kargolara dağıtıldığını hesaplar.
    """
    if not trendyol_seller_id or not trendyol_api_key or not trendyol_api_secret:
        return json.dumps({
            "error": "Trendyol API bilgileri eksik. Lütfen sol taraftaki menüden Seller ID, API Key ve API Secret bilgilerini doldurun."
        }, ensure_ascii=False)

    url = f"https://apigw.trendyol.com/integration/order/sellers/{trendyol_seller_id}/orders"
    headers = get_trendyol_auth_header(trendyol_api_key, trendyol_api_secret)

    all_orders = []
    page = 0
    size = 100

    try:
        while True:
            # Kullanıcının talebi üzerine tüm operasyonel, kargo ve iade durumlarını kapsayacak statüler
            params = {
                "status": "Created,Picking,Invoiced,Shipped,Delivered,UnDelivered,Returned,Cancelled",
                "page": page,
                "size": size
            }
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                return json.dumps({
                    "error": f"Trendyol API Hatası: HTTP {response.status_code} - {response.text}"
                }, ensure_ascii=False)

            data = response.json()
            content = data.get("content", [])
            all_orders.extend(content)

            total_pages = data.get("totalPages", 1)

            if page + 1 >= total_pages or len(content) == 0:
                break

            page += 1

        total_orders_fetched = len(all_orders)
        delayed_orders_count = 0
        cargo_distribution = {}
        status_distribution = {}
        total_revenue = 0.0
        product_sales_freq = {}
        today = date.today()

        for order in all_orders:
            status = order.get("status", "Unknown")

            # Statü dağılımı (Açık, Bekleyen, Kargoda, Teslim Edildi, İade vb. için)
            if status in status_distribution:
                status_distribution[status] += 1
            else:
                status_distribution[status] = 1

            # Sadece iptal/iade olmayan siparişlerin cirosunu hesapla
            if status not in ["Cancelled", "Returned", "UnDelivered"]:
                total_price = order.get("totalPrice", 0.0)
                total_revenue += float(total_price)

            # Gecikenleri/SLA riskli olanları hesapla (Sadece aktif gönderim bekleyenler için)
            if status in ["Created", "Picking", "Invoiced"]:
                agreed_delivery_ms = order.get("agreedDeliveryDate")
                if agreed_delivery_ms:
                    delivery_date = datetime.fromtimestamp(agreed_delivery_ms / 1000.0).date()
                    if delivery_date <= today:
                        delayed_orders_count += 1

            # Kargo şirketlerini hesapla
            cargo_provider = order.get("cargoProviderName", "Bilinmeyen Kargo")
            if cargo_provider in cargo_distribution:
                cargo_distribution[cargo_provider] += 1
            else:
                cargo_distribution[cargo_provider] = 1

            # En çok satan ürünleri hesapla
            for line in order.get("lines", []):
                product_name = line.get("productName", "Bilinmeyen Ürün")
                quantity = line.get("quantity", 0)
                if product_name in product_sales_freq:
                    product_sales_freq[product_name] += quantity
                else:
                    product_sales_freq[product_name] = quantity

        # En çok satan ilk 5 ürünü bul
        top_selling_products = sorted(product_sales_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        top_selling_products_list = [{"productName": k, "quantity": v} for k, v in top_selling_products]

        # Sadece açık/bekleyen (kargolanmamış) statülerin toplamı
        open_orders_count = sum(v for k, v in status_distribution.items() if k in ["Created", "Picking", "Invoiced"])

        summary = {
            "total_orders_fetched": total_orders_fetched,
            "open_and_pending_orders_count": open_orders_count,
            "delayed_orders_count": delayed_orders_count, # SLA raporu için
            "order_status_distribution": status_distribution, # Kargo, teslimat ve iade statüleri
            "cargo_distribution": cargo_distribution,
            "total_revenue": round(total_revenue, 2),
            "top_selling_products": top_selling_products_list,
            "message": f"Sistemden {total_orders_fetched} adet sipariş çekildi. {open_orders_count} adet açık/bekleyen sipariş var. {delayed_orders_count} tanesi gecikme riski taşıyor. Toplam geçerli ciro {round(total_revenue, 2)} TL."
        }

        return json.dumps(summary, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"Beklenmeyen bir hata oluştu: {str(e)}"
        }, ensure_ascii=False)


# Tool function: Get all product statistics from Trendyol
def get_trendyol_product_stats():
    """
    Trendyol API'ye bağlanıp ürünleri çeker. Güncel aktif ürün sayısını bulur,
    önceki günle karşılaştırıp kapanan (stoku sıfırlanan vb.) ürünleri hesaplar.
    Ayrıca data/trendyol_telegram_cache.json dosyasından dünkü durumu kontrol eder.
    """
    if not trendyol_seller_id or not trendyol_api_key or not trendyol_api_secret:
        return json.dumps({
            "error": "Trendyol API bilgileri eksik. Lütfen sol taraftaki menüden Seller ID, API Key ve API Secret bilgilerini doldurun."
        }, ensure_ascii=False)

    url = f"https://apigw.trendyol.com/integration/product/sellers/{trendyol_seller_id}/products"
    headers = get_trendyol_auth_header(trendyol_api_key, trendyol_api_secret)
    headers["User-Agent"] = f"{trendyol_seller_id} - SelfIntegration"

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
                return json.dumps({
                    "error": f"Trendyol API Hatası: HTTP {response.status_code} - {response.text}"
                }, ensure_ascii=False)

            data = response.json()
            content = data.get("content", [])
            all_products.extend(content)

            total_pages = data.get("totalPages", 1)

            if page + 1 >= total_pages or len(content) == 0:
                break

            page += 1

        current_active_products_count = sum(1 for p in all_products if p.get("quantity", 0) > 0)
        total_products_count = len(all_products)

        # Dünkü verileri kontrol et
        previous_data = {}

        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        cache_file = os.path.join("data", f"trendyol_cache_{trendyol_seller_id}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    previous_data = json.load(f)
            except Exception:
                pass

        yesterday_active_count = sum(1 for p in previous_data.values() if p.get("quantity", 0) > 0)

        # Güncel veriyi sözlüğe çevir (barkoda göre) ve kritik stoku hesapla
        current_data_dict = {}
        low_stock_products = []

        for p in all_products:
            barcode = str(p.get("barcode", ""))
            qty = p.get("quantity", 0)
            title = p.get("title", "Bilinmeyen Ürün")

            current_data_dict[barcode] = {
                "title": title,
                "quantity": qty,
                "productCode": p.get("productCode", ""),
                "stockCode": p.get("stockCode", ""),
            }

            # Kritik stok (0'dan büyük, 5 veya daha az ise)
            if 0 < qty <= 5:
                low_stock_products.append({"title": title, "quantity": qty, "barcode": barcode})

        # Kritik stoklu ürünleri adedine göre sırala (azdan çoğa)
        low_stock_products = sorted(low_stock_products, key=lambda x: x["quantity"])

        closed_products_count = 0
        closed_product_titles = []

        if previous_data:
            for barcode, prev_info in previous_data.items():
                prev_qty = prev_info.get("quantity", 0)
                if prev_qty > 0:
                    curr_info = current_data_dict.get(barcode)
                    if not curr_info or curr_info.get("quantity", 0) <= 0:
                        closed_products_count += 1
                        closed_product_titles.append(prev_info.get("title", "Bilinmeyen Ürün"))

        summary = {
            "total_products": total_products_count,
            "current_active_products": current_active_products_count,
            "yesterday_active_products": yesterday_active_count if previous_data else "Bilinmiyor",
            "closed_products_count_today": closed_products_count,
            "closed_product_examples": closed_product_titles[:5], # Sadece ilk 5 örneği göster
            "low_stock_products_count": len(low_stock_products),
            "low_stock_product_examples": low_stock_products[:10] # İlk 10 örneği göster
        }

        # Güncel veriyi kaydet ki yarına kullanılsın
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(current_data_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Sadece konsola yaz, ana akışı bozma
            print(f"Veriler kaydedilirken hata oluştu: {e}")

        return json.dumps(summary, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"Beklenmeyen bir hata oluştu: {str(e)}"
        }, ensure_ascii=False)

# Tool function: Get all claim/return statistics from Trendyol
def get_trendyol_return_stats():
    """
    Trendyol API'ye bağlanıp iade/talep (claims) verilerini çeker.
    İade nedenlerinin dağılımını analiz ederek NLP ve Müşteri Raporları için zemin hazırlar.
    """
    if not trendyol_seller_id or not trendyol_api_key or not trendyol_api_secret:
        return json.dumps({
            "error": "Trendyol API bilgileri eksik. Lütfen sol taraftaki menüden Seller ID, API Key ve API Secret bilgilerini doldurun."
        }, ensure_ascii=False)

    url = f"https://apigw.trendyol.com/integration/claims/sellers/{trendyol_seller_id}/claims"
    headers = get_trendyol_auth_header(trendyol_api_key, trendyol_api_secret)

    all_claims = []
    # Maksimum limitli çekim (örnek olarak ilk sayfalar veya status verilerek)
    params = {
        "size": 200, # Claims servisi genellikle 200 döner
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        # Eğer bu endpoint seller'da yetkili değilse veya yanlışsa hata dön
        if response.status_code != 200:
            return json.dumps({
                "error": f"Trendyol İade API Hatası: HTTP {response.status_code}. (Yetki veya endpoint hatası olabilir)",
                "details": response.text
            }, ensure_ascii=False)

        data = response.json()
        content = data.get("content", [])

        total_claims = len(content)
        reason_distribution = {}
        status_distribution = {}

        for claim in content:
            # İade nedenlerini topla
            reason = claim.get("customerReason", claim.get("reason", "Bilinmeyen Neden"))
            if reason in reason_distribution:
                reason_distribution[reason] += 1
            else:
                reason_distribution[reason] = 1

            # İade statüleri
            status = claim.get("claimStatus", "Bilinmeyen Statü")
            if status in status_distribution:
                status_distribution[status] += 1
            else:
                status_distribution[status] = 1

        # En çok iade edilen nedenleri sırala
        top_reasons = sorted(reason_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
        top_reasons_list = [{"reason": k, "count": v} for k, v in top_reasons]

        summary = {
            "total_returns_analyzed": total_claims,
            "return_status_distribution": status_distribution,
            "top_return_reasons": top_reasons_list,
            "message": f"Toplam {total_claims} adet iade talebi analiz edildi. NLP analizi ve kalite kontrol iyileştirmeleri için 'top_return_reasons' kullanılabilir."
        }

        return json.dumps(summary, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"İade verisi çekilirken hata oluştu: {str(e)}"
        }, ensure_ascii=False)

# Tool function: Get all settlement/finance statistics from Trendyol
def get_trendyol_finance_stats():
    """
    Trendyol API'ye bağlanıp finansal mutabakat (settlement) verilerini çeker.
    Komisyon, kargo kesintisi ve net hakediş raporları için temel sağlar.
    """
    if not trendyol_seller_id or not trendyol_api_key or not trendyol_api_secret:
        return json.dumps({
            "error": "Trendyol API bilgileri eksik. Lütfen sol taraftaki menüden Seller ID, API Key ve API Secret bilgilerini doldurun."
        }, ensure_ascii=False)

    url = f"https://apigw.trendyol.com/integration/finance/sellers/{trendyol_seller_id}/settlements"
    headers = get_trendyol_auth_header(trendyol_api_key, trendyol_api_secret)

    # Tarih aralığı (örneğin son 1 ay)
    today = datetime.now()
    # Unix timestamp in milliseconds
    start_date_ms = int((today.timestamp() - (30 * 24 * 60 * 60)) * 1000)
    end_date_ms = int(today.timestamp() * 1000)

    params = {
        "startDate": start_date_ms,
        "endDate": end_date_ms,
        "size": 500
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        # Eğer bu endpoint yetkili değilse veya hata dönerse
        if response.status_code != 200:
            return json.dumps({
                "error": f"Trendyol Finans API Hatası: HTTP {response.status_code}. (Yetki veya endpoint hatası olabilir)",
                "details": response.text
            }, ensure_ascii=False)

        data = response.json()
        content = data.get("content", [])

        total_settlements = len(content)
        total_commission_deduction = 0.0
        total_shipping_deduction = 0.0
        total_net_payout = 0.0

        for settlement in content:
            # İşlem türüne göre gelir/gider hesabı (Örn: Sale, Return, Commission, Cargo vs)
            transaction_type = settlement.get("transactionType", "")
            amount = float(settlement.get("amount", 0.0))

            if transaction_type == "Sale":
                total_net_payout += amount
            elif transaction_type == "Return":
                total_net_payout -= abs(amount) # İade tutarı düşülür
            elif transaction_type in ["Commission", "DiscountCommission"]:
                total_commission_deduction += abs(amount)
                total_net_payout -= abs(amount)
            elif transaction_type in ["Cargo", "Shipping"]:
                total_shipping_deduction += abs(amount)
                total_net_payout -= abs(amount)
            else:
                # Diğer işlemler (Ceza, Hizmet bedeli vs) genelde eksi bakiye yazar
                total_net_payout += amount

        summary = {
            "total_finance_records_analyzed": total_settlements,
            "period": "Son 30 Gün",
            "total_commission_deduction": round(total_commission_deduction, 2),
            "total_shipping_deduction": round(total_shipping_deduction, 2),
            "estimated_net_payout": round(total_net_payout, 2),
            "message": f"Son 30 güne ait {total_settlements} finansal hareket incelendi. Tahmini net ödeme/hakediş: {round(total_net_payout, 2)} TL, Toplam Kesilen Komisyon: {round(total_commission_deduction, 2)} TL, Toplam Kargo Kesintisi: {round(total_shipping_deduction, 2)} TL."
        }

        return json.dumps(summary, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"Finansal veriler çekilirken hata oluştu: {str(e)}"
        }, ensure_ascii=False)

# Tool function: Get all Q&A questions from Trendyol
def get_trendyol_questions_stats():
    """
    Trendyol API'ye bağlanıp müşterilerin sorduğu soruları çeker.
    """
    if not trendyol_seller_id or not trendyol_api_key or not trendyol_api_secret:
        return json.dumps({
            "error": "Trendyol API bilgileri eksik. Lütfen sol taraftaki menüden Seller ID, API Key ve API Secret bilgilerini doldurun."
        }, ensure_ascii=False)

    url = f"https://apigw.trendyol.com/integration/messages/sellers/{trendyol_seller_id}/questions"
    headers = get_trendyol_auth_header(trendyol_api_key, trendyol_api_secret)

    params = {
        "status": "WAITING_FOR_ANSWER", # Öncelikle cevap bekleyenler
        "size": 50
    }

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return json.dumps({
                "error": f"Trendyol Soru API Hatası: HTTP {response.status_code}. (Yetki veya endpoint hatası olabilir)",
                "details": response.text
            }, ensure_ascii=False)

        data = response.json()
        content = data.get("content", [])

        total_unanswered = len(content)
        questions_list = []

        for q in content:
            questions_list.append({
                "productName": q.get("productName", "Bilinmeyen Ürün"),
                "questionText": q.get("text", ""),
                "creationDate": datetime.fromtimestamp(q.get("creationDate", 0) / 1000.0).strftime('%Y-%m-%d %H:%M') if q.get("creationDate") else ""
            })

        summary = {
            "unanswered_questions_count": total_unanswered,
            "questions": questions_list[:10], # İlk 10 tanesini göster
            "message": f"Şu anda cevap bekleyen {total_unanswered} müşteri sorusu var."
        }

        return json.dumps(summary, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"Soru verisi çekilirken hata oluştu: {str(e)}"
        }, ensure_ascii=False)


# Define the tools available to the OpenAI assistant
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_trendyol_order_stats",
            "description": "Trendyol'dan sipariş verilerini çeker. Operasyonel durumları (Açık, Bekleyen, Kargoda, Teslim edildi, İade vs.), SLA riskli geciken siparişleri, geçerli siparişlerin cirosunu, ortalama sepet tutarını, en çok satan ürünleri ve kargo dağılımını verir.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trendyol_product_stats",
            "description": "Trendyol'dan ürün verilerini çeker. Toplam/aktif ürün sayısını, satış hızını (son 24 saatlik satış), kapanan ürünleri ve kritik stok (azalan stok) seviyesindeki ürünleri verir.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trendyol_return_stats",
            "description": "Trendyol'dan iade/talep (claims) verilerini çeker. İade durumlarının dağılımını ve en sık karşılaşılan iade nedenlerini (Kusurlu ürün, görselden farklı vs. tespiti için) verir.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trendyol_finance_stats",
            "description": "Trendyol'dan finansal mutabakat verilerini çeker. Son 30 günlük toplam komisyon kesintisi, kargo kesintisi ve satıcıya ödenecek tahmini net hakedişi (net payout) verir.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trendyol_questions_stats",
            "description": "Trendyol'dan müşterilerin sorduğu cevap bekleyen soruları çeker.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# Display chat messages
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle user input
if prompt := st.chat_input("Pazar yerleri hakkında bir soru sorun (Örn: Trendyolda bugün gecikene girecek sipariş kaldı mı?)"):
    if not openai_api_key:
        st.error("Lütfen sol taraftaki menüden OpenAI API Key'inizi girin.")
    else:
        # Add user message to state and display
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Initialize OpenAI client
        client = OpenAI(api_key=openai_api_key)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("Düşünüyor...")

            # Prepare messages for API
            api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]
            api_messages.insert(0, {
                "role": "system",
                "content": "Sen pazar yerleri (Trendyol) yönetimi konusunda uzman ve kullanıcılara veri odaklı, net ve detaylı analiz raporları sunan bir asistansın. "
                           "Kullanıcı senden aşağıdaki alanlarda rapor isteyebilir:\n\n"
                           "1. **Operasyonel Raporlar (SLA ve Süreç Takibi)**: Açık ve bekleyen siparişler listesi, kargoya veriliş süresi dolmak üzere olan SLA riskli siparişler (gecikenler), siparişlerin şehirlere ve kargo firmalarına dağılımı, kargo durum ve teslimat raporu.\n"
                           "2. **Finansal Raporlar**: Tahmini net hakediş (payout), pazaryeri komisyon kesintileri, kargo kesintisi raporları ve ortalama sepet tutarı.\n"
                           "3. **Stok ve Envanter Raporları**: Kritik stok seviyesi (Out of Stock) raporu, satış hızı (velocity) analizi, güncel toplam ve aktif ürün sayıları.\n"
                           "4. **Müşteri ve İade Raporları**: İade nedenleri analiz raporu (Kusurlu ürün vs. kalite kontrol tespiti), müşteri soruları, yanıt bekleyen soruların durumu.\n\n"
                           "Bu raporları oluştururken her zaman fonksiyonları (tools) kullanarak gerçek API verilerini çek. Eğer istenen bazı metrikler (Örn: ROAS, Yorumlar) mevcut tool'lardan gelmiyorsa, API ile anlık çekilemediğini nazikçe belirt."
            })

            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=api_messages,
                    tools=tools,
                    tool_choice="auto",
                )

                response_message = response.choices[0].message
                tool_calls = response_message.tool_calls

                # Check if the model wants to call a function
                if tool_calls:
                    api_messages.append(response_message) # Extend conversation with assistant's reply

                    for tool_call in tool_calls:
                        function_name = tool_call.function.name

                        message_placeholder.markdown(f"Trendyol sistemine bağlanılıyor... (`{function_name}` çalıştırılıyor)")

                        if function_name == "get_trendyol_order_stats":
                            function_response = get_trendyol_order_stats()

                            api_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            })
                        elif function_name == "get_trendyol_product_stats":
                            function_response = get_trendyol_product_stats()

                            api_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            })
                        elif function_name == "get_trendyol_return_stats":
                            function_response = get_trendyol_return_stats()

                            api_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            })
                        elif function_name == "get_trendyol_finance_stats":
                            function_response = get_trendyol_finance_stats()

                            api_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            })
                        elif function_name == "get_trendyol_questions_stats":
                            function_response = get_trendyol_questions_stats()

                            api_messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            })

                    # Second API call with function results
                    message_placeholder.markdown("Veriler analiz ediliyor...")
                    second_response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=api_messages,
                    )

                    final_reply = second_response.choices[0].message.content
                    message_placeholder.markdown(final_reply)
                    st.session_state["messages"].append({"role": "assistant", "content": final_reply})

                else:
                    # Model didn't call any function, just normal text reply
                    final_reply = response_message.content
                    message_placeholder.markdown(final_reply)
                    st.session_state["messages"].append({"role": "assistant", "content": final_reply})

            except Exception as e:
                st.error(f"OpenAI API Hatası: {str(e)}")
                st.session_state["messages"].pop() # Remove the user message if it failed
