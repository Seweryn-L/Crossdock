# Walkthrough: przyrostowe trasy (demo dla firmy)

> Scenariusz nadal aktualny. Stan systemu: [`stan_projektu.md`](stan_projektu.md).

Ścieżka demo pod spotkanie: wgrywanie tygodni → propozycje → akceptacja pojedynczych tras → dopełnianie floty.

## Przygotowanie

1. `uv sync` + `uv run alembic upgrade head`
2. Uruchom aplikację (`uv run python -m crossdock` / zgodnie z README projektu).
3. Ustawienia → Flota: ustaw liczby aktywnych jednostek bus / truck / curtain → **Zastosuj liczby pojazdów**.

## Scenariusz

1. **Import tygodnia** — Zlecenia → wgraj jeden plik z `dane/carrier_load_status *.xlsx` (format e2open).
2. **Generuj plan** — Plany → Generuj. Baner pokazuje wolne / zajęte pojazdy i pulę zleceń `NEW`.
3. **Zatwierdź trasę** — zaznacz wiersz trasy → **Zatwierdź trasę**. Pojazd staje się zajęty; zlecenia trasy → `APPROVED`.
4. **Dopełnij** — Generuj ponownie (działa przy statusie `partial`). Solver bierze tylko `NEW` + wolne pojazdy; zatwierdzone trasy zostają.
5. **Kolejny tydzień** — zaimportuj następny plik weekly; nowe zlecenia wchodzą do puli; powtórz kroki 2–4.
6. **Skrót** — **Zatwierdź wszystkie trasy** zatwierdza pozostałe propozycje; **Odblokuj cały plan** zwalnia wszystkie zajęte pojazdy.

## Co pokazać biznesowi

- Nie ma już „zatwierdź cały plan albo nic”.
- Szacunek palet: bus **131.25 kg/EP**, FTL **≈742 kg/EP** (z `fleet_seed.json`); gdy pojawi się kolumna palet w Excelu — nadpisze szacunek.
- Flota: edycja liczby sztuk per typ, bez ręcznego klepania każdego `BUS-0N`.

Szczegóły techniczne: plan w Cursor (`przyrostowe_trasy_i_flota`); otwarte wejścia W-03/W-04 w [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md).
