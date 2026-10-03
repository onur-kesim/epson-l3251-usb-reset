# KRITER 0.1.3 — `epson-usb`: CI imajı, güncel upstream'e karşı sözleşme, `compat.py` uyarısı

> **DONDURULDU — 3 Eki 2026.** Bu dosya `epson-usb` **0.1.3** işinin **İLK commit'idir** ve koddan ÖNCE gelir.
> Bu commit'ten sonra değişirse deneme **BAŞARISIZ** sayılır.
> **Karar:** Onur, 3 Eki 2026 — kapsam "pin + güncel upstream + compat uyarısı"; soket keşfi **yapılmayacak**.

## ÖLÇÜLEN DURUM (3 Eki 2026, bu dosya yazılırken)

- **Yayın hattı riski.** Üç iş akışının dört işi de `runs-on: ubuntu-latest`. GitHub'ın kendi notu:
  *"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026."* `release.yml` Python
  **3.10** ile, `epson-usb.yml` **3.9 + 3.10** ile koşuyor. Yeni imajda bu sürümlerin sağlanıp sağlanmayacağı
  **ÖLÇÜLEMEDİ**; sağlanmazsa PyPI'ye yayın hattı kod hatası olmadan kırılır.
- **Upstream bu paketi artık PyPI'den alıyor.** `Ircama/epson_print_conf` `413c2d0` (25 Eyl 2026, *"Move the USB
  bridge into this repository, bump version to 8.1.1"*): kendi `epson_usb/` kopyasını sildi, köprüyü kendi
  `epson_usb_bridge.py` dosyasına taşıdı; `requirements.txt` → `epson-usb>=0.1.0; python_version >= "3.10"`.
  Güncel main: **`da1a7f6b41884d4afa678217534ade7c80adee53`** (3 Eki 2026, 8.1.4).
- **Upstream'in bu paketten import ettiği yüzey** (`epson_usb_bridge.py`, da1a7f6):
  `epson_usb.errors.TransportError` · `epson_usb.printer.EpsonUsbPrinter` · `epson_usb.backends.backend_class` ·
  `epson_usb.backends.find_devices`. Dördü de bu depoda var (`errors.py:40`, `printer.py:114`,
  `backends/__init__.py:70` ve `:114`).
- **CI'ın upstream pini eski:** `UPSTREAM_SHA: 1ef1555…` köprü taşınmadan önceki hâl; orada upstream hâlâ
  `epson_usb.compat`'ı import ediyor. Güncel upstream'in kullandığı yüzey **hiçbir testte güncel upstream'e
  karşı denenmiyor.**
