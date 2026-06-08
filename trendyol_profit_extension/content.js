// content.js
(function() {
    // Arayüzün zaten eklenip eklenmediğini kontrol et
    if (document.getElementById('ty-profit-calculator')) return;

    // HTML Yapısını Oluştur
    const container = document.createElement('div');
    container.id = 'ty-profit-calculator';

    container.innerHTML = `
        <div id="ty-profit-header">
            <span>₺ Kâr Asistanı</span>
            <button id="ty-profit-toggle">_</button>
        </div>
        <div id="ty-profit-body">
            <div class="ty-profit-input-group">
                <label>Satış Fiyatı (₺)</label>
                <input type="number" id="ty-price" value="0" step="0.01">
            </div>
            <div class="ty-profit-input-group">
                <label>Ürün Maliyeti (₺)</label>
                <input type="number" id="ty-cost" value="0" step="0.01">
            </div>
            <div style="display: flex; gap: 10px;">
                <div class="ty-profit-input-group" style="flex: 1;">
                    <label>Komisyon (%)</label>
                    <input type="number" id="ty-commission-rate" value="15" step="0.1">
                </div>
                <div class="ty-profit-input-group" style="flex: 1;">
                    <label>KDV (%)</label>
                    <input type="number" id="ty-tax-rate" value="20" step="1">
                </div>
            </div>
            <div class="ty-profit-input-group">
                <label>Kargo Ücreti (₺)</label>
                <input type="number" id="ty-shipping" value="0" step="0.01">
            </div>

            <div class="ty-profit-divider"></div>

            <div class="ty-profit-result-row">
                <span>Komisyon Tutarı:</span>
                <span id="ty-commission-cost">0.00 ₺</span>
            </div>
            <div class="ty-profit-result-row">
                <span>KDV Tutarı:</span>
                <span id="ty-tax-cost">0.00 ₺</span>
            </div>

            <div class="ty-profit-divider"></div>

            <div class="ty-profit-result-row" style="align-items: center;">
                <strong>Net Kâr:</strong>
                <span id="ty-profit-net" class="ty-profit-positive">0.00 ₺</span>
            </div>
            <div class="ty-profit-result-row" style="justify-content: flex-end;">
                <span id="ty-profit-margin" style="font-size: 11px; color: #666;">Marj: %0.00</span>
            </div>
        </div>
    `;

    document.body.appendChild(container);

    // Element Seçimleri
    const toggleBtn = document.getElementById('ty-profit-toggle');
    const bodyDiv = document.getElementById('ty-profit-body');
    const inputs = container.querySelectorAll('input');

    // Gizle/Göster (Minimize)
    toggleBtn.addEventListener('click', () => {
        if (bodyDiv.style.display === 'none') {
            bodyDiv.style.display = 'flex';
            toggleBtn.innerText = '_';
        } else {
            bodyDiv.style.display = 'none';
            toggleBtn.innerText = '□';
        }
    });

    // Hesaplama Fonksiyonu (Plan Adım 5: Hesaplama Mantığı)
    function calculateProfit() {
        const price = parseFloat(document.getElementById('ty-price').value) || 0;
        const cost = parseFloat(document.getElementById('ty-cost').value) || 0;
        const commissionRate = parseFloat(document.getElementById('ty-commission-rate').value) || 0;
        const taxRate = parseFloat(document.getElementById('ty-tax-rate').value) || 0;
        const shipping = parseFloat(document.getElementById('ty-shipping').value) || 0;

        // Komisyon hesaplama
        const commissionCost = price * (commissionRate / 100);

        // KDV hesaplama (Satış fiyatı üzerinden iç yüzde hesabı: Fiyat - (Fiyat / (1+KDV)))
        // Veya doğrudan basit KDV hesabı: (Satış Fiyatı * KDV Oranı) / (100 + KDV Oranı)
        // Türkiye'de genelde iç kdv böyle hesaplanır
        const taxCost = price - (price / (1 + (taxRate / 100)));

        // Toplam Gider
        const totalExpenses = cost + commissionCost + shipping + taxCost;

        // Net Kâr
        const netProfit = price - totalExpenses;

        // Kâr Marjı (%)
        const profitMargin = price > 0 ? (netProfit / price) * 100 : 0;

        // UI Güncelleme
        document.getElementById('ty-commission-cost').innerText = commissionCost.toFixed(2) + ' ₺';
        document.getElementById('ty-tax-cost').innerText = taxCost.toFixed(2) + ' ₺';

        const netElement = document.getElementById('ty-profit-net');
        netElement.innerText = netProfit.toFixed(2) + ' ₺';

        if (netProfit < 0) {
            netElement.className = 'ty-profit-negative';
        } else {
            netElement.className = 'ty-profit-positive';
        }

        document.getElementById('ty-profit-margin').innerText = 'Marj: %' + profitMargin.toFixed(2);
    }

    // Girdiler değiştikçe otomatik hesapla
    inputs.forEach(input => {
        input.addEventListener('input', calculateProfit);
    });

})();
