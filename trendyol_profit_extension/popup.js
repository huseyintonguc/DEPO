// popup.js - TONGUÇ FİYAT V2

const KOMISYON_LISTESI = {
    "Aksesuar": { "Altın (İşlenmemiş)": 9.0, "Mücevher": 21.5, "Atkı & Bere & Eldiven": 21.5, "Gözlük": 21.5, "Takı": 22.5, "Diğer Aksesuar": 22.5, "Saat": 21.5 },
    "Ayakkabı & Çanta": { "Ayakkabı": 21.5, "Çanta": 21.5 },
    "Bahçe & Elektrikli El Aletleri": { "Bahçe": 20.0, "Elektrikli El Aletleri": 16.5, "Enerji Sistemleri": 16.5 },
    "Bahçe ve Yapı Market": { "Yapı Market": 20.0 },
    "Banyo Yapı & Hırdavat": { "Elektrik & Tesisat Malzemeleri": 20.0, "Banyo Yapı Malzemeleri": 18.0, "Boya": 19.5, "Hırdavat": 16.5 },
    "Çocuk": { "Çocuk Gereçleri": 19.0, "Oyuncak": 19.0, "Bebek Beslenme/Emzirme": 19.0, "Bebek Banyo & Tuvalet": 19.0, "Bebek Odası ve Tekstili": 19.0 },
    "Dijital Kod & Ürünler": { "Dijital Kod & Ürünler": 11.0, "Dijital Kart & Kupon & Hizmetler": 11.0 },
    "E-Kitap Okuyucu": { "E-Kitap Okuyucu": 10.0 },
    "Elektronik": { "Elektrikli Ev Aletleri": 19.5, "Elektronik Aksesuarlar": 23.0, "Giyilebilir Teknoloji & Kulaklıklar": 16.5, "Bilgisayar Grubu": 11.0, "Telefon": 7.0, "Beyaz Eşya & TV": 15.0, "Tablet Grubu": 19.0, "Oyun & Oyun Konsolları": 12.0, "Foto & Kamera": 11.0, "Görüntü & Ses Sistemleri": 17.0, "Kişisel Bakım Aletleri": 18.6, "Klima & Isıtıcı": 11.0 },
    "Ev": { "Banyo": 18.5, "Sofra & Mutfak": 19.0, "Ev Tekstili": 21.0 },
    "Giyim": { "Giyim": 21.5 },
    "Hobi & Eğlence": { "Çakmaklar": 20.5, "Müzik Alet ve Ekipmanları": 15.0, "Yetişkin Hobi ve Oyun": 20.0, "Drone": 12.0, "Drone Aksesuarı": 18.5, "Film": 11.0, "Hobi Malzemeleri": 20.5, "Parti ve Yılbaşı Ürünleri": 20.5, "RC Araç ve Aksesuarlar": 19.0 },
    "Kitap": { "Kitap": 15.5, "E-Kitap": 10.0 },
    "Kırtasiye & Ofis Malzemeleri": { "Boya & Sanatsal Malzemeler": 18.0, "Kırtasiye Kağıt Ürünleri": 18.0, "Fotokopi ve Baskı Kağıtları": 9.0, "Ofis Teknolojileri": 15.0, "Diğer Kırtasiye Malzemeleri": 19.0 },
    "Kozmetik & Kişisel Bakım": { "Kişisel Bakım": 19.0, "Kozmetik": 19.0 },
    "Mobilya": { "Aydınlatma": 23.5, "Salon Mobilyası": 23.0, "Yatak Odası Mobilyası": 23.0, "Ev Gereçleri": 21.0, "Bebek & Çocuk Odası Mobilyası": 22.0, "Mutfak & Banyo Mobilyası": 23.0, "Ev Dekorasyon": 24.0, "Halı/Kilim": 22.5, "Ofis Mobilyaları": 23.0, "Takım Mobilyalar": 22.0, "Perde": 22.5, "Bahçe & Balkon Mobilyası": 23.0 },
    "Otomobil & Motosiklet": { "Oto Aksesuar": 12.0, "Otomobil Yedek Parça": 22.5, "Oto Bakım / Temizlik": 16.5, "Oto Ses Görüntü Sistemleri": 14.0, "Motosiklet Aksesuarları": 15.0, "Motosiklet Yedek Parça": 17.0, "Jantlar & Jant Kapakları": 17.5, "Lastikler": 10.0 },
    "Spor": { "Spor Ekipmanları": 15.0, "Outdoor Ekipmanları": 12.0 },
    "Süpermarket": { "Gıda & İçecek": 19.0, "Bebek Bakım": 20.0, "Ev Bakım ve Temizlik": 17.0, "Bebek Beslenme": 15.0, "Sağlık": 19.0, "Pet Shop": 20.0 },
};

