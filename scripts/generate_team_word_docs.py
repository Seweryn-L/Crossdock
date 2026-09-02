"""Generate two Word starter packs for the Crossdock tester/docs team."""

# ruff: noqa: RUF001

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

OUT_DIR = Path(__file__).resolve().parents[1] / "docs"


def _set_doc_defaults(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")


def _h(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _p(doc: Document, text: str, *, bold: bool = False) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = bold


def _bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def _numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Number")


def _table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, value in enumerate(row):
            table.rows[r_idx].cells[c_idx].text = value
    doc.add_paragraph()


def build_guide() -> Path:
    doc = Document()
    _set_doc_defaults(doc)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Crossdock — przewodnik użytkownika (szkielet)")
    run.bold = True
    run.font.size = Pt(18)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(
        "Materiały startowe dla dyspozytorów / operacji\n"
        "Stan aplikacji: to, co działa dziś (demo / serwer)\n"
        "Uwaga: w menu planowanie nazywa się „Operacje” (/plans)"
    )

    _h(doc, "1. Po co jest Crossdock")
    _p(
        doc,
        "Crossdock pomaga dyspozytorom łączyć wiele drobniejszych zleceń "
        "w pełniejsze transporty całopojazdowe (FTL) przez magazyn przeładunkowy "
        "(cross-dock).",
    )
    _p(doc, "Problem, który rozwiązuje:", bold=True)
    _bullets(
        doc,
        [
            "rozproszone zlecenia z różnymi terminami i odbiorcami,",
            "niepełne auta i zbędne przejazdy,",
            "ręczne „składanie” ładunków bez wspólnego obrazu dnia.",
        ],
    )
    _p(doc, "Co robi system dziś:", bold=True)
    _bullets(
        doc,
        [
            "przyjmuje zlecenia z pliku Excel (eksport z TMS),",
            "proponuje trasy FTL (co jedzie razem i w jakiej kolejności przystanków),",
            "pokazuje wynik na mapie, w magazynie i w raportach,",
            "pozwala zatwierdzić trasę, oznaczyć ją jako zrealizowaną "
            "oraz zarządzać kolejką / buforem w magazynie.",
        ],
    )

    _h(doc, "2. Typowy dzienny przepływ pracy")
    _numbered(
        doc,
        [
            "Logowanie → /login (na demo: konto admin).",
            "Import zleceń → Zlecenia → Importuj z Excela.",
            "Sprawdzenie wyniku importu (przyjęte / już w bazie / odrzucone / brak w pliku).",
            "Operacje → ustawienie dnia planowania (jeśli symulacja) → Generuj.",
            "Przegląd propozycji: Jedzie / Zostaje / Wymaga uwagi.",
            "Zatwierdź pełne trasy (albo pojedynczo Zatwierdź trasę).",
            "Kontrola na Mapie i w Magazynie (kolejka, w drodze, bufor).",
            "Po powrocie auta: Zrealizowane (Pulpit / Operacje / Magazyn).",
            "Podsumowanie w Raportach (opcjonalnie pobranie Excela).",
        ],
    )
    _p(
        doc,
        "Kolejność krytyczna: Import → Generuj → Zatwierdź → Zrealizowane.",
        bold=True,
    )

    _h(doc, "3. Logowanie i demo na serwerze")
    _h(doc, "Jak się zalogować", 2)
    _numbered(
        doc,
        [
            "Otwórz adres demo (np. http://IP:8080).",
            "Podaj nazwę użytkownika i hasło.",
            "Kliknij Zaloguj się.",
        ],
    )
    _h(doc, "Uwagi dla testerów / firmy", 2)
    _bullets(
        doc,
        [
            "Na demo zwykle jest wspólne konto admin.",
            "Baza jest wspólna — każde importowanie dokłada dane.",
            "Przed dużym importem uzgodnijcie: czy czyścicie zlecenia, "
            "czy pracujecie na rosnącym zbiorze.",
            "Nie usuwajcie „wszystkich zleceń” bez uzgodnienia z zespołem.",
            "Po testach zostawcie krótki opis: co zaimportowano, jaki był "
            "dzień planowania, co zatwierdzono.",
        ],
    )

    _h(doc, "4. Zakładki — co robią i jak z nich korzystać")

    _h(doc, "4.1 Pulpit (/)", 2)
    _p(doc, "Po co: codzienny obraz dnia — co jedzie, co zostaje, co wymaga uwagi.")
    _p(doc, "Zobaczysz m.in.:", bold=True)
    _bullets(
        doc,
        [
            "stan operacyjny (aktualna generacja),",
            "liczniki: Jedzie, Zostaje w magazynie, Wymaga uwagi,",
            "listę Tras w drodze,",
            "skróty do Zleceń / Operacji / Magazynu / Raportów,",
            "podsumowanie ostatniego importu.",
        ],
    )
    _p(doc, "Jak oznaczyć powrót auta", bold=True)
    _numbered(
        doc,
        [
            "Zaznacz trasę w „Trasy w drodze”.",
            "Kliknij Zrealizowane.",
        ],
    )
    _p(doc, "Jak dodać zostające do kolejki", bold=True)
    _numbered(doc, ["Kliknij Dodaj zostające do kolejki."])
    _p(doc, "Jak przejść dalej", bold=True)
    _bullets(doc, ["Otwórz operacje", "Pokaż na mapie"])

    _h(doc, "4.2 Zlecenia (/orders)", 2)
    _p(doc, "Po co: import Excela i przegląd aktywnych zleceń.")
    _p(doc, "Główne działania:", bold=True)
    _bullets(
        doc,
        [
            "Importuj z Excela (.xlsx / .xls),",
            "filtry terminu i statusu,",
            "Odśwież,",
            "Usuń zaznaczone / Usuń wszystkie (ostrożnie na demo),",
            "Zmień palety (tylko dla zlecenia zatwierdzonego, jedno zaznaczenie).",
        ],
    )
    _p(doc, "Jak zaimportować plik", bold=True)
    _numbered(
        doc,
        [
            "Wejdź w Zlecenia.",
            "Kliknij Importuj z Excela.",
            "Wybierz raport (docelowo format firmy: nagłówek w 3. wierszu).",
            "Sprawdź podsumowanie: przyjęto / pominięto / brak w pliku / odrzucono.",
            "Odfiltruj status Nowe i sprawdź, czy widać świeże kody dostawy.",
        ],
    )
    _p(doc, "Statusy zlecenia (język UI):", bold=True)
    _bullets(
        doc,
        [
            "nowe → do planowania,",
            "zaplanowane → w propozycji,",
            "zatwierdzone → trasa zatwierdzona / w drodze,",
            "zrealizowane → dostawa zamknięta.",
        ],
    )

    _h(doc, "4.3 Operacje (/plans) — planowanie FTL", 2)
    _p(doc, "Po co: serce dnia — generowanie, zatwierdzanie i realizacja tras.")
    _p(doc, "Główne przyciski:", bold=True)
    _bullets(
        doc,
        [
            "Generuj — liczy propozycje; nie rusza tras już zatwierdzonych/zrealizowanych,",
            "Zatwierdź pełne trasy — zatwierdza trasy gotowe do wysyłki,",
            "Zatwierdź trasę — ręcznie, także słabsze auto,",
            "Zrealizowane — zamyka trasę, zwalnia pojazd,",
            "Odblokuj trasę / Odblokuj zatwierdzone — powrót do propozycji "
            "(nie dla zrealizowanych),",
            "Pokaż na mapie,",
            "Zaawansowane — historia generacji, nazwa, pusta generacja, usuwanie,",
            "Dzień planowania + Zastosuj dzień / Następny dzień.",
        ],
    )
    _p(doc, "Jak wygenerować plan", bold=True)
    _numbered(
        doc,
        [
            "Zaimportuj zlecenia.",
            "Ustaw Dzień planowania (jeśli pokaz / symulacja).",
            "Kliknij Generuj i poczekaj na wynik.",
            "Sprawdź: ile tras propozycja, ile zleceń zostaje, co wymaga uwagi.",
        ],
    )
    _p(doc, "Jak zatwierdzić wysyłkę", bold=True)
    _numbered(
        doc,
        [
            "Przejrzyj trasy ze statusem propozycja.",
            "Kliknij Zatwierdź pełne trasy albo zaznacz i Zatwierdź trasę.",
            "Sprawdź, że zlecenia przeszły na zatwierdzone, a pojazdy są zajęte.",
        ],
    )
    _p(doc, "Jak zamknąć dzień trasy", bold=True)
    _numbered(
        doc,
        [
            "Zaznacz trasę zatwierdzoną.",
            "Kliknij Zrealizowane.",
        ],
    )
    _p(
        doc,
        "Co system maksymalizuje przy Generuj, jakie są twarde limity "
        "i kolejność etapów — w rozdziale 5.2.",
    )

    _h(doc, "4.4 Mapa (/map)", 2)
    _p(
        doc,
        "Po co: wizualna kontrola tras bieżącego stanu (lub wybranej generacji z Raportów).",
    )
    _bullets(
        doc,
        [
            "magazyn i punkty rozładunku,",
            "linie tras (schemat w linii prostej magazyn ↔ przystanki),",
            "legenda pojazdów, filtry statusu, strzałki kierunku.",
        ],
    )
    _p(doc, "Jak korzystać", bold=True)
    _numbered(
        doc,
        [
            "Wygeneruj plan w Operacjach.",
            "Wejdź w Mapę lub kliknij Pokaż na mapie.",
            "Najedź na trasę (skrót) / kliknij (szczegóły).",
            "Odfiltruj statusy lub ukryj wybrane pojazdy w legendzie.",
        ],
    )

    _h(doc, "4.5 Magazyn (/warehouse)", 2)
    _p(doc, "Po co: stan hubu, kolejka wydań, trasy w drodze, propozycja buforowania.")
    _numbered(
        doc,
        [
            "Stan magazynu — kg vs pojemność, najbliższy wyjazd.",
            "Do kolejki — zlecenia nowe jeszcze poza kolejką → Dodaj do kolejki.",
            "Kolejka wydań — W górę / W dół / Wstrzymaj / Wznów / Usuń z kolejki.",
            "W drodze — zatwierdzone trasy → Zrealizowane.",
            "Propozycja buforowania — Odśwież propozycję → tabela tylko "
            "„przytrzymaj” → Akceptuj przytrzymanie. "
            "„Wyślij teraz” tylko w podsumowaniu (bez akcji na Magazynie).",
        ],
    )
    _p(doc, "Jak ustawić priorytet wyjazdu", bold=True)
    _numbered(
        doc,
        [
            "Dodaj zlecenie do kolejki.",
            "Przesuń je W górę (pozycja 1 jest traktowana jako pilna).",
            "Albo Wstrzymaj, jeśli ma poczekać.",
        ],
    )
    _p(doc, "Jak użyć bufora", bold=True)
    _numbered(
        doc,
        [
            "Kliknij Odśwież propozycję.",
            "W tabeli są tylko propozycje przytrzymania (dni, oszczędność %).",
            "Zaznacz pozycje i Akceptuj przytrzymanie.",
        ],
    )
    _p(
        doc,
        "Wzory „przytrzymaj vs wyślij teraz” — w rozdziale 5.3.",
    )

    _h(doc, "4.6 Raporty (/reports)", 2)
    _p(doc, "Po co: efektywność bieżącego stanu + historia generacji.")
    _bullets(
        doc,
        [
            "zapełnienie wagowe, km, koszt €, status tras,",
            "podsumowanie oszczędności względem scenariusza „1 zlecenie = 1 pojazd”,",
            "historia generacji (audyt),",
            "Podgląd na mapie (nie zmienia bieżącego stanu Operacji),",
            "Pobierz Excel (arkusze Zapełnienie / Oszczędności).",
        ],
    )
    _p(doc, "Jak pobrać raport", bold=True)
    _numbered(
        doc,
        [
            "Wejdź w Raporty.",
            "Sprawdź podsumowanie oszczędności.",
            "Kliknij Pobierz Excel.",
        ],
    )
    _p(
        doc,
        "Wzory oszczędności (€ i %) oraz skąd biorą się stawki — w rozdziale 5.1.",
    )

    _h(doc, "4.7 Stan systemu (/system)", 2)
    _p(
        doc,
        "Po co: zdrowie aplikacji na serwerze demo / lokalnie. "
        "Ekran dla opiekuna demo, nie codzienny ekran dyspozytora.",
    )
    _bullets(
        doc,
        [
            "ścieżka i rozmiar bazy, wolne miejsce,",
            "ostatnia generacja, ostatni import, ostatnia kopia, ogon logów,",
            "przyciski: Odśwież, Utwórz kopię teraz, Pokaż log.",
        ],
    )

    _h(doc, "4.8 Ustawienia (ikona ustawień)", 2)
    _p(doc, "Po co: flota, współrzędne lokalizacji, parametry biznesowe.")
    _bullets(
        doc,
        [
            "Flota — liczba aktywnych bus / truck / curtain, edycja pojazdów,",
            "Lokalizacje — słownik współrzędnych, uzupełnianie koordynat w zleceniach,",
            "Parametry — min. zapełnienie, maks. punktów rozładunku, dzień planowania, "
            "stawki, bufor, backup itd.",
        ],
    )
    _p(
        doc,
        "Ważne: po zmianie parametrów trzeba zwykle wygenerować plan od nowa. "
        "Stary szkic sam się nie przeliczy.",
        bold=True,
    )

    _h(doc, "5. Logika systemu — oszczędności, planowanie, bufor")
    _p(
        doc,
        "Ten rozdział wyjaśnia, jak system liczy wyniki — nie „gdzie kliknąć”, "
        "tylko logikę biznesową za Raportami, Generuj i propozycją buforowania. "
        "Stawki i progi pochodzą z Ustawienia → Parametry (domyślne wartości "
        "poniżej — do uzgodnienia z firmą).",
    )

    _h(doc, "5.1 Oszczędności (Raporty / KPI)", 2)
    _p(doc, "Baseline (koszt odniesienia)", bold=True)
    _p(
        doc,
        "System porównuje plan z scenariuszem „1 zlecenie = 1 pojazd”: "
        "każde zlecenie, które faktycznie weszło na trasę, jedzie samotnie "
        "w obie strony (magazyn → odbiorca → magazyn).",
    )
    _p(doc, "Oznaczenia", bold=True)
    _bullets(
        doc,
        [
            "dᵢ — odległość magazyn–odbiorca zlecenia i (linia prosta; "
            "tylko zlecenia z współrzędnymi wchodzą do baseline),",
            "s — stawka €/km (Parametry: Stawka €/km, cost_per_km; domyślnie 1,20),",
            "K_odniesienia — suma kosztów samotnych przejazdów,",
            "K_plan — koszt zoptymalizowany = suma kosztów tras planu (każda trasa: km trasy × s),",
            "N — liczba zleceń na trasach (bez nieprzydzielonych).",
        ],
    )
    _p(doc, "Wzory", bold=True)
    _bullets(
        doc,
        [
            "K_odniesienia = Σᵢ (2 × dᵢ × s)   dla wszystkich zleceń na trasach",
            "K_plan = Σ_tras (km_trasy × s)",
            "Oszczędność € = K_odniesienia − K_plan",
            "Oszczędność % = (Oszczędność € / K_odniesienia) × 100   (gdy K_odniesienia = 0 → 0%)",
        ],
    )
    _p(
        doc,
        "Uwaga: to szacunek ze stawek w Parametrach, nie faktura przewoźnika. "
        "Zapełnienie wagowe w raporcie = waga na aucie / ładowność pojazdu.",
    )
    _p(doc, "Przykład liczbowy", bold=True)
    _p(
        doc,
        "Dwa zlecenia do tego samego odbiorcy, d = 100 km, s = 1,20 €/km. "
        "Baseline: 2 × (2 × 100 × 1,20) = 480 €. "
        "Plan (jedno auto, jeden przystanek, tam i z powrotem): 200 × 1,20 = 240 €. "
        "Oszczędność = 240 € (50%).",
    )

    _h(doc, "5.2 Optymalizacja doboru do pojazdów (planowanie FTL)", 2)
    _p(
        doc,
        "Po Generuj system uruchamia algorytm optymalizacyjny w dwóch etapach. "
        "To nie jest jeden rachunek „znajdź najtańsze trasy”.",
    )
    _p(doc, "Etapy", bold=True)
    _numbered(
        doc,
        [
            "Przydział do pojazdów — co jedzie z czym (pakowanie ładunku).",
            "Kolejność dropów — w jakiej kolejności auto odwiedza punkty rozładunku.",
            "Koszt / km — po ułożeniu trasy: koszt_trasy = km_trasy × stawka €/km "
            "(stawka nie decyduje, kto z kim jedzie).",
        ],
    )
    _p(doc, "Co system maksymalizuje / minimalizuje", bold=True)
    _bullets(
        doc,
        [
            "Etap 1: maksymalizuje sumę kilogramów spakowanych na auta "
            "(zapełnienie wagowe floty). Zlecenia, które muszą wyjechać dziś "
            "(ostatni dzień wyjazdu, spóźnione, pozycja 1 w kolejce, overflow magazynu), "
            "dostają silną premię — mają pierwszeństwo przed cięższymi, ale niepilnymi.",
            "Etap 2: dla każdego załadowanego auta minimalizuje sumę odcinków "
            "magazyn → przystanki → magazyn (linia prosta).",
            "Euro nie jest celem pakowania — pojawia się dopiero po policzeniu km.",
        ],
    )
    _p(doc, "Twarde ograniczenia (język biznesowy)", bold=True)
    _bullets(
        doc,
        [
            "Nierozdzielność — całe zlecenie (wszystkie przesyłki pod jednym kodem) "
            "jedzie na jednym aucie; system nigdy nie dzieli zlecenia między pojazdy.",
            "Pojemność pojazdu (kg) — suma wag na aucie ≤ ładowność. "
            "Zlecenie cięższe niż największe auto wypada z planu.",
            "Limit punktów rozładunku — na jednej trasie najwyżej N różnych "
            "odbiorców/adresów (Parametry: maks. punktów rozładunku; domyślnie 3). "
            "Ten sam odbiorca = jeden przystanek. Przy nadmiarze zostają punkty "
            "najbliższe magazynowi (przy remisie: cięższe); reszta wraca do „zostaje”.",
            "Próg minimalnego zapełnienia — nie blokuje pakowania. Po spakowaniu "
            "decyduje Jedzie vs Czeka na dopełnienie: gdy zapełnienie < próg "
            "(domyślnie 90%) i wszystkie zlecenia na trasie mają luz SLA > 0, "
            "trasa zostaje w magazynie na dopełnienie. "
            "„Zatwierdź pełne trasy” takich tras nie bierze; dyspozytor może "
            "wymuszyć wyjazd ręcznie (Zatwierdź trasę).",
            "SLA / termin wyjazdu — must_leave_by = termin u odbiorcy − wyjazd przed "
            "terminem (domyślnie 2 dni); luz = must_leave_by − dzień planowania T. "
            "Przy luzie ≤ 0 trasa jedzie nawet poniżej progu zapełnienia. "
            "Wyjazd w dniu dostawy u odbiorcy nie jest legalny.",
        ],
    )
    _p(doc, "Przykład (uproszczony)", bold=True)
    _p(
        doc,
        "Trzy zlecenia po 8 t, dwa auta po 24 t, limit 3 punktów, min. zapełnienie 90%. "
        "Algorytm pakuje np. 24 t na auto A (100%) i zostawia 8 t poza FTL, "
        "jeśli drugie auto nie da się sensownie zapełnić innymi zleceniami dnia — "
        "priorytet mają kg i pilność, nie „ładny” kierunek geograficzny. "
        "Potem dla auta A układa kolejność przystanków pod najkrótszą sumę odcinków.",
    )

    _h(doc, "5.3 Buforowanie (Magazyn — propozycja)", 2)
    _p(
        doc,
        "Osobna logika na Magazynie („Propozycja buforowania”), nie część Generuj. "
        "Dla zlecenia, które nie weszło do pełnego FTL, system porównuje dwa warianty.",
    )
    _p(doc, "Kiedy „przytrzymaj”, a kiedy „wyślij teraz”", bold=True)
    _bullets(
        doc,
        [
            "Wyślij teraz — gdy brak luzu SLA (luz ≤ 0) albo gdy przytrzymanie "
            "nie daje wymaganej oszczędności względem progu.",
            "Przytrzymaj N dni — gdy koszt „magazyn + później FTL” jest niższy "
            "od „wyślij teraz jako drobnica” o co najmniej próg oszczędności "
            "(Parametry; domyślnie 15%). System bierze najkrótsze N od 1 do "
            "maks. dni buforowania (domyślnie 3), ścięte do dostępnego luzu.",
        ],
    )
    _p(doc, "Oznaczenia i wzory", bold=True)
    _bullets(
        doc,
        [
            "d — odległość magazyn–odbiorca,",
            "s — stawka €/km,",
            "m — mnożnik drobnicy (ltl_cost_multiplier; domyślnie 1,8),",
            "p — liczba palet (gdy brak w danych → przyjmuje 1),",
            "c — koszt magazynowania €/paleta/dzień (storage_cost_per_pallet_day; domyślnie 2,00),",
            "τ — próg oszczędności (buffer_savings_threshold; domyślnie 0,15 = 15%).",
            "K_teraz = 2 × d × s × m",
            "K_FTL = 2 × d × s",
            "K_bufor(N) = (p × N × c) + K_FTL",
            "Przytrzymaj, gdy K_bufor(N) ≤ K_teraz × (1 − τ); "
            "oszczędność względna = (K_teraz − K_bufor) / K_teraz",
        ],
    )
    _p(
        doc,
        "Kwoty są szkicem kosztowym ze stawek w Parametrach, nie cennikiem przewoźnika.",
    )
    _p(doc, "Przykład liczbowy", bold=True)
    _p(
        doc,
        "d = 100 km, s = 1,20, m = 1,8, p = 2, c = 2,00, τ = 15%. "
        "K_FTL = 240 €; K_teraz = 432 €. "
        "Przy N = 1: magazyn 4 € + FTL 240 € = 244 €. "
        "Oszczędność ≈ 43,5% ≥ 15% → propozycja: przytrzymaj 1 dzień.",
    )

    _h(doc, "6. Słownik pojęć (język biznesowy)")
    _table(
        doc,
        ["Pojęcie", "Znaczenie w Crossdock"],
        [
            [
                "Zlecenie",
                "Jednostka planowania (kod dostawy, odbiorca, termin, waga, palety). "
                "Przesyłki pod jednym zleceniem jadą zawsze razem.",
            ],
            [
                "Przesyłka",
                "Numer shipment przypięty do zlecenia; system ich nie rozdziela.",
            ],
            [
                "Generacja / plan",
                "Wynik jednego uruchomienia Generuj (stan roboczy lub częściowo/zatwierdzony).",
            ],
            [
                "Trasa",
                "Załadunek jednego pojazdu: przystanki i zlecenia. "
                "Statusy: propozycja → zatwierdzona → zrealizowana.",
            ],
            [
                "Zatwierdzenie",
                "Decyzja dyspozytora: trasa blokowana, pojazd zajęty, zlecenia zatwierdzone.",
            ],
            [
                "Zrealizowane",
                "Trasa zakończona: zlecenia dostarczone, pojazd wolny. Nie cofa się przez Generuj.",
            ],
            [
                "Jedzie",
                "Trasy gotowe do zatwierdzenia lub już zatwierdzone "
                "(w zależności od kontekstu ekranu).",
            ],
            ["Zostaje", "Zlecenia poza pełnym FTL / czekające na dopełnienie."],
            ["Kolejka", "Lista wydań w magazynie z priorytetem pozycji."],
            ["Wstrzymane", "Pozycja kolejki celowo niejedzie."],
            [
                "Bufor / przytrzymaj",
                "Świadome odłożenie wysyłki, gdy późniejszy FTL wychodzi taniej "
                "niż wysyłka „teraz”.",
            ],
            [
                "Dzień planowania",
                "Sztuczne „dziś” do symulacji i SLA; może różnić się od daty kalendarzowej.",
            ],
            ["Luz [dni]", "Ile dni zostało do ostatniego legalnego wyjazdu."],
            [
                "Wymaga uwagi",
                "Braki danych (np. współrzędne) lub limity uniemożliwiające czyste zaplanowanie.",
            ],
        ],
    )

    _h(doc, "7. Czego NIE obiecywać w dokumentacji firmowej")
    _bullets(
        doc,
        [
            "Automatyczne API TMS e2open — dziś jest ręczny import Excela.",
            "Śledzenie GPS / lokalizacja kierowcy na żywo — brak.",
            "Trasy po drogach / nawigacja — w produkcie domyślnie schemat w linii prostej; "
            "nie opisuj jako GPS ani jako gotową nawigację drogową.",
            "Automatyczny import 2× dziennie — jeszcze nie; import jest ręczny.",
            "Planowanie czasu pracy kierowców / tachograf — poza zakresem.",
            "Optymalizacja po paletach/objętości przy pakowaniu — pakowanie opiera się "
            "głównie na kilogramach i limicie punktów.",
            "Cennik przewoźnika „1:1” — koszty/oszczędności to szacunek ze stawek w Ustawieniach.",
            "Samoczynne przeliczanie wszystkich dni tygodnia — każdy dzień T wymaga "
            "osobnego Generuj.",
            "Gwarancja optymalnego kosztu globalnego — system najpierw pakuje kg, "
            "potem układa kolejność; euro liczone jest po fakcie.",
        ],
    )

    _h(doc, "8. Mini-procedury „jak zrobić X”")
    _h(doc, "Import dnia", 2)
    _numbered(
        doc,
        [
            "Zlecenia → Importuj z Excela",
            "Sprawdź deltę importu",
            "Odśwież listę (status: aktywne / nowe)",
        ],
    )
    _h(doc, "Plan FTL", 2)
    _numbered(
        doc,
        [
            "Operacje → Dzień planowania",
            "Generuj",
            "Przejrzyj trasy i „zostaje”",
            "Zatwierdź pełne trasy",
        ],
    )
    _h(doc, "Kontrola jakości planu", 2)
    _numbered(
        doc,
        [
            "Mapa — czy kierunki/przystanki mają sens",
            "Magazyn — kolejka i overflow",
            "Raporty — zapełnienie / km / koszt",
        ],
    )
    _h(doc, "Zamknięcie trasy", 2)
    _numbered(
        doc,
        [
            "Pulpit lub Magazyn → Trasy w drodze",
            "Zaznacz → Zrealizowane",
        ],
    )
    _h(doc, "Przytrzymanie towaru", 2)
    _numbered(
        doc,
        [
            "Magazyn → Odśwież propozycję",
            "Akceptuj przytrzymanie (tylko wiersze w tabeli)",
            "Albo ręcznie: kolejka → Wstrzymaj",
        ],
    )

    _h(doc, "9. Załącznik — checklista codziennej pracy")
    _bullets(
        doc,
        [
            "[ ] Logowanie",
            "[ ] Import Excela i kontrola delty",
            "[ ] Generuj w Operacjach",
            "[ ] Przegląd Jedzie / Zostaje / Wymaga uwagi",
            "[ ] Zatwierdzenie tras",
            "[ ] Kontrola na Mapie",
            "[ ] Kolejka / bufor w Magazynie (jeśli potrzeba)",
            "[ ] Zrealizowane po powrocie",
            "[ ] Raport / zapis co zrobiono na demo",
        ],
    )

    path = OUT_DIR / "Crossdock_przewodnik_uzytkownika.docx"
    doc.save(path)
    # Kopia w katalogu głównym — wygodny plik do oddania firmie / zespołowi.
    root_copy = Path(__file__).resolve().parents[1] / "Crossdock_przewodnik_uzytkownika.docx"
    doc.save(root_copy)
    return path


def build_roles() -> Path:
    doc = Document()
    _set_doc_defaults(doc)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Crossdock — podział obowiązków (3 osoby)")
    run.bold = True
    run.font.size = Pt(18)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(
        "Testy aplikacji + jednolita dokumentacja użytkownika dla firmy\n"
        "Każda osoba: zakres testów + rozdziały dokumentacji + kryteria done"
    )

    _h(doc, "1. Cel pracy zespołu")
    _numbered(
        doc,
        [
            "Przetestować aplikację Crossdock na rzeczywistym stanie (demo / serwer).",
            "Napisać jedną spójną dokumentację użytkownika dla dyspozytorów / operacji.",
        ],
    )
    _p(
        doc,
        "Zasada: najpierw testy krytycznej ścieżki i backlog błędów, "
        "potem dokumentacja szczegółowa.",
        bold=True,
    )

    _h(doc, "2. Wspólny spis treści dokumentacji firmowej")
    _numbered(
        doc,
        [
            "Wstęp: po co Crossdock",
            "Logowanie i pierwsze uruchomienie (demo)",
            "Słownik pojęć i statusów",
            "Przepływ dnia (krytyczna ścieżka)",
            "Zlecenia — import i przegląd",
            "Operacje — generowanie, zatwierdzanie, realizacja",
            "Mapa — odczyt tras",
            "Magazyn — kolejka, w drodze, bufor",
            "Raporty — efektywność i historia",
            "Ustawienia — flota, lokalizacje, parametry",
            "Stan systemu — kopie i logi",
            "Logika systemu — oszczędności, planowanie FTL, bufor (wzory)",
            "Czego system nie robi (ograniczenia)",
            "FAQ / typowe problemy",
            "Załącznik: checklista codziennej pracy",
        ],
    )

    _h(doc, "3. Osoba 1 — Operacje i plany (lead krytycznej ścieżki)")
    _p(
        doc,
        "Rola: właściciel ścieżki Import → Generuj → Zatwierdź → Zrealizowane.",
        bold=True,
    )
    _h(doc, "Zakres ekranów", 2)
    _bullets(
        doc,
        [
            "Logowanie",
            "Pulpit (skróty, trasy w drodze, Dodaj zostające…)",
            "Operacje (całość przycisków dnia + dzień planowania)",
            "Raporty (podstawowy odczyt oszczędności po zatwierdzeniu)",
        ],
    )
    _h(doc, "Checklista testów", 2)
    _bullets(
        doc,
        [
            "[ ] Logowanie admin działa; złe hasło daje komunikat",
            "[ ] Po imporcie Pulpit pokazuje sensowne liczniki",
            "[ ] Generuj kończy się wynikiem (nie zawiesza UI)",
            "[ ] Zatwierdź pełne trasy zmienia statusy zleceń/tras",
            "[ ] Zatwierdź trasę działa dla pojedynczej słabej trasy",
            "[ ] Kolejne Generuj nie niszczy tras zatwierdzonych/zrealizowanych",
            "[ ] Odblokuj trasę wraca do propozycji (gdy dozwolone)",
            "[ ] Zrealizowane zwalnia pojazd",
            "[ ] Następny dzień + Generuj ma sens w symulacji",
            "[ ] Usuwanie generacji jest zablokowane, gdy jest trasa zrealizowana",
        ],
    )
    _h(doc, "Rozdziały dokumentacji", 2)
    _bullets(
        doc,
        [
            "1 Wstęp",
            "3 Słownik (statusy — wersja kanoniczna)",
            "4 Przepływ dnia",
            "6 Operacje",
            "12.2 Logika — optymalizacja doboru / kolejność tras",
            "fragment 15 (checklista dnia: kroki 1–4)",
        ],
    )
    _h(doc, "Kryteria done", 2)
    _bullets(
        doc,
        [
            "Krytyczna ścieżka przetestowana na demo end-to-end",
            "Rozdziały 1/3/4/6 gotowe, bez żargonu IT",
            "Spis statusów uzgodniony z Osobami 2 i 3 (jedna tabela)",
        ],
    )
    _h(doc, "Zależności", 2)
    _bullets(
        doc,
        [
            "Czeka na Osobę 3 tylko w kwestii „jak opisać import” "
            "(linkuje do rozdz. 5, nie duplikuje)",
            "Ustala nazwy przycisków używane potem przez wszystkich",
        ],
    )

    _h(doc, "4. Osoba 2 — Magazyn i mapa")
    _p(doc, "Rola: wizualizacja i decyzje magazynowe.", bold=True)
    _h(doc, "Zakres ekranów", 2)
    _bullets(
        doc,
        [
            "Mapa",
            "Magazyn (stan, kolejka, w drodze, bufor)",
            "Pulpit (tylko spójność „w drodze” / kolejka)",
        ],
    )
    _h(doc, "Checklista testów", 2)
    _bullets(
        doc,
        [
            "[ ] Mapa pokazuje trasy po Generuj",
            "[ ] Legenda: ukryj/pokaż pojazdy, filtr statusu",
            "[ ] Klik/hover na trasie daje zrozumiały opis",
            "[ ] Kandydaci → Dodaj do kolejki",
            "[ ] W górę / w dół / wstrzymaj / wznów / usuń z kolejki",
            "[ ] Pozycja 1 wpływa na pilność (obserwacja po Generuj)",
            "[ ] W drodze → Zrealizowane działa tak samo jak na Pulpicie",
            "[ ] Odśwież propozycję bufora + Akceptuj przytrzymanie",
            "[ ] Stan kg / pojemność / ostrzeżenie overflow (jeśli da się wywołać)",
            "[ ] Jeśli OSRM wyłączone: linie są „proste” — zanotować do ograniczeń",
        ],
    )
    _h(doc, "Rozdziały dokumentacji", 2)
    _bullets(
        doc,
        [
            "7 Mapa",
            "8 Magazyn",
            "12.3 Logika — buforowanie (wzory przytrzymaj / wyślij teraz)",
            "część 13 (ograniczenia mapy/GPS — bez obiecywania nawigacji drogowej)",
            "FAQ: „dlaczego trasa nie idzie drogami?”, „co znaczy luz?”",
        ],
    )
    _h(doc, "Kryteria done", 2)
    _bullets(
        doc,
        [
            "Scenariusze magazyn+mapa przetestowane",
            "Rozdziały 7–8 kompletne ze zrzutami",
            "W ograniczeniach jasno: brak GPS; OSRM tylko jeśli włączone",
        ],
    )
    _h(doc, "Zależności", 2)
    _bullets(
        doc,
        [
            "Nie opisuje szczegółów Generuj/Zatwierdź (odsyła do Osoby 1)",
            "Używa słownika statusów z Osoby 1 bez synonimów",
        ],
    )

    _h(doc, "5. Osoba 3 — Dane, ustawienia, stabilność demo")
    _p(
        doc,
        "Rola: jakość danych wejściowych, parametry, higiena wspólnego serwera.",
        bold=True,
    )
    _h(doc, "Zakres ekranów", 2)
    _bullets(
        doc,
        [
            "Zlecenia (import, filtry, palety, usuwanie)",
            "Ustawienia (flota / lokalizacje / parametry)",
            "Stan systemu (backup, logi, metryki)",
            "Raporty (eksport Excel + historia → podgląd mapy)",
        ],
    )
    _h(doc, "Checklista testów", 2)
    _bullets(
        doc,
        [
            "[ ] Import przykładowego pliku firmowego działa",
            "[ ] Ponowny import tego samego kodu = pominięcie (bez duplikatu)",
            "[ ] Widok delty: już w bazie / brak w pliku / błędy wierszy",
            "[ ] Filtry terminu/statusu nie gubią aktywnych zleceń",
            "[ ] Zmień palety tylko dla zatwierdzonego",
            "[ ] Ustawienia floty: zmiana liczby aktywnych pojazdów",
            "[ ] Lokalizacje: zapis + uzupełnij współrzędne w zleceniach",
            "[ ] Parametry: min. zapełnienie / max drops / dzień planowania zapisują się",
            "[ ] Raport: Pobierz Excel; historia → Podgląd na mapie nie zmienia bieżącego stanu",
            "[ ] Stan systemu: Utwórz kopię teraz; Pokaż log",
            "[ ] Zasady pracy na wspólnym demo: dane rosną, nie kasować „wszystkiego” "
            "bez uzgodnienia",
        ],
    )
    _h(doc, "Rozdziały dokumentacji", 2)
    _bullets(
        doc,
        [
            "2 Logowanie i demo",
            "5 Zlecenia",
            "9 Raporty",
            "10 Ustawienia",
            "11 Stan systemu",
            "12.1 Logika — oszczędności (€ / %) i stawki z Parametrów",
            "reszta 13 + FAQ danych („brak współrzędnych”, „import nic nie przyjął”)",
        ],
    )
    _h(doc, "Kryteria done", 2)
    _bullets(
        doc,
        [
            "Import i ustawienia opisane krok po kroku",
            "Sekcja demo: wspólna baza, przyrost danych, backup",
            "Załącznik checklisty dnia: kroki importu i kontroli danych",
        ],
    )
    _h(doc, "Zależności", 2)
    _bullets(
        doc,
        [
            "Nie duplikuje opisu Generuj (Osoba 1)",
            "Nie duplikuje kolejki/bufora (Osoba 2) — tylko linkuje",
        ],
    )

    _h(doc, "6. Wspólne konwencje pisania")
    _numbered(
        doc,
        [
            "Nazwy UI dokładnie jak na przycisku: Generuj, Zatwierdź pełne trasy, "
            "Zrealizowane, Importuj z Excela.",
            "Statusy tylko z UI: nowe / zaplanowane / zatwierdzone / zrealizowane; "
            "trasy: propozycja / zatwierdzona / zrealizowana.",
            "Zakładka planowania = Operacje (nie „Plany”, chyba że raz w nawiasie).",
            "Język polski, bezosobowo: „Kliknij…”, „Sprawdź…”.",
            "Zrzuty: numerowane rys. X, strzałka na przycisk, krótki podpis.",
            "Każdy rozdział: Po co → Kiedy używać → Jak zrobić → Czego unikać.",
            "Ograniczenia zawsze w osobnej sekcji.",
            "Nie używać żargonu IT (solver, CP-SAT, OR-Tools itd.).",
        ],
    )

    _h(doc, "7. Jeden backlog błędów — szablon zgłoszenia")
    _table(
        doc,
        ["Pole", "Treść"],
        [
            ["ID", "CD-001"],
            ["Data / osoba", ""],
            ["Środowisko", "demo serwer / lokal"],
            ["Ekran", "Operacje / Magazyn / …"],
            ["Kroki", "1. … 2. …"],
            ["Dane", "jaki Excel, ile zleceń, dzień planowania"],
            ["Oczekiwane", ""],
            ["Faktyczne", ""],
            ["Załączniki", "zrzut / ID generacji / kod dostawy"],
            ["Priorytet", "blocker / major / minor"],
            ["Status", "nowe / w toku / poprawione / odrzucone"],
        ],
    )
    _p(
        doc,
        "Zasada: najpierw zgłoszenie, potem dokumentacja omija dziurę albo opisuje "
        "workaround — nie ukrywamy błędu w instrukcji jako „tak ma być”.",
    )

    _h(doc, "8. Harmonogram współpracy (4–5 dni)")
    _table(
        doc,
        ["Dzień", "Co robi zespół"],
        [
            [
                "D0 (1–2 h)",
                "Kick-off: wspólne przejście krytycznej ścieżki na demo; "
                "Osoba 1 prowadzi; uzgodnienie słownika i spisu treści",
            ],
            [
                "D1",
                "Testy krytycznej ścieżki (Os.1) + import/dane (Os.3); "
                "Os.2 obserwuje mapę po pierwszym Generuj",
            ],
            [
                "D2",
                "Testy Magazyn+Mapa (Os.2) + Ustawienia/Stan systemu/Raporty (Os.3); "
                "backlog błędów uzupełniony",
            ],
            [
                "D3",
                "Pisanie rozdziałów wg podziału; Os.1 oddaje kanoniczny słownik statusów",
            ],
            [
                "D4",
                "Scalenie dokumentacji: jeden redaktor (najlepiej Os.1) ujednolica język; "
                "wspólny przegląd FAQ i ograniczeń",
            ],
            [
                "D5 (opcjonalnie)",
                "Smoke retest po poprawkach + finalna checklista dnia dla firmy",
            ],
        ],
    )

    _h(doc, "9. Reguły anty-duplikacji")
    _bullets(
        doc,
        [
            "Opis Generuj / Zatwierdź / Odblokuj → tylko Osoba 1",
            "Opis kolejki / bufora / legendy mapy → tylko Osoba 2",
            "Opis importu / floty / backupu → tylko Osoba 3",
            "Słownik statusów → jedna tabela w rozdz. 3, reszta tylko odsyła",
        ],
    )

    path = OUT_DIR / "Crossdock_podzial_obowiazkow.docx"
    doc.save(path)
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    guide = build_guide()
    roles = build_roles()
    print(guide)
    print(roles)


if __name__ == "__main__":
    main()
