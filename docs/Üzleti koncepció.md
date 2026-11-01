---
projekt: Pénzügyi nyomkövető
tipus: üzleti koncepció
datum: 2026-11-01
tags: [penzugy, projekt]
---

# Háztartási pénzügyi nyomkövető – üzleti koncepció

Kapcsolódó: [[Technikai terv]] · [[Fejlesztési terv]] · [[Sprint 1]]

## Cél és szerkezet

A projekt célja, hogy a háztartás minden kiadása és bevétele egy helyen, visszakereshetően legyen tárolva, és ebből tervezni lehessen: mennyit költünk, mennyi marad, és mikorra jön össze egy tévére vagy egy utazásra.

A klasszikus medallion felosztás üzletileg is értelmes:

1. **Bronz – a „cipősdoboz”:** ide kerül minden blokk, számla és kézi bejegyzés, változatlanul.
2. **Silver – a „könyvelő”:** rendet rak, a nyers adatból értelmezett kiadás és bevétel lesz.
3. **Gold – a „pénzügyi tanácsadó”:** megmondja, mit jelent mindez.
4. **BI eszköz:** egyszerű felület az áttekintéshez és a tervezéshez.

## Bronz – minden, ami bejön, változatlanul

Minden fizetésből rekord lesz, amely nyersen, as-is kerül tárolásra: blokkfotó, PDF számla vagy kézi bejegyzés. Üzletileg itt az alábbiakat kell eldönteni:

- **Feltöltés egy fotóval:** a telefonnal lefotózzuk a blokkot, és megadjuk, ki vásárolt, a blokkon szereplő dátumot, valamint egy vagy több címkét (pl. élelmiszer + háztartás). A címkékből a rendszer tanul, hogy később ne kelljen megadni; a nyers fotó változatlan marad.
- **Két időbélyeg:** mikor töltötték fel, és mikor történt a vásárlás. A kettő gyakran napokkal eltér, mert a blokk a zsebben marad.
- **Ki rögzítette és ki fizetett:** ketten használjuk, és a kettő eltérhet (az egyikünk tölti fel, de a másik fizetett). Ebből látszik később, ki mennyit állt a közös kiadásokból.
- **Források:** blokkfotó (fő csatorna), PDF számla, e-mailben továbbított számla, kézi bejegyzés, elektronikus bérpapír a bevételekhez, kézzel felvitt banki kivonat a blokk nélküli kártyás fizetésekhez.
- **Semmit nem törlünk és nem írunk felül:** a hibát a silverben javítjuk, a bronz marad a bizonyíték.

## Silver – értelmezett, tiszta tranzakciók

A silverbe töltéskor történik a tényleges feldolgozás: a blokkból kiadás lesz. A projekt legfontosabb üzleti döntései ide esnek.

