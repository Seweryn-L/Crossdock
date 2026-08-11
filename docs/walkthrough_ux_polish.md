# UX polish — walkthrough

Krótki przegląd zmian UI (język PL, motyw, ustawienia, pulpit).

## Co się zmieniło

- **Język:** statusy z bazy (`new`, `draft`, `approved`, …) pozostają angielskie; w UI widać polskie etykiety (`crossdock/text_pl.py`, `crossdock/ui/labels.py`).
- **Motyw:** slate + teal w `layout.py` (klasy `.cd-card`, `.cd-stat`, `.cd-toolbar`).
- **Ustawienia → Parametry:** zapis do `data/runtime_settings.json`, nakładany na `Settings` (bez sekretów / host / port).
- **Pulpit:** KPI zleceń, ostatni plan, kolejka, ostatni import, skróty nawigacji.
- **Zlecenia:** przycisk „Importuj z Excela” + ukryty upload.
- **Mapa:** strzałki kierunku na odcinkach trasy.
- **Raport Excel:** arkusze „Zapełnienie” / „Oszczędności”, sformatowane nagłówki.

## Szybki check ręczny

1. Zaloguj się → Pulpit pokazuje liczby i skróty.
2. Ustawienia → Parametry: zmień `max_drops_per_route`, zapisz, odśwież — wartość zostaje.
3. Zlecenia: „Importuj z Excela” otwiera wybór pliku.
4. Mapa (po planie): legenda wspomina strzałki kierunku.
5. Raporty → Pobierz Excel → nagłówki pogrubione, arkusze PL.