- **`compat.py`** (419 satır) README'de belgelenmiş açık API; upstream ≥ 8.1.1 onu kullanmıyor
  (Ircama'nın 25 Eyl ipucu). Upstream da1a7f6'nın tüm `.py` dosyaları Python 3.9 dilbilgisiyle ayrıştırılabiliyor
  (`ast.parse(..., feature_version=(3, 9))`) — yalnız **sözdizimi** ölçüldü, çalışma zamanı değil.

## KAPSAM

K13 (CI imajı) + K14 (güncel upstream'e karşı sözleşme) + K15 (`compat.py` kullanımdan kaldırma uyarısı) + K16 (sürüm).

## 🔴 KIRMIZI ÇİZGİLER

- D4 el sıkışması, kredi akışı, EEPROM adresleri, `RKEY`/`WKEY`, bölenler, 0.1.2'nin arayüz seçimi ve geri
  çekilmesi — **dokunulmaz**. EPSON-CTRL **soket keşfi YOK** (Onur'un kararı).
- Upstream'in import ettiği dört sembolün **adı ve imzası değişmez.**
- `compat.py` **SİLİNMEZ**; yalnız uyarı verir.
- Mevcut test dosyalarından **test silinmez**; K1 tabanı düşürülmez.
- Yeni **dış bağımlılık YOK** (test-zamanı upstream hariç, o zaten var).
- Upstream deposuna PR/issue/yorum **YOK**. `PUSH ETME, PR AÇMA, YORUM GÖNDERME` — hepsi Onur'da.

## Yürürlükteki: K1–K12 aynen geçerli

`KRITER.md` (K1–K4), `KRITER_0.1.1.md` (K5–K6), `KRITER_0.1.2.md` (K7–K12). K1'in tabanı bu sürümde, yeni
testler eklendikten sonra **ölçülen toplama** yükseltilir; aşağı inmez.

## Yeni: K13–K16

- **K13 — CI imajı sabit.** `.github/workflows/` altında `runs-on: ubuntu-latest` sayısı **0**,
  `runs-on: ubuntu-24.04` sayısı **4** (`ci.yml` 1 · `epson-usb.yml` 1 · `release.yml` 2).
  Python sürümleri **değişmez** (3.11 · 3.9+3.10 · 3.10).
- **K14 — Güncel upstream'e karşı sözleşme.** CI'ın `UPSTREAM_SHA` değeri
  `da1a7f6b41884d4afa678217534ade7c80adee53` olur ve şunlar **o commit'e karşı** yeşil koşar:
  - **(a) Sözleşme testi:** upstream'in `epson_usb_bridge.py` dosyasının bu paketten import ettiği dört sembol
    import edilir ve upstream'in onları çağırdığı biçimle (aynı parametre adları) çağrılabilir.
  - **(b) Uçtan uca köprü testi:** upstream'in kendi `epson_usb_bridge.usb_printer(...)` köprüsüyle kurulan
    yazıcı nesnesi, bu deponun `mock` aktarımı üzerinde EEPROM `0x30` okuması yapar; sonuç, aynı `mock`'a
    doğrudan `EpsonUsbPrinter` ile yapılan okumayla **aynıdır**.
  - **(c) Gölge koruması:** upstream'in `requirements.txt`'i PyPI'den `epson-usb` kurduğunda bile testler
    **bu deponun** paketini import eder (mevcut "The package under test is THIS repository's" adımı korunur ve
    her iki Python işinde geçer).
  - **(d) Mutant M5:** upstream'in kullandığı dört sembolden biri yeniden adlandırılırsa suite **KIRMIZI**.
    `mutant_run.py` → **5/5 yakalandı**, dosyalar bayt-bayt geri döner.
  - Upstream'e bağlı testler Python 3.9 işinde koşamıyorsa bu **ölçülerek** rapora yazılır ve 3.9 işinde
    `skipped = 0` kuralını delmek yerine o test sınıfları **açıkça seçilmez**; K6'nın 3.9 için istediği
    (K1 ve K3/K10'un yeşili) paketin kendi testleri için korunur. Bu durum olursa README'nin "What has not
    been measured" tablosuna yazılır.
- **K15 — `compat.py` kullanımdan kaldırma uyarısı.** `import epson_usb.compat` bir **`DeprecationWarning`**
  verir; mesaj, epson_print_conf **≥ 8.1.1**'in kendi `epson_usb_bridge` köprüsünü adıyla anar. Bunu yakalayan
  bir test vardır (uyarı gelmezse KIRMIZI). `compat.py` dosyası yerinde kalır ve mevcut compat testleri geçer.
  README'deki `compat` bölümü "deprecated" olarak işaretlenir ve upstream'in köprüsünü gösterir.
- **K16 — Sürüm ve CI.** `epson_usb/__version__.py` = `"0.1.3"`. CI'da K1 (yeni taban, `skipped = 0`, çıkış 0),
  K3/K10/K14d (**5/5**) ve K4–K6 **her iki Python işinde yeşil**. PyPI'ye yalnız CI yeşilken yayınlanır;
  `release.yml` yeni imajda (`ubuntu-24.04`) build + publish'i başarıyla tamamlar.

## NE ÖLÇÜLEMEZ (baştan yazıldı)

- Ubuntu 26 imajında Python 3.9/3.10'un sağlanıp sağlanmayacağı — K13 bu belirsizliği ortadan kaldırmak için var.
- Upstream'in Python 3.9'da **çalışma zamanı** uyumu — yalnız sözdizimi ölçüldü.
- `compat.py`'yi gerçekte kimin import ettiği — PyPI indirme sayıları import kullanımını göstermez.
- Pin sabit olduğu için CI, upstream'in **bundan sonraki** değişikliklerini görmez.
