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
            params = {
                "status": "Created,Picking,Invoiced",
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

        total_active_orders = len(all_orders)
        delayed_orders_count = 0
        cargo_distribution = {}
        today = date.today()

        for order in all_orders:
            # Gecikenleri hesapla
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

        summary = {
            "total_active_orders": total_active_orders,
            "delayed_orders_count": delayed_orders_count,
            "cargo_distribution": cargo_distribution,
            "message": f"Toplam {total_active_orders} aktif sipariş var. {delayed_orders_count} tanesi gecikme riski taşıyor veya gecikmiş."
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
        cache_file = os.path.join("data", "trendyol_telegram_cache.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    previous_data = json.load(f)
            except Exception:
                pass

        yesterday_active_count = sum(1 for p in previous_data.values() if p.get("quantity", 0) > 0)

        # Güncel veriyi sözlüğe çevir (barkoda göre)
        current_data_dict = {}
        for p in all_products:
            barcode = str(p.get("barcode", ""))
            current_data_dict[barcode] = {
                "title": p.get("title", "Bilinmeyen Ürün"),
                "quantity": p.get("quantity", 0),
                "productCode": p.get("productCode", ""),
                "stockCode": p.get("stockCode", ""),
            }

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
            "closed_product_examples": closed_product_titles[:5] # Sadece ilk 5 örneği göster
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

# Define the tools available to the OpenAI assistant
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_trendyol_order_stats",
            "description": "Trendyol'dan sipariş verilerini çeker. Anlık sipariş adetini, gecikmeye giren/girecek sipariş sayısını ve hangi kargolara (kargo şirketleri) dağıtıldığını verir.",
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
            "description": "Trendyol'dan ürün verilerini çeker. Kaç adet ürünümüzün aktif olduğunu, dün kaç adet aktif olduğunu ve bugün stoğu bitip kapanan ürün olup olmadığını verir.",
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
                "content": "Sen pazar yerleri (Trendyol, Hepsiburada vb.) yönetimi konusunda uzman ve kullanıcılara veri odaklı, net ve detaylı analiz raporları sunan bir asistansın. Her zaman aradığın veriyi çekmek için fonkisyonları (tools) kullan. Kullanıcı sana 'bugün kapanan var mı?', 'geciken sipariş var mı?', 'kargo dağılımı nasıl?' gibi sorular sorduğunda sadece ilgili tool'lardan dönen verileri analiz et, gereksiz yorumlardan kaçın ve net sayılar/listeler ile Türkçe rapor ver."
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
