// content.js - TONGUÇ FİYAT V2

const HIZMET_BEDELI_NORMAL = 10.99;
const HIZMET_BEDELI_BUGUN  = 6.99;

// --- Local Storage Wrapper ---
const LocalDB = {
    async getProduct(modelKodu, barkod) {
        return new Promise(resolve => {
            chrome.storage.local.get(['tf_products'], (res) => {
                const db = res.tf_products || {};
                resolve(db[modelKodu] || db[barkod] || null);
            });
        });
    },
    async saveProduct(modelKodu, barkod, maliyet, desi, kdv, kargoTipi = 'hizli') {
        return new Promise(resolve => {
            chrome.storage.local.get(['tf_products'], (res) => {
                const db = res.tf_products || {};
                const data = {
                    urun_maliyeti: parseFloat(maliyet),
                    cargo_deci: parseFloat(desi),
                    kdv_orani: parseFloat(kdv),
                    kargo_tipi_manual: kargoTipi
                };
                if (modelKodu) db[modelKodu] = data;
                if (barkod) db[barkod] = data;
                chrome.storage.local.set({ tf_products: db }, () => resolve(true));
            });
        });
    }
};

// --- Format Utilities ---
function parseTL(str) {
    if (!str) return 0;
    return parseFloat(str.toString().replace(/\./g, '').replace(',', '.').replace(/[₺\s]/g, '').trim()) || 0;
}

function formatTL(val) {
    const n = Number(val || 0);
    const abs = Math.abs(n).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return n < 0 ? "-₺" + abs : "₺" + abs;
}

// --- Hesaplama Algoritması (Hardcoded Kargo Ücretleri) ---
function getCargoFeeLocal(desi, fiyat, kargoTipi) {
    // User requested "hepsi normal kargo olarak hesaplansın" and provided an Aras Kargo table.
    // The provided prices are VAT exclusive (KDV hariç). We return KDV dahil (+%20).
    let kargoKdvHaric = 0;
    const roundedDesi = Math.ceil(desi); // Desi is usually rounded up

    if (roundedDesi <= 2) kargoKdvHaric = 83.93;
    else if (roundedDesi === 3) kargoKdvHaric = 95.12;
    else if (roundedDesi === 4) kargoKdvHaric = 103.68;
    else if (roundedDesi === 5) kargoKdvHaric = 111.17;
    else if (roundedDesi === 6) kargoKdvHaric = 121.12;
    else if (roundedDesi === 7) kargoKdvHaric = 128.46;
    else if (roundedDesi === 8) kargoKdvHaric = 137.05;
    else if (roundedDesi === 9) kargoKdvHaric = 144.91;
    else if (roundedDesi === 10) kargoKdvHaric = 153.48;
    else if (roundedDesi === 11) kargoKdvHaric = 161.77;
    else if (roundedDesi === 12) kargoKdvHaric = 167.73;
    else kargoKdvHaric = 175.34; // 13+ desi (fallback to the max provided in the image)

    return Math.round(kargoKdvHaric * 1.20 * 100) / 100;
}

function hesaplaKar(satisFiyati, maliyet, kdvOrani, desi, komisyonOrani, kargoTipi = 'hizli') {
    if (!satisFiyati || satisFiyati <= 0) return null;
    if (!maliyet || maliyet <= 0) return null;
    if (!desi || desi <= 0) return null;

    const kargoFeeKdvDahil = getCargoFeeLocal(desi, satisFiyati, kargoTipi);
    const komisyon         = Math.round(satisFiyati * komisyonOrani * 100) / 100;
    const hizmetBedeli     = kargoTipi === 'bugun' ? HIZMET_BEDELI_BUGUN : HIZMET_BEDELI_NORMAL;
    const hizmetBedeliKdv  = Math.round(hizmetBedeli * 1.20 * 100) / 100;
    const kdvRate          = kdvOrani / 100;
    const fiyatKdvsiz      = satisFiyati / (1 + kdvRate);
    const stopaj           = Math.round(fiyatKdvsiz * 0.01 * 100) / 100;

    const satisKdv  = satisFiyati - fiyatKdvsiz;
    const kargoKdvH = (kargoFeeKdvDahil / 1.20) * 0.20;
    const hizmetKdv = hizmetBedeli * 0.20;
    const commKdv   = komisyon - (komisyon / 1.20);
    const malKdv    = maliyet - (maliyet / (1 + kdvRate));
    const netKdv    = Math.round((satisKdv - kargoKdvH - hizmetKdv - commKdv - malKdv) * 100) / 100;

    const netKarFinal = Math.round((satisFiyati - maliyet - komisyon - kargoFeeKdvDahil - hizmetBedeliKdv - stopaj - netKdv) * 100) / 100;
    const karMarji    = satisFiyati > 0 ? Math.round((netKarFinal / satisFiyati) * 100 * 10) / 10 : 0;

    return {
        netKar: netKarFinal,
        karMarji,
        netKdv,
        breakdown: {
            satisFiyati,
            urunMaliyeti: maliyet,
            komisyon: Math.round(komisyon * 100) / 100,
            komisyonOrani: Math.round(komisyonOrani * 1000) / 10,
            kargo: Math.round(kargoFeeKdvDahil * 100) / 100,
            hizmetBedeli: Math.round(hizmetBedeliKdv * 100) / 100,
            stopaj: Math.round(stopaj * 100) / 100,
            netKdv,
            netKar: netKarFinal,
            kargoTipi,
            kargoDesi: desi
        }
    };
}

