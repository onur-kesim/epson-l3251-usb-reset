# KRITER 0.1.2 — `epson-usb` USB arayüz seçimi

> **DONDURULDU — 2 Eki 2026.** Bu dosya `epson-usb` **0.1.2** işinin **İLK commit'idir** ve koddan ÖNCE gelir.
> Bu commit'ten sonra değişirse deneme **BAŞARISIZ** sayılır.
> **Tetik:** Witton-431'in `Ircama/epson_print_conf` #35 saha raporu
> ([issuecomment-5936448547](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5936448547),
> 1 Eki 2026 17:05:17Z). `author_association = NONE`, `user.type = User` → **üçüncü kişi**, bakımcı değil.
> Raporcunun kendi cümlesi: *"One unit, one firmware, so please treat it as a field report."*

## ÖLÇÜLEN KUSUR (2 Eki 2026, koddan okundu)

`epson_usb/backends/libusb.py:240` `select_interface_and_endpoints` sıralaması:
① vendor-specific (sınıf 0xFF) arayüzler · ② diğerleri · eşitlikte **en küçük numara kazanır**.

Raporcunun L3251'i üç arayüz açıyor: **0** = 255/255/255 (vendor-specific) · **1** = printer class ·
**2** = vendor-specific, alt sınıf 170. 0 ve 2 aynı kümede olduğu için **arayüz 0** seçiliyor ve
D4 orada cevap vermiyor (*"D4 Init failed"*). `interface=1` zorlanınca **D4 revision 0x10** alınıyor,
EEPROM okunuyor. Dosyanın kendi docstring'i (satır 23-26) varsayımı yazıyor:
*"Only the vendor-specific interface answers D4"* — bu rapor o varsayımı **çürütüyor**.
CLI'da arayüz seçecek bayrak yok: *"The CLI has no flag to choose the interface, so I used the library directly."*

## KAPSAM

Yalnız **libusb arka ucundaki arayüz seçimi + geri çekilme** ve **CLI bayrağı**. Tek dikey dilim.

## 🔴 KIRMIZI ÇİZGİLER

- **Windows `usbprint` yolunun davranışı DEĞİŞMEZ.** README satır 1-3 onun üstünde duruyor.
- `RKEY`, `WKEY`, `WASTE_ADDRS`, bölenler (6345/3416/1300), D4 el sıkışması, kredi akışı — **dokunulmaz**.
- Ircama'nın `epson_print_conf` profil verisi ve yazma anahtarı **bu paketin işi değildir**; düzeltme
  **sahiplenilmez**, PR/issue **açılmaz** (proje başına 1 açık iş kuralı).
- `compat.py` temizliği ve EPSON-CTRL **soket keşfi** bu sürümün **KAPSAMI DIŞINDA** (0.1.3, ayrı KRITER).
- Yeni **dış bağımlılık YOK**. `PUSH ETME, PR AÇMA, YORUM GÖNDERME` — hepsi Onur'da.

## Yürürlükteki: K1–K6 aynen geçerli

`KRITER.md` (K1–K4, 24 Eyl 2026) ve `KRITER_0.1.1.md` (K5–K6, 25 Eyl 2026) olduğu gibi yürürlüktedir.

## Yeni: K7–K12

- **K7 — Aday listesi.** Sıralı bir **aday arayüz dizisi** döndüren bir yol vardır. Altın küme vakası
  **W1** (Witton-431, #35, 1 Eki 2026) ile — arayüz 0: sınıf 0xFF/alt 0xFF/proto 0xFF · arayüz 1: printer
  class (0x07) · arayüz 2: sınıf 0xFF/alt 0xAA, üçünde de bulk IN **ve** OUT — dönen liste **üç arayüzü de
  içerir** ve **arayüz 1 listededir**. Mevcut `select_interface_and_endpoints` tek-değer davranışını korur:
  bugünkü testler **değişmeden** geçer.
- **K8 — Geri çekilme.** Açılış yolu bir adayda D4 init başarısız olduğunda **sıradaki adayı dener**;
  adaylar bitince hata verir. Ölçüt: `mock` aktarımla, arayüz 0'da D4 init'i **başarısız**, arayüz 1'de
  **başarılı** kılan bir test → açılış **arayüz 1** ile döner ve `DeviceInfo.interface == 1`.
  **Donanım gerekmez.**
- **K9 — CLI bayrağı.** `epson_usb/examples/epson_print_conf_over_usb.py` içinde `--interface N`.
  Verildiğinde **yalnız o arayüz** denenir (otomatik seçim ve geri çekilme devre dışı); verilmediğinde
  bugünkü seçim + K8 geri çekilmesi. `--help` çıktısında görünür.
- **K10 — Mutant 4/4.** `python epson_usb/tests/mutant_run.py` → **4/4 yakalandı**, çıkış 0.
  Mevcut iki mutanta ek olarak: **M3** sıralamayı printer-class adayını eleyecek şekilde boz → suit KIRMIZI.
  **M4** geri çekilme döngüsünü ilk adaydan sonra durdur → suit KIRMIZI.
- **K11 — README.** Saha raporu tablosuna **satır 6**: L3251 (*"identifies as L3250 Series"*), firmware
  XF26P8, Linux, Witton-431, `epson_print_conf` v8.1.2 + `epson_usb`. Raporcunun **kendi cümlesiyle**
  "field report" olarak girer; **"doğrulandı" DENMEZ**. "What has not been measured" tablosuna şu satır
  eklenir: *arayüz geri çekilmesi gerçek donanımda ölçülmedi* — Windows yolu (`usbprint`) bu kodu
  çalıştırmaz, bakımcının makinesinde `libusb` arka ucu Zadig gerektirdiği için koşulmadı.
- **K12 — Sürüm ve CI.** `epson_usb/__version__.py` = `"0.1.2"`. CI'da K1 (`Ran ≥ 66` + yeni testler,
  `skipped = 0`, çıkış 0) ve K10 (4/4) **yeşil**. PyPI'ye yalnız CI yeşilken yayınlanır.

## NE ÖLÇÜLEMEZ (baştan yazıldı)

Bu düzeltme **bakımcının kendi donanımında doğrulanamaz**: Windows `usbprint` yolu bu seçim kodunu hiç
çalıştırmaz, `libusb` arka ucunu Windows'ta koşmak sürücü değişimi (Zadig) ister ve paketin tüm satış
noktası ondan kaçınmaktır. Doğrulama bu yüzden **birim testidir** (K7, K8, K10) ve README bunu açıkça
yazar (K11). Raporcunun cihazında geri çekilmenin fiilen çalıştığı da **ÖLÇÜLMEDİ** — yalnız
`interface=1` zorlamasının çalıştığı rapor edildi.