const HIZMET_BEDELI_NORMAL = 10.99;
const HIZMET_BEDELI_BUGUN  = 6.99;

let kdvOrani = 20;
let teslimatTipi = 'normal';
let aciklamaAcik = false;

function fmt(val) {
    const n = Number(val || 0);
    return "₺" + Math.abs(n).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function r(n) { return Math.round(n * 100) / 100; }

function hesapla({ satisFiyati, maliyet, kdvOrani, komisyonOrani, kargoKdvli, teslimatTipi }) {
    const hizmetBedeli = teslimatTipi === 'bugun' ? HIZMET_BEDELI_BUGUN : HIZMET_BEDELI_NORMAL;
    const komisyon = satisFiyati * (komisyonOrani / 100);
    const kdvRate = kdvOrani / 100;
    const fiyatKdvsiz = satisFiyati / (1 + kdvRate);
    const stopaj = fiyatKdvsiz * 0.01;
    const hizmetKdvli = hizmetBedeli * 1.20;

    const kargoKdvsiz = kargoKdvli / 1.20;
    const satisKdv = satisFiyati - fiyatKdvsiz;

    const netKdv = satisKdv - (kargoKdvsiz * 0.20) - (hizmetBedeli * 0.20) - (komisyon - komisyon / 1.20) - (maliyet - maliyet / (1 + kdvRate));
    const netKar = satisFiyati - komisyon - stopaj - hizmetKdvli - kargoKdvli - maliyet - netKdv;
    const karMarji = satisFiyati > 0 ? (netKar / satisFiyati) * 100 : 0;
    const karMaliyetMarji = maliyet > 0 ? (netKar / maliyet) * 100 : 0;
    const hakedis = satisFiyati - kargoKdvli - hizmetKdvli - komisyon - stopaj;

    return {
        satisFiyati: r(satisFiyati),
        komisyon: r(komisyon),
        stopaj: r(stopaj),
        hizmetBedeli: r(hizmetKdvli),
        kargoUcret: r(kargoKdvli),
        urunMaliyeti: r(maliyet),
        netKar: r(netKar),
        karMarji: r(karMarji),
        karMaliyetMarji: r(karMaliyetMarji),
        hakedis: r(hakedis),
        netKdv: r(netKdv),
        komisyonOrani,
        teslimatTipi
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const selKat = document.getElementById('kategori');
    const selAlt = document.getElementById('alt-kategori');
    const inputKomisyon = document.getElementById('komisyon');

    // Kategorileri doldur
    Object.keys(KOMISYON_LISTESI).sort().forEach(k => {
        const opt = document.createElement('option');
        opt.value = k; opt.textContent = k;
        selKat.appendChild(opt);
    });

    selKat.addEventListener('change', (e) => {
        const kat = e.target.value;
        selAlt.innerHTML = '<option value="">Seçiniz</option>';
        if (!kat) { selAlt.disabled = true; return; }

        Object.keys(KOMISYON_LISTESI[kat]).forEach(a => {
            const opt = document.createElement('option');
            opt.value = a; opt.textContent = a;
            selAlt.appendChild(opt);
        });
        selAlt.disabled = false;
        inputKomisyon.value = '';
    });

    selAlt.addEventListener('change', (e) => {
        const kat = selKat.value;
        const alt = e.target.value;
        if (kat && alt && KOMISYON_LISTESI[kat][alt]) {
            inputKomisyon.value = KOMISYON_LISTESI[kat][alt];
        }
    });

    // Buton Toggle İşlemleri
    document.querySelectorAll('.kdv-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.kdv-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            kdvOrani = parseInt(btn.dataset.kdv);
        });
    });

    document.querySelectorAll('.tip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tip-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            teslimatTipi = btn.dataset.tip;
            document.getElementById('hizmet-hint').textContent = `Hizmet: ₺${teslimatTipi === 'bugun' ? HIZMET_BEDELI_BUGUN : HIZMET_BEDELI_NORMAL} + KDV`;
        });
    });

    // Hesapla
    document.getElementById('hesapla-btn').addEventListener('click', () => {
        const maliyet = parseFloat(document.getElementById('maliyet').value) || 0;
        const komisyonOran = parseFloat(inputKomisyon.value) || 0;
        const satisFiyati = parseFloat(document.getElementById('satis-fiyati').value) || 0;
        const kargoKdvli = parseFloat(document.getElementById('kargo').value) || 0;

        if (!maliyet || !komisyonOran || !satisFiyati) return;

        const s = hesapla({ satisFiyati, maliyet, kdvOrani, komisyonOrani: komisyonOran, kargoKdvli, teslimatTipi });

        const karEl = document.getElementById('sonuc-kar');
        karEl.className = `sonuc-kar ${s.netKar >= 0 ? 'profit' : 'loss'}`;
        karEl.innerHTML = `
            <div class="sonuc-kar-label">NET KÂR</div>
            <div class="sonuc-kar-val">${s.netKar < 0 ? '-' : ''}${fmt(Math.abs(s.netKar))}</div>
            <div class="sonuc-marj-grid">
                <div class="sonuc-marj-item"><label>Kar/Satış</label><span>%${s.karMarji.toFixed(1)}</span></div>
                <div class="sonuc-marj-item"><label>Kar/Maliyet</label><span>%${s.karMaliyetMarji.toFixed(1)}</span></div>
            </div>
        `;

        const html = [
            { label: 'Satış Fiyatı', val: s.satisFiyati, plus: true },
            { label: `Komisyon (%${s.komisyonOrani})`, val: -s.komisyon, plus: false },
            { label: 'Stopaj (%1)', val: -s.stopaj, plus: false },
            { label: 'Hizmet Bedeli (KDV dahil)', val: -s.hizmetBedeli, plus: false },
            { label: 'Kargo (KDV dahil)', val: -s.kargoUcret, plus: false },
            { label: 'Ürün Maliyeti', val: -s.urunMaliyeti, plus: false },
            { label: 'Net KDV', val: s.netKdv >= 0 ? -s.netKdv : Math.abs(s.netKdv), plus: s.netKdv < 0, isKdv: true }
        ].map(item => {
            const abs = Math.abs(item.val);
            const goster = item.val < 0 ? `-${fmt(abs)}` : (item.isKdv ? `+${fmt(abs)}` : fmt(abs));
            const cls = item.isKdv ? (item.val < 0 ? 'minus' : 'plus') : (item.plus ? 'plus' : 'minus');
            return `<div class="detay-row"><span class="detay-label">${item.label}</span><span class="detay-val ${cls}">${goster}</span></div>`;
        }).join('');

        document.getElementById('detay-rows').innerHTML = html + `
            <div class="divider"></div>
            <div class="detay-row bold">
                <span class="detay-label">Tahmini Hakediş</span>
                <span class="detay-val">${fmt(s.hakedis)}</span>
            </div>
        `;

        document.getElementById('detay-card').style.display = 'block';
        document.getElementById('aciklama-btn').style.display = 'flex';

        // Açıklama Paneli Doldur
        const tip = s.teslimatTipi === 'bugun' ? HIZMET_BEDELI_BUGUN : HIZMET_BEDELI_NORMAL;
        document.getElementById('aciklama-panel').innerHTML = `
            <div style="font-weight:bold;margin-bottom:6px">Nasıl Hesaplanıyor?</div>
            <div class="aciklama-item"><span class="aciklama-key">Komisyon:</span><span>Satış fiyatı × %${s.komisyonOrani}</span></div>
            <div class="aciklama-item"><span class="aciklama-key">Stopaj:</span><span>KDV hariç fiyat × %1</span></div>
            <div class="aciklama-item"><span class="aciklama-key">Hizmet B.:</span><span>₺${tip} + %20 KDV</span></div>
            <div class="aciklama-formula">Net Kâr = Satış − Maliyet − Komisyon − Kargo − Hizmet − Stopaj ± Net KDV</div>
        `;
    });

    document.getElementById('aciklama-btn').addEventListener('click', () => {
        aciklamaAcik = !aciklamaAcik;
        document.getElementById('aciklama-panel').classList.toggle('open', aciklamaAcik);
        document.getElementById('aciklama-arrow').textContent = aciklamaAcik ? '▲' : '▼';
    });
});