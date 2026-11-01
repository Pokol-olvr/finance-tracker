# 0012 Újranyitás és előtöltött javítás az újraolvasás helyett

**Állapot:** elfogadva

**Dátum:** 2026-11-01

## Kontextus

Egy szállítólevél üresnek látszott az Ellenőrzés képernyőn, ezért elvetésre került, és az újrafeltöltése csak „már megvolt” eredményt adott. A modell valójában hiánytalanul elolvasta: a feldolgozó szándékosan nem készít tételeket abból, ami nem kiadás, a képernyő viszont ezt nem mondta ki. Az [[0011-ellenorzes-kepernyo-csomagokkal|ADR 0011]] szerint a döntés nem módosítható, ezért a téves elvetés után nem volt út vissza. Javításkor az üres űrlapon minden sort kézzel kellett volna felvenni.

Felmerült egy újrafeldolgozó gomb. Ezt egy szkennelt A4-es lapon mértük: ugyanazzal a beállítással háromszor betűre ugyanaz a szöveg jött ki, a margók levágása nem adott több tételt, 2000 pixelen pedig a kimenet elérte a tokenhatárt, és kevesebb tétel lett. A modell `temperature: 0` beállítással fut, ezért a változatlan újraolvasás nem hoz mást.

## Döntés

- **Újranyitás:** minden döntés visszavonható. A dokumentum újra döntésre vár, a bronzba `reopened` sor kerül, a korábbi döntés is megmarad. Ez felülírja az ADR 0011 szabályát, hogy a döntés a képernyőn nem módosítható.
- **Újrafeltöltés:** ha egy elvetett dokumentum fájlját töltjük fel újra, a dokumentum modellfutás nélkül újranyílik. Minden más esetben az eredmény marad „már megvolt”.
- **Magyarázat:** ami nem kiadás, annál a képernyő kiírja, hogy a modell elolvasta, és a szöveges olvasat nyitva látszik.
- **Előtöltött javítás:** nem kiadásnál és ismeretlen táblázatú számlánál a feldolgozó `draft` javaslatot ad a szövegből: bolt, dátum, végösszeg, tételek. Ez csak a javítás űrlapját tölti ki, mentés nélkül nem számít adatnak.

## Elvetett alternatívák

- **Újrafeldolgozó gomb a modellre:** a mérés szerint ugyanazt vagy rosszabbat ad, és percekig fut. Rossz fotónál az új fotó a valódi újrapróbálás, mert annak más a hash-e. Jobb szabályoknál a tárolt szöveg eddig is modell nélkül feldolgozódik.
- **Ugyanaz a fájl mindig újra feldolgozva:** eltűnne a duplikációszűrés, és a kétszer feltöltött blokk kétszer számolódna.
- **Szállítólevél tételként:** kétszer számolódna a hozzá tartozó számlával. A javaslat ezt elkerüli, mert csak a felhasználó döntésére lesz belőle adat.
- **Kézi felvétel az üres űrlapon:** működik, de egy hosszú dokumentumnál sok munka és sok elgépelés.

## Következmények

- A `bronze.review_decision` `decision` mezője `reopened` értéket is kap. Egy dokumentumhoz több sor tartozhat, a FIN-406 a legutóbbit veszi, és a `reopened` azt jelenti, hogy nincs érvényes döntés.
- A javaslat lehet hiányos: a kipróbált szállítólevélen a sorok a végösszeg 98,4%-át adták, a hiányzó sort kézzel kell felvenni. Az űrlap az eltérést mutatja.
- A rossz fotó újrapróbálásához továbbra is új fotó vagy szkennelés kell.
