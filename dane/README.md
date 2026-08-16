# Dane z Google Drive (`Projekt - TY100`)

Pliki robocze zsynchronizowane z folderem zespołu na Drive.
Nie zawierają haseł / loginów TMS — te trzymamy poza repo (patrz `docs/karta_projektu_i_wdrozenia.md`).

| Plik | Źródło Drive | Uwagi |
| :--- | :--- | :--- |
| `przykladowe_dane_od_firmy.xlsx` | `dane/przykładowe_dane_od_firmy.xlsx` | Bogaty sample e2open (46 kolumn); kopia też w `tests/fixtures/` |
| `dane_01.04.2026-31.07.2026.xlsx` | arkusz `dane 01.04.2026- 31.07.2026` | Eksport TMS (Ashland / Hargo Antwerp) |
| `carrier_load_status1594822.xlsx` | `dane/` | Dodatkowy sample carrier load |
| `carrier_load_status *.xlsx` (9 plików) | `dane tygodniowe tms/` | Tygodniowe statusy maj–sierpień 2026 |
| `FLota.xlsx` | arkusz `FLota` (Martyna) | Pojemności bus / naczepa; liczby pojazdów nieznane |

Mapowanie floty do seedu aplikacji: [`config/fleet_seed.json`](../config/fleet_seed.json).

## Import tygodniowy (przyrostowe planowanie)

1. W aplikacji: **Zlecenia** → wgraj wybrany `carrier_load_status *.xlsx`.
2. **Plany** → Generuj → zatwierdzaj **pojedyncze trasy** (zajęty pojazd wypada z kolejnych generacji).
3. Kolejny plik weekly = kolejne zlecenia `NEW` → Generuj ponownie (dopełnia wolne auta).

Instrukcja demo: [`docs/walkthrough_incremental_routes.md`](../docs/walkthrough_incremental_routes.md).