// ====================================================================================
// --- FLOATING HESAP MAKİNESİ (TÜM SAYFALAR İÇİN) ---
// ====================================================================================
function injectFloatingCalculator() {
    if (document.getElementById('ty-profit-calculator')) return;

    const container = document.createElement('div');
    container.id = 'ty-profit-calculator';
    container.innerHTML = `
        <div id="ty-profit-header">
            <span>₺ TONGUÇ FİYAT</span>
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

    const toggleBtn = document.getElementById('ty-profit-toggle');
    const bodyDiv = document.getElementById('ty-profit-body');
    const inputs = container.querySelectorAll('input');

    toggleBtn.addEventListener('click', () => {
        if (bodyDiv.style.display === 'none') {
            bodyDiv.style.display = 'flex';
            toggleBtn.innerText = '_';
        } else {
            bodyDiv.style.display = 'none';
            toggleBtn.innerText = '□';
        }
    });

    function calculateProfit() {
        const price = parseFloat(document.getElementById('ty-price').value) || 0;
        const cost = parseFloat(document.getElementById('ty-cost').value) || 0;
        const commissionRate = parseFloat(document.getElementById('ty-commission-rate').value) || 0;
        const taxRate = parseFloat(document.getElementById('ty-tax-rate').value) || 0;
        const shipping = parseFloat(document.getElementById('ty-shipping').value) || 0; // KDV dahil kargo varsayılıyor

        const kdvRateNum = taxRate / 100;

        // Komisyon
        const commissionCost = price * (commissionRate / 100);

        // Stopaj
        const fiyatKdvsiz = price / (1 + kdvRateNum);
        const stopaj = fiyatKdvsiz * 0.01;

        // Hizmet Bedeli (KDV Dahil)
        const hizmetBedeliKdv = HIZMET_BEDELI_NORMAL * 1.20;

        // Net KDV Hesabı (Tam formül)
        const satisKdv = price - fiyatKdvsiz;
        const kargoKdvH = (shipping / 1.20) * 0.20;
        const hizmetKdv = HIZMET_BEDELI_NORMAL * 0.20;
        const commKdv = commissionCost - (commissionCost / 1.20);
        const malKdv = cost - (cost / (1 + kdvRateNum));

        const netKdv = satisKdv - kargoKdvH - hizmetKdv - commKdv - malKdv;

        // Net Kar
        const netProfit = price - cost - commissionCost - shipping - hizmetBedeliKdv - stopaj - netKdv;
        const profitMargin = price > 0 ? (netProfit / price) * 100 : 0;

        document.getElementById('ty-commission-cost').innerText = commissionCost.toFixed(2) + ' ₺';
        document.getElementById('ty-tax-cost').innerText = netKdv.toFixed(2) + ' ₺';

        const netElement = document.getElementById('ty-profit-net');
        netElement.innerText = netProfit.toFixed(2) + ' ₺';

        if (netProfit < 0) {
            netElement.className = 'ty-profit-negative';
        } else {
            netElement.className = 'ty-profit-positive';
        }

        document.getElementById('ty-profit-margin').innerText = 'Marj: %' + profitMargin.toFixed(2);
    }

    inputs.forEach(input => input.addEventListener('input', calculateProfit));
}

// ====================================================================================
// --- PRODUCT LISTING SAYFASI (/product-listing) ENTEGRASYONU ---
// ====================================================================================

function plReadModelKodu(productInfoEl) {
    const el = productInfoEl.querySelector('p[cy-id="contentModelCode"]');
    return el ? el.textContent.trim() : null;
}

function plReadSatisFiyati(productRow) {
    const allText = productRow.querySelectorAll('*');
    let komisyonFiyat = null;
    let musteriGorduguFiyat = null;

    for (const el of allText) {
        const text = el.textContent.trim();
        if (text === 'Komisyonun Hesaplandığı Fiyat' && el.nextElementSibling) {
            komisyonFiyat = parseTL(el.nextElementSibling.textContent.trim());
        }
        if (text === 'Müşterinin Gördüğü Fiyat' && el.nextElementSibling) {
            musteriGorduguFiyat = parseTL(el.nextElementSibling.textContent.trim());
        }
    }
    return komisyonFiyat ?? musteriGorduguFiyat ?? 0;
}

function plReadKomisyon(productRow) {
    const commEl = productRow.querySelector('[cy-id="contentCommision"] .commission-value-container div:first-child');
    if (commEl) {
        const val = parseFloat((commEl.textContent || '0').replace('%', '').replace(',', '.').trim());
        if (val > 0) return val;
    }
    const containerEl = productRow.querySelector('.commission-value-container div:first-child');
    if (containerEl) {
        const val = parseFloat((containerEl.textContent || '0').replace('%', '').replace(',', '.').trim());
        if (val > 0) return val;
    }
    return null;
}

function plInjectHeader() {
    if (document.querySelector('.tf-pl-th')) return;
    const headerRow = document.querySelector('div.thead div.tr');
    if (!headerRow) return;
    const urunBilgisiTh = Array.from(headerRow.querySelectorAll('div.th')).find(th => th.textContent.includes('Ürün Bilgisi'));
    if (!urunBilgisiTh) return;

    const th = document.createElement('div');
    th.className = 'th tf-pl-th';
    th.style.cssText = 'min-width:170px; max-width:170px; background:#fff8f0; color:#d46b08; font-size:12px; font-weight:500; flex-shrink:0; display:flex; align-items:center; padding:8px 10px; position:relative; z-index:1;';
    th.innerHTML = '<span style="background:#f27a1a;color:#fff;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;margin-right:5px;flex-shrink:0;">TF</span><span style="color:#d46b08;font-size:12px;font-weight:500;">Ürün Maliyeti</span>';
    urunBilgisiTh.insertAdjacentElement('afterend', th);
}

function renderKarBand(container, sonuc) {
    if (!sonuc) {
        container.innerHTML = '';
        return;
    }
    const bd = sonuc.breakdown;
    const isProfit = sonuc.netKar >= 0;
    const bandClass = isProfit ? 'band-profit' : 'band-loss';

    const kargoTipLabel = bd.kargoTipi === 'bugun' ? 'Bugün Kargo' : bd.kargoTipi === 'hizli' ? 'Hızlı Kargo' : 'Normal Kargo';

    container.className = 'tf-pl-auto-band';
    container.style.cssText = 'position:relative;display:inline-block;min-width:150px; cursor:default;';

    const tooltipHtml = `
        <div class="tf-breakdown-tooltip">
            <div class="tf-bt-row"><span class="tf-bt-label">Satış Fiyatı</span><span class="tf-bt-val tf-bt-pos">${formatTL(bd.satisFiyati)}</span></div>
            <div class="tf-bt-row"><span class="tf-bt-label">Ürün Maliyeti</span><span class="tf-bt-val tf-bt-neg">${formatTL(bd.urunMaliyeti)}</span></div>
            <div class="tf-bt-row"><span class="tf-bt-label">Komisyon %${bd.komisyonOrani}</span><span class="tf-bt-val tf-bt-neg">${formatTL(bd.komisyon)}</span></div>
            <div class="tf-bt-row"><span class="tf-bt-label">Kargo (KDV dahil)</span><span class="tf-bt-val tf-bt-neg">${formatTL(bd.kargo)}</span></div>
            <div class="tf-bt-row"><span class="tf-bt-label">Hizmet Bedeli</span><span class="tf-bt-val tf-bt-neg">${formatTL(bd.hizmetBedeli)}</span></div>
            <div class="tf-bt-row"><span class="tf-bt-label">Stopaj</span><span class="tf-bt-val tf-bt-neg">${formatTL(bd.stopaj)}</span></div>
            <div class="tf-bt-row"><span class="tf-bt-label">Net KDV</span><span class="tf-bt-val ${-bd.netKdv >= 0 ? 'tf-bt-pos' : 'tf-bt-neg'}">${formatTL(-bd.netKdv)}</span></div>
            <div class="tf-bt-divider"></div>
            <div class="tf-bt-row"><span class="tf-bt-label tf-bt-bold">Net Kâr</span><span class="tf-bt-val tf-bt-bold ${isProfit ? 'tf-bt-pos' : 'tf-bt-neg'}">${formatTL(bd.netKar)}</span></div>
            <div class="tf-bt-footer">📦 ${kargoTipLabel} · ${bd.kargoDesi} desi</div>
        </div>
    `;

    container.innerHTML = `
        ${tooltipHtml}
        <div class="tf-band-inner ${bandClass}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
                <span style="font-size:11px;color:#fff;font-weight:500;letter-spacing:0.3px">NET KÂR</span>
                <span style="font-size:14px;color:#fff;font-weight:500">${formatTL(sonuc.netKar)}</span>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:11px;color:#fff;font-weight:500;letter-spacing:0.3px">KÂR MARJI</span>
                <span style="font-size:13px;color:#fff;font-weight:500">%${sonuc.karMarji.toFixed(1)}</span>
            </div>
        </div>
    `;

    container.addEventListener('mouseenter', () => {
        const tooltip = container.querySelector('.tf-breakdown-tooltip');
        if (!tooltip) return;
        const rect = container.getBoundingClientRect();
        tooltip.style.display = 'block';
        let left = rect.left + rect.width / 2 - 105;
        if (left < 8) left = 8;
        if (left + 210 > window.innerWidth - 8) left = window.innerWidth - 218;
        tooltip.style.left = `${left}px`;
        tooltip.style.top  = `${rect.top - tooltip.offsetHeight - 6}px`;
    });
    container.addEventListener('mouseleave', () => {
        const tooltip = container.querySelector('.tf-breakdown-tooltip');
        if (tooltip) tooltip.style.display = 'none';
    });
}

async function plProcessRow(productRow) {
    if (productRow.dataset.tfPlDone) return;
    productRow.dataset.tfPlDone = '1';

    const productInfoEl = productRow.querySelector('div.table-product-info');
    if (!productInfoEl) return;

    const modelKodu = plReadModelKodu(productInfoEl);
    if (!modelKodu) return;

    const existingData = await LocalDB.getProduct(modelKodu, null);

    const td = document.createElement('div');
    td.className = 'td tf-pl-td';
    td.style.cssText = 'min-width:170px; max-width:170px; padding:8px 10px; vertical-align:top; background:#fffdf7; flex-shrink:0;';

    const maliyet = existingData?.urun_maliyeti ?? '';
    const desi = existingData?.cargo_deci ?? '';
    const existingKdv = existingData?.kdv_orani ?? 20;
    let aktifKargoTipi = existingData?.kargo_tipi_manual || 'hizli';
    const hasSaved = maliyet > 0 && desi > 0;

    const card = document.createElement('div');
    card.className = `tf-pl-card ${hasSaved ? 'tf-pl-card-saved' : 'tf-pl-card-empty'}`;
    card.innerHTML = `
        <div class="tf-pl-field">
            <span class="tf-pl-label">Maliyet ₺ (KDV Dahil)</span>
            <input class="tf-pl-input" type="number" placeholder="0,00" value="${maliyet}" min="0" step="0.01" data-field="maliyet">
        </div>
        <div style="display:flex; gap:5px; margin-bottom:8px">
            <div class="tf-pl-field" style="flex:1; margin-bottom:0">
                <span class="tf-pl-label">KDV %</span>
                <select class="tf-pl-input" data-field="kdv">
                    <option value="0" ${existingKdv == 0 ? 'selected' : ''}>%0</option>
                    <option value="10" ${existingKdv == 10 ? 'selected' : ''}>%10</option>
                    <option value="20" ${existingKdv == 20 ? 'selected' : ''}>%20</option>
                </select>
            </div>
            <div class="tf-pl-field" style="flex:1; margin-bottom:0">
                <span class="tf-pl-label">Desi</span>
                <input class="tf-pl-input" type="number" placeholder="0" value="${desi}" min="0" step="0.1" data-field="desi">
            </div>
        </div>
        <div class="tf-pl-kargo-sec" style="margin-bottom:8px;">
            <div style="font-size:10px;color:#888;margin-bottom:4px;">Kargo Türü</div>
            <div style="display:flex;gap:4px;">
                <button class="tf-pl-kargo-btn" data-tip="normal">Normal</button>
                <button class="tf-pl-kargo-btn" data-tip="hizli">Hızlı ⚡</button>
                <button class="tf-pl-kargo-btn" data-tip="bugun">Bugün 🚀</button>
            </div>
        </div>
        <button class="tf-pl-btn">${hasSaved ? 'Güncelle' : 'Kaydet'}</button>
        <div class="tf-pl-ok" style="display:${hasSaved ? 'flex' : 'none'}">✅ Kaydedildi</div>
    `;

    td.appendChild(card);

    const firstTd = productRow.querySelector('div.fixed-column.content-text.td') || productRow.querySelector('div.fixed-column.td');
    if (!firstTd) return;
    firstTd.insertAdjacentElement('afterend', td);

    const karWrapper = document.createElement('div');
    karWrapper.style.cssText = 'margin-top:6px;display:flex;justify-content:center;';
    const karBandEl = document.createElement('div');
    karWrapper.appendChild(karBandEl);
    firstTd.appendChild(karWrapper);

    const malInput = card.querySelector('[data-field="maliyet"]');
    const kdvInput = card.querySelector('[data-field="kdv"]');
    const desInput = card.querySelector('[data-field="desi"]');
    const btn = card.querySelector('.tf-pl-btn');
    const okEl = card.querySelector('.tf-pl-ok');
    const kargoBtns = card.querySelectorAll('.tf-pl-kargo-btn');

    function guncelleKargoButonlari() {
        kargoBtns.forEach(b => {
            b.classList.remove('active-btn');
            if (b.dataset.tip === aktifKargoTipi) b.classList.add('active-btn');
        });
    }

    function guncelleKarBand() {
        const satisFiyati = plReadSatisFiyati(productRow);
        const maliyet = parseFloat(malInput.value);
        const desi = parseFloat(desInput.value);
        if (!satisFiyati || isNaN(maliyet) || maliyet <= 0 || isNaN(desi) || desi <= 0) {
            karBandEl.innerHTML = '';
            return;
        }
        const kdvOrani = parseFloat(kdvInput.value) || 20;
        const komisyonRaw = plReadKomisyon(productRow);
        if (komisyonRaw === null) return;

        const sonuc = hesaplaKar(satisFiyati, maliyet, kdvOrani, desi, komisyonRaw / 100, aktifKargoTipi);
        renderKarBand(karBandEl, sonuc);
    }

    guncelleKargoButonlari();
    guncelleKarBand();

    kargoBtns.forEach(b => {
        b.addEventListener('click', () => {
            aktifKargoTipi = b.dataset.tip;
            guncelleKargoButonlari();
            guncelleKarBand();
        });
    });

    [malInput, kdvInput, desInput].forEach(inp => {
        inp.addEventListener('input', () => {
            card.classList.remove('tf-pl-card-error');
            karBandEl.innerHTML = '';
        });
    });

    btn.addEventListener('click', async () => {
        const m = parseFloat(malInput.value);
        const k = parseFloat(kdvInput.value);
        const d = parseFloat(desInput.value);

        if (!m || !d) {
            card.classList.add('tf-pl-card-error');
            return;
        }

        btn.textContent = 'Kaydediliyor...';
        await LocalDB.saveProduct(modelKodu, null, m, d, k, aktifKargoTipi);

        btn.textContent = 'Güncelle';
        card.classList.add('tf-pl-card-saved');
        card.classList.remove('tf-pl-card-error', 'tf-pl-card-empty');
        okEl.style.display = 'flex';
        guncelleKarBand();
    });
}

async function plProcessAll() {
    const rows = Array.from(document.querySelectorAll('div.tr, tr')).filter(row =>
        !row.querySelector('div.variant-product-info-container') &&
        !row.dataset.tfPlDone &&
        row.querySelector('div.table-product-info') !== null
    );
    if (rows.length > 0) {
        plInjectHeader();
        for (const row of rows) {
            await plProcessRow(row);
        }
    }
}

// ====================================================================================
// --- SİPARİŞLER SAYFASI (/orders/shipment-packages) ENTEGRASYONU ---
// ====================================================================================
async function injectOrderKar() {
    const rows = document.querySelectorAll('tr.chakra-table__row');

    for (const row of rows) {
        if (row.querySelector('.tf-order-kar-band')) continue;
        const orderNoEl = row.querySelector('p[data-testid="shipment-package-order-number"]');
        if (!orderNoEl) continue;
        const orderNo = orderNoEl.textContent.trim().replace('#', '');
        if (!orderNo) continue;

        // Sipariş detaylarından fiyat vs okuma
        const priceEl =
            row.querySelector('p[data-testid="unit-price-value"]') ||
            row.querySelector('p[data-testid="unit-price-value-after-ty-plus"]') ||
            row.querySelector('p[data-testid="unit-price-value-before-ty-plus"]');

        const priceContainer = priceEl ? (priceEl.closest('td') || priceEl.closest('div')) : row.querySelector('td:nth-child(4)');
        if (!priceContainer) continue;

        const satisFiyati = parseTL(priceEl?.textContent?.trim() || '');
        if (!satisFiyati) continue;

        // Barkod okuma (Sipariş detaylarında line-item-barcode-value veya shipment-package-barcode olarak bulunabilir)
        let modelKodu = '';
        let barcode = '';
        const spans = row.querySelectorAll('span');
        for (let i = 0; i < spans.length; i++) {
            if (spans[i].textContent.trim() === 'Stok Kodu:' && spans[i].nextElementSibling) {
                modelKodu = spans[i].nextElementSibling.textContent.trim();
            }
            if (spans[i].textContent.trim() === 'Barkod:' && spans[i].nextElementSibling) {
                barcode = spans[i].nextElementSibling.textContent.trim();
            }
        }

        if (!modelKodu) {
            const modelKoduEl = row.querySelector('p[data-testid="line-item-stock-code-value"]') || row.querySelector('p[data-testid="shipment-package-stock-code"]');
            modelKodu = modelKoduEl?.textContent?.trim() || '';
        }
        if (!barcode) {
            const barcodeEl = row.querySelector('p[data-testid="line-item-barcode-value"]') || row.querySelector('p[data-testid="shipment-package-barcode"]');
            barcode = barcodeEl?.textContent?.trim() || '';
        }

        // Ürün verisini LocalDB'den çek
        const urunData = await LocalDB.getProduct(modelKodu, barcode);
        const maliyet = urunData?.urun_maliyeti ?? 0;
        const desi = urunData?.cargo_deci ?? 0;
        const kdvOrani = urunData?.kdv_orani ?? 20;
        const kargoTipi = urunData?.kargo_tipi_manual || 'hizli';

        const band = document.createElement('div');
        band.className = 'tf-order-kar-band';
        band.style.position = 'relative';

        if (!maliyet || maliyet <= 0) {
            band.innerHTML = `<span style="font-size:10px; color:#c62828; font-weight:bold;">Maliyet Eksik</span>`;
        } else if (!desi || desi <= 0) {
            band.innerHTML = `<span style="font-size:10px; color:#c62828; font-weight:bold;">Desi Eksik</span>`;
        } else {
            // Varsayılan komisyon %15 alınıyor (Sipariş sayfasından okumak zor olabilir)
            const sonuc = hesaplaKar(satisFiyati, maliyet, kdvOrani, desi, 0.15, kargoTipi);
            if (sonuc) {
                const bd = sonuc.breakdown;
                const isProfit = sonuc.netKar >= 0;
                const bandClass = isProfit ? 'band-profit' : 'band-loss';

                band.innerHTML = `
                <div class="tf-band-inner ${bandClass}" style="margin-top:5px; max-width: 150px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
                        <span style="font-size:11px;color:#fff;font-weight:500;letter-spacing:0.3px">NET KÂR</span>
                        <span style="font-size:14px;color:#fff;font-weight:500">${formatTL(sonuc.netKar)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="font-size:11px;color:#fff;font-weight:500;letter-spacing:0.3px">MARJ</span>
                        <span style="font-size:13px;color:#fff;font-weight:500">%${sonuc.karMarji.toFixed(1)}</span>
                    </div>
                </div>
                `;
            }
        }

        const priceCell = priceEl?.closest('td') || priceContainer;
        if(priceCell) priceCell.appendChild(band);
    }
}

// ====================================================================================
// --- FİYATLANDIRMA SAYFASI (/pricing) ENTEGRASYONU ---
// ====================================================================================

function getFiyatAraliklari(row) {
    const list = [];
    const carousels = row.querySelectorAll('td div.cell-carousel');
    carousels.forEach((carousel, i) => {
        if (carousel.closest('div.content-update-box-v2')) return;
        const tierContent = carousel.querySelector('div.tier-content');
        const otherPricesBox = carousel.querySelector('div.other-prices-box-tier');
        if (!tierContent && !otherPricesBox) return;

        let priceEl, commEl;
        if (tierContent) {
            priceEl = tierContent.querySelector('div.tier-content-price span:first-child');
            commEl  = tierContent.querySelector('span.tier-content-commission-main');
        } else {
            priceEl = otherPricesBox.querySelector('div.other-prices-box-price span');
            commEl  = otherPricesBox.querySelector('span.other-prices-box-commission-main');
        }
        if (!priceEl) return;

        const priceVal = parseTL(priceEl.textContent?.trim() || '');
        const commRate = parseFloat((commEl?.textContent || '0').replace('%', '').replace(',', '.').trim()) || 0;
        const labelEl  = carousel.querySelector('span.cell-carousel-label');
        const label    = labelEl?.textContent?.trim() || `${i + 1}. Aralık`;
        const isUstu   = (tierContent?.textContent || otherPricesBox?.textContent || '').includes('ve üstü');

        if (priceVal > 0) list.push({ index: i, priceVal, commRate, isUstu, label, el: carousel });
    });
    return list;
}

function getGuncelKomisyon(row) {
    const tds = row.querySelectorAll('td');
    for (const td of tds) {
        const box = td.querySelector('div.current-price-commission-box');
        if (box) {
            const priceRows = box.querySelectorAll('div.current-price-row');
            for (const priceRow of priceRows) {
                const lbl = priceRow.querySelector('span.label');
                const val = Array.from(priceRow.querySelectorAll('span.value')).find(v => v.parentElement === priceRow);
                if (lbl?.textContent?.trim().includes('ncel Komisyon') && val) {
                    return parseFloat(val.textContent.replace('%', '').replace(',', '.').trim()) || 0;
                }
            }
        }
    }
    return 0;
}

async function processPricingRows() {
    const rows = Array.from(document.querySelectorAll('tr.content-row')).filter(row => !row.dataset.tfPricingDone);

    for (const row of rows) {
        row.dataset.tfPricingDone = '1';

        const barkod = readBarcode(row);
        const modelKodu = plReadModelKodu(row) || readModelKodu(row);

        const araliklar = getFiyatAraliklari(row);
        const guncelKomisyon = getGuncelKomisyon(row);

        const urunData = await LocalDB.getProduct(modelKodu, barkod);
        const maliyet = urunData?.urun_maliyeti ?? 0;
        const desi = urunData?.cargo_deci ?? 0;
        const kdvOrani = urunData?.kdv_orani ?? 20;
        const kargoTipi = urunData?.kargo_tipi_manual || 'hizli';

        if (maliyet > 0 && desi > 0) {
            // Aralıkları hesapla ve ekrana bas
            araliklar.forEach(aralik => {
                const commRate = aralik.commRate || guncelKomisyon;
                const sonuc = hesaplaKar(aralik.priceVal, maliyet, kdvOrani, desi, commRate / 100, kargoTipi);

                if (sonuc && !aralik.el.querySelector('.tf-pricing-kar-band')) {
                    const band = document.createElement('div');
                    band.className = 'tf-pricing-kar-band';
                    band.style.cssText = 'margin-top:6px;';

                    const isProfit = sonuc.netKar >= 0;
                    const bandClass = isProfit ? 'band-profit' : 'band-loss';

                    band.innerHTML = `
                        <div class="tf-band-inner ${bandClass}">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
                                <span style="font-size:10px;color:#fff;font-weight:600">NET KÂR</span>
                                <span style="font-size:13px;color:#fff;font-weight:700">${formatTL(sonuc.netKar)}</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <span style="font-size:10px;color:#fff;font-weight:600">MARJ</span>
                                <span style="font-size:12px;color:#fff;font-weight:600">%${sonuc.karMarji.toFixed(1)}</span>
                            </div>
                        </div>
                    `;
                    aralik.el.appendChild(band);
                }
            });

            // Fiyat Güncelleme sütununa Etkileşimli Kâr Hesabı Widget'ı ekle
            const tds = row.querySelectorAll('td');
            if (tds.length > 0) {
                const lastTd = tds[tds.length - 1]; // "Fiyat Güncelle" sütunu
                if (!lastTd.querySelector('.tf-interactive-calc-card')) {

                    // Widget konteyneri
                    const calcCard = document.createElement('div');
                    calcCard.className = 'tf-interactive-calc-card';
                    calcCard.style.cssText = `
                        margin-top: 10px;
                        border: 1px solid #f27a1a;
                        border-radius: 8px;
                        padding: 10px;
                        background-color: #fff;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                        width: 200px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    `;

                    // Hesaplamalar için ortalama kargo bulalım
                    // Varsayılan kargo fiyatı 100 TL ile başlasın, hesaplaKar ile bulabiliriz (Satış Fiyatı geçici bir değer olsun)
                    const tempSonuc = hesaplaKar(100, maliyet, kdvOrani, desi, 0.15, kargoTipi);
                    const kargoUcreti = tempSonuc ? tempSonuc.breakdown.kargo : 0;

                    calcCard.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span style="font-size:12px; font-weight:700; color:#f27a1a; display:flex; align-items:center;">
                                <span style="background-color:#f27a1a; color:#fff; padding:2px 4px; border-radius:3px; margin-right:6px; font-size:10px;">TF</span>
                                Kâr Hesabı
                            </span>
                            <span style="font-size:12px; cursor:pointer; color:#999;" class="tf-calc-reset" title="Sıfırla">✏️</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:4px; color:#666;">
                            <span>Maliyet</span>
                            <span style="font-weight:700; color:#333;">${formatTL(maliyet)}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:12px; color:#666;">
                            <span>Ort. Kargo (KDV dahil)</span>
                            <span style="font-weight:700; color:#333;">${formatTL(kargoUcreti)}</span>
                        </div>

                        <div style="margin-bottom:6px;">
                            <label style="font-size:10px; color:#888; display:block; margin-bottom:4px;">Satış Fiyatı</label>
                            <input type="number" class="tf-calc-price-input" placeholder="Fiyat girin..." style="width:100%; box-sizing:border-box; padding:6px 8px; border:1px solid #e2e8f0; border-radius:4px; font-size:12px; outline:none; transition:border-color 0.2s;" onfocus="this.style.borderColor='#f27a1a'" onblur="this.style.borderColor='#e2e8f0'">
                        </div>

                        <div style="display:flex; gap:8px; margin-bottom:12px;">
                            <div style="flex:1;">
                                <label style="font-size:10px; color:#888; display:block; margin-bottom:4px;">Komisyon (%)</label>
                                <input type="number" class="tf-calc-comm-input" value="${guncelKomisyon}" style="width:100%; box-sizing:border-box; padding:6px 8px; border:1px solid #e2e8f0; border-radius:4px; font-size:12px; outline:none; transition:border-color 0.2s;" onfocus="this.style.borderColor='#f27a1a'" onblur="this.style.borderColor='#e2e8f0'">
                            </div>
                            <div style="flex:1;">
                                <label style="font-size:10px; color:#888; display:block; margin-bottom:4px;">KDV (%)</label>
                                <input type="number" class="tf-calc-kdv-input" value="${kdvOrani}" style="width:100%; box-sizing:border-box; padding:6px 8px; border:1px solid #e2e8f0; border-radius:4px; font-size:12px; background:#f8fafc; color:#64748b;" disabled>
                            </div>
                        </div>

                        <button class="tf-calc-btn" style="width:100%; background-color:#f27a1a; color:#fff; border:none; border-radius:4px; padding:8px 0; font-size:12px; font-weight:600; cursor:pointer; transition:background 0.2s;" onmouseover="this.style.backgroundColor='#d46b08'" onmouseout="this.style.backgroundColor='#f27a1a'">Hesapla</button>

                        <div class="tf-calc-result-container" style="margin-top:12px; display:none; padding-top:10px; border-top:1px dashed #e2e8f0;">
                            <div style="display:flex; justify-content:space-between; font-size:10px; margin-bottom:4px; color:#666;">
                                <span>Komisyon Tutarı:</span>
                                <span class="tf-calc-comm-cost" style="font-weight:600;">0.00 ₺</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-size:10px; margin-bottom:10px; color:#666;">
                                <span>Net KDV:</span>
                                <span class="tf-calc-kdv-cost" style="font-weight:600;">0.00 ₺</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                <span style="font-size:11px; font-weight:600; color:#475569;">Net Kâr:</span>
                                <span class="tf-calc-net" style="font-size:14px; font-weight:700; color:#10b981;">0.00 ₺</span>
                            </div>
                            <div style="text-align:right;">
                                <span class="tf-calc-marj" style="font-size:10px; color:#64748b; font-weight:500;">Marj: %0.00</span>
                            </div>
                        </div>
                    `;

                    lastTd.appendChild(calcCard);

                    // Etkileşimler
                    const btn = calcCard.querySelector('.tf-calc-btn');
                    const priceInput = calcCard.querySelector('.tf-calc-price-input');
                    const commInput = calcCard.querySelector('.tf-calc-comm-input');
                    const resContainer = calcCard.querySelector('.tf-calc-result-container');
                    const resNet = calcCard.querySelector('.tf-calc-net');
                    const resMarj = calcCard.querySelector('.tf-calc-marj');
                    const resetBtn = calcCard.querySelector('.tf-calc-reset');

                    btn.addEventListener('click', () => {
                        const sPrice = parseFloat(priceInput.value);
                        const cRate = parseFloat(commInput.value);

                        if (sPrice > 0 && cRate >= 0) {
                            const dynSonuc = hesaplaKar(sPrice, maliyet, kdvOrani, desi, cRate / 100, kargoTipi);
                            if (dynSonuc) {
                                const resCommCost = calcCard.querySelector('.tf-calc-comm-cost');
                                const resKdvCost = calcCard.querySelector('.tf-calc-kdv-cost');
                                if (resCommCost) resCommCost.textContent = formatTL(dynSonuc.breakdown.komisyon);
                                if (resKdvCost) resKdvCost.textContent = formatTL(Math.abs(dynSonuc.breakdown.netKdv));
                                resNet.textContent = formatTL(dynSonuc.netKar);
                                resMarj.textContent = `Marj: %${dynSonuc.karMarji.toFixed(1)}`;

                                if (dynSonuc.netKar >= 0) {
                                    resNet.style.color = '#0f9d58'; // Yeşil
                                } else {
                                    resNet.style.color = '#db4437'; // Kırmızı
                                }

                                resContainer.style.display = 'block';
                            }
                        }
                    });

                    resetBtn.addEventListener('click', () => {
                        priceInput.value = '';
                        resContainer.style.display = 'none';
                    });
                }
            }
        }
    }
}

// Barkod ve Model Kodu seçicilerini genel sayfalar için tanımla
function readBarcode(row) {
    let barcode = '';
    const divs = row.querySelectorAll('div.product-info-additional');
    for (const div of divs) {
        if (div.textContent.toLowerCase().includes('barkod')) {
            const span = div.querySelector('span.product-info-additional-value') || div.querySelector('span');
            if (span) barcode = span.textContent.trim();
        }
    }
    return barcode;
}

function readModelKodu(row) {
    const cyEl = row.querySelector('p[cy-id="contentModelCode"]');
    if (cyEl) return cyEl.textContent.trim();
    const el = row.querySelector('div.product-info-code span');
    return el?.textContent?.replace('Model Kodu:', '').trim() || '';
}

// --- Init Yönlendirmesi ---
let tfObserver = null;

function runExtension() {
    // Tüm sayfalarda Floating Calculator çalışsın
    injectFloatingCalculator();

    if (tfObserver) {
        tfObserver.disconnect();
        tfObserver = null;
    }

    const path = window.location.pathname;
    let debounceTimer = null;

    tfObserver = new MutationObserver(() => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            if (path.includes('/product-listing')) {
                plProcessAll();
            } else if (path.includes('/orders/shipment-packages')) {
                injectOrderKar();
            } else if (path.includes('/pricing')) {
                processPricingRows();
            }
        }, 500);
    });

    tfObserver.observe(document.body, { childList: true, subtree: true });

    // İlk çalıştırma
    if (path.includes('/product-listing')) {
        plProcessAll();
    } else if (path.includes('/orders/shipment-packages')) {
        injectOrderKar();
    } else if (path.includes('/pricing')) {
        processPricingRows();
    }
}

// SPA Sayfa Değişikliklerini Yakalama
(function() {
    let lastPath = location.pathname;
    function onUrlChange() {
        if (location.pathname !== lastPath) {
            lastPath = location.pathname;
            setTimeout(runExtension, 1000);
            setTimeout(runExtension, 3000);
        }
    }
    const origPush = history.pushState;
    const origReplace = history.replaceState;
    history.pushState = function(...args) { origPush.apply(this, args); onUrlChange(); };
    history.replaceState = function(...args) { origReplace.apply(this, args); onUrlChange(); };
    window.addEventListener('popstate', onUrlChange);
})();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runExtension);
} else {
    runExtension();
}