- **Tétel szintű feldolgozás (eldöntve):** minden blokk tételekre bomlik. Így látszik, hogy egy 18 450 Ft-os Lidl-vásárlásból mennyi volt élelmiszer és mennyi háztartási cikk, és követhető egy termék árának változása.
- **Kategorizálás szabályokkal:** a feltöltéskor megadott címkékből és a javításokból szabályok és egy tanuló osztályozó lesz, amely a tételeket a címkék közé sorolja, pl. mosószer → háztartás, sonka → élelmiszer. A silver ezt minden következő blokknál magától alkalmazza, és csak az ismeretlen tételeknél kérdez. A blokkon a nevek gyakran rövidítettek (pl. „MOSÓGÉL 1,1L”), ezért a szabály a név egy részére is illeszkedjen.
- **Alap kategóriák:** élelmiszer, háztartás, lakbér, közlekedés, szórakozás, egészség. Bővíthető.
- **Bolt felismerése:** a bolt is szabály alapján egységesül (pl. „LIDL MO. KFT” és „Lidl” ugyanaz).
- **Duplikációszűrés:** ugyanazt a blokkot kétszer töltik fel, vagy a blokk és a banki tétel ugyanaz a vásárlás.
- **Fizetési mód és fizető fél:** készpénz, kártya, SZÉP-kártya, és ki fizetett: a közös kártya vagy valamelyikünk saját pénze. A SZÉP-kártya külön zseb, nem keveredhet a szabad pénzzel.
- **Belső átvezetések:** a közös kártyára és a célok Revolut-zsebébe utalt összeg nem kiadás, csak pénzmozgás köztünk és a közös kassza között. Ha kiadásként számolnánk, a közös vásárlások kétszer szerepelnének.
- **DRS-betétdíj:** a blokkon fizetett betétdíj nem kiadás, hanem várható pénz, amely visszaváltáskor jön vissza. Külön egyenlegen vezetjük, a kiadásokba nem kerül. Az egyenleg kézzel állítható, és visszaváltáskor nullázható. Ha kiadásként számolnánk, a visszajáró pénz is a havi költést növelné.
- **Bevételek a bérpapírból:** az elektronikus bérpapír alapján személyenként a nettó bevétel, igény szerint a bruttó és a levonások is.
- **Ismétlődő tételek jelölése:** lakbér, előfizetések, hiteltörlesztők. Ezek a tervezés alapjai.

## Gold – üzleti összefüggések

A gold a tervezés alapja; a legfontosabb mutatója a szabad keret.

- Havi bevétel, kiadás és a kettő különbsége, vagyis a megtakarítási ráta, külön a közös háztartásra és mindkettőnkre
- Fix és változó költségek aránya: mennyi pénz megy el magától minden hónapban
- Kategóriatrendek, költségkeret a ténnyel szemben
- **Közös kassza:** a havi befizetések a közös kártya kiadásaival szemben, a kártya egyenlege, és hogy a befizetés fedezi-e a tényleges közös kiadást
- Ki mennyit fizetett saját pénzből közös célra
- Előfizetések listája: mit fizetünk havonta, és tényleg kell-e mind
- Személyes infláció: ugyanazok a termékek hogyan drágultak nálunk, nem a KSH-kosárban
- Hitelek és egyéb tartozások: havi törlesztő összesen, a törlesztők aránya a nettó bevételhez, hátralévő tartozás
- **Szabad keret:** átlagosan mennyi marad havonta, miután minden fix és szokásos kiadás, a törlesztőket és a közös befizetést is beleértve, lement

## A BI eszköz fülei

A felület három nézetből indul: egy közös háztartás fül és egy-egy személyes fül; ezek mellett vannak a funkcionális fülek.

| Fül | Mit mutat |
| --- | --- |
| Közös háztartás | Közös kártya: befizetések, kiadások, egyenleg, javasolt befizetés-emelés |
| Személyes (fejenként egy) | Saját bevétel a bérpapírból, saját kiadások, saját tartozások és célok; mindketten látjuk egymásét |
| Áttekintés | A teljes háztartás képe: ez a hónap az előzőhöz és az átlaghoz képest |
| Kiadások | Kategóriák, boltok, tételek, trendek, szűrhetően arra, ki fizetett, lefúrással egészen a blokkig |
| Költségkeret | Havi limit kategóriánként, jelzés, ha közel jár |
| Hitelek és tartozások | Banki hitelek és egyéb tartozások, törlesztők, hátralévő összeg |
| Célok és tervezés | Megtakarítási célok, szükséges havi összeg, what-if számítások |
| Előrejelzés | Várható jövő havi kiadás az ismétlődő tételek és minták alapján |

### Közös háztartás fül

- Mindketten fix összeget utalunk havonta a közös kártyára; a fül ezt veti össze azzal, amennyit a kártyáról ténylegesen elköltünk.
- Ha a közös kiadás tartósan meghaladja a befizetést, vagy fogy a kártya egyenlege, a fül javaslatot ad: az elmúlt hónapok átlaga alapján mennyivel érdemes emelni a havi utalást, és ez fejenként mennyi (50/50 arányban).
- Fordítva is jelez: ha hónapok óta gyűlik a pénz a kártyán, a befizetés csökkenthető, vagy a többlet mehet egy közös célra.
- Látszik, mely kategóriák húzzák fel a közös kiadást (pl. élelmiszer vagy lakbér).

### Célok és tervezés

- Megadjuk a célt (pl. tévé, 350 000 Ft, karácsonyig), és a rendszer kiszámolja, mennyit kell havonta félrerakni.
- Megnézi, belefér-e a szabad keretbe a tényadatok alapján, nem óhaj szerint.
- What-if: „ha 20%-kal kevesebbet költünk étteremre, két hónappal hamarabb meglesz az utazás”.
- **Közös célok:** a közös célokra (pl. utazás) mindketten egyforma összeget utalunk. Az összeget nem előre rögzítjük: a fül a tervezett kiadások utáni szabad keret alapján javasolja, mennyi menjen most a célra. A pénz külön Revolut-zsebben gyűlik, a fül ennek egyenlegét veti össze a céllal.
- Több cél esetén prioritás: mi élvez elsőbbséget, ha nem fér bele minden.

### Hitelek és tartozások

- Banki hitelenként: hitelező, típus (lakás-, személyi, áruhitel), felvett összeg, hátralévő tartozás, havi törlesztő, kamat, lejárat. Kézzel visszük fel, a törlesztések a kézzel felvitt kivonatból frissülnek.
- **Egyéb tartozások:** kézzel könyvelhető bármilyen más tartozás (pl. családtól kapott kölcsön, egymás közötti tartozás): kinek, mennyi, mikorra, mennyi van már visszafizetve.
- A törlesztők fix költségként csökkentik a szabad keretet.
- Látszik, mikor jár le egy hitel, és onnantól mennyivel nő a szabad keret. Ez közvetlenül visszahat a célokra (pl. „márciustól havi 45 000 Ft-tal több mehet az utazásra”).

## Kockázatok

A legnagyobb kockázat nem technikai, hanem a fegyelem: ha a blokk feltöltése macerás, két hét után abbamarad. Ezért a rögzítés legyen extrém egyszerű (lefotózod, és kész). A banki kivonat importja jó kiegészítés, mert a kártyás fizetéseket blokk nélkül is lefedi.

## Döntések és nyitott kérdések

### Eldöntve

- Ketten használjuk, minden tételnél rögzítjük, ki fizetett: a közös kártya vagy valamelyikünk.
- Külön rögzítjük, ki vásárolt: ő mindig személy, akkor is, ha a közös kártyával fizetett.
- Van egy közös kártya, amelyre mindketten fix összeget utalunk havonta, 50/50 arányban.
- A BI-ban egy közös háztartás fül és fejenként egy személyes fül lesz; egymás személyes fülét is látjuk.
- Közös célokra egyforma összeget utalunk, amelynek nagyságát a tervezett kiadások utáni szabad keret alapján döntjük el.
- A közös célok pénze külön Revolut-zsebben van, így a közös kártya egyenlege csak a mindennapi közös kiadásokat mutatja.
- Tétel szintű feldolgozás a silverben, kategóriák feltöltéskor beállított szabályokkal.
- Alap kategóriák: élelmiszer, háztartás, lakbér, közlekedés, szórakozás, egészség.
- Források: blokkfotó, PDF, e-mailben továbbított számla, kézi bejegyzés, elektronikus bérpapír, kézzel felvitt banki kivonat.
- Hitelek kézzel, mellettük egyéb tartozások is könyvelhetők.
- A DRS-betétdíj nem kiadás: külön, várható összegként vezetjük, kézzel állítható, és visszaváltáskor nullázható.

### Még eldöntendő

- Ha a visszaváltási utalványt egy következő vásárlásnál váltjuk be, a blokk negatív sora magától csökkentse-e a várható betétdíjat? Javaslat: igen, kézzel felülírhatóan.
