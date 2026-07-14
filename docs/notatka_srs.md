# Notatka Wsadowa do Specyfikacji Wymagań (SRS)

## 1. Metryczka

| Parametr | Zawartość |
| :--- | :--- |
| **Projekt** | Optymalizacja cross-dockingu w logistyce transportowej |
| **Firma/klient** | brak danych w źródłach |
| **Data spotkania** | brak danych w źródłach |
| **Uczestnicy** | brak danych w źródłach |
| **Pliki źródłowe** | [notatki_z_spotkania_z_firma.txt](file:///d:/ja/TY100/Zadanie1/spotkanie1/notatki_z_spotkania_z_firma.txt), [wymagania.txt](file:///d:/ja/TY100/Zadanie1/spotkanie1/wymagania.txt) |
| **Data opracowania** | 14.07.2026 |

---

## 2. Cel i kontekst biznesowy

Celem projektu jest rozwiązanie problemu nieefektywnego zarządzania rozproszonymi zleceniami transportowymi od kontrahentów, które cechują się zróżnicowanymi parametrami logistycznymi. Obecny brak optymalizacji procesów logistycznych generuje wysokie koszty operacyjne, prowadzi do niepełnego wykorzystania przestrzeni ładunkowej pojazdów oraz zwiększa emisję dwutlenku węgla. Projekt ma na celu automatyczne grupowanie przesyłek w magazynie przeładunkowym i planowanie optymalnych transportów całopojazdowych. Pozwoli to zminimalizować liczbę transportów i punktów rozładunkowych, a w konsekwencji obniżyć koszty działalności firmy.

---

## 3. Zakres

### 3.1 W zakresie
* Automatyczne pobieranie zleceń transportowych z różnych źródeł (w tym z systemu TMS klienta).
* Modelowanie parametrów logistycznych zleceń (kody dostaw, waga i liczba palet, miejsca odbioru/dostawy, terminy realizacji).
* Automatyczne grupowanie przesyłek (cross-docking) w magazynie przeładunkowym.
* Automatyczne planowanie i optymalizacja transportów całopojazdowych (FTL) dla floty składającej się z busów, ciężarówek i pojazdów z plandekami, w celu maksymalizacji wykorzystania ich przestrzeni ładunkowej.
* Optymalizacja tras przewozowych (minimalizacja punktów rozładunku, grupowanie kierunkowe, redukcja dystansu i kosztów).
* Możliwość kolejkowania zleceń i przetrzymywania towarów w magazynie przeładunkowym przez kilka dni w celu optymalizacji kosztów transportu.
* Prezentacja wyników planowania (wizualizacja tras na mapie oraz raporty efektywności w zakresie oszczędności i wykorzystania pojazdów).
* Integracja z systemami TMS (własnym oraz klienta).
* Obsługa powiązania w strukturze danych uniemożliwiającego rozdzielanie paczek (gdy pod jedno zlecenie podpięte są 2 numery przesyłek).
* Obsługa rotacji paczek w magazynie własnym firmy.
* Aktualizacja liczby palet w zlecenie po jego zaakceptowaniu, przed momentem odbioru z magazynu klienta.

### 3.2 Poza zakresem
* Uwzględnianie czasu pracy kierowców (w tym monitorowanie tachometrów oraz planowanie wymaganych przerw).

---

## 4. Aktorzy / interesariusze

| Aktor | Rola | Co robi w systemie |
| :--- | :--- | :--- |
| **Dyspozytor** | Główny użytkownik systemu | Zarządza procesem planowania, konfiguruje integracje z systemami TMS, zatwierdza zoptymalizowane plany transportowe FTL, przegląda wizualizacje tras na mapie oraz analizuje raporty efektywności operacyjnej. |
| **Kontrahent / Klient** | Interesariusz zewnętrzny (system zewnętrzny) | Dostarcza zlecenia transportowe (poprzez powiązany system TMS lub pliki) oraz generuje aktualizacje danych o zapotrzebowaniu (np. zmiany w liczbie palet) przed fizycznym odbiorem towaru. |

---

## 5. Słownik pojęć

| Termin | Definicja | Źródło |
| :--- | :--- | :--- |
| **Cross-docking** | Proces przeładunku towarów w magazynie przeładunkowym bez ich długotrwałego przechowywania i magazynowania. | WYMAGANIA |
| **FTL (Full Truck Load)** | Transport całopojazdowy, polegający na optymalnym zapełnieniu całej dostępnej przestrzeni ładunkowej pojazdu przesyłkami. | SPOTKANIE / WYMAGANIA |
| **TMS (Transportation Management System)** | System zarządzania transportem wykorzystywany do planowania, realizacji i optymalizacji fizycznego przemieszczania towarów. | SPOTKANIE / WYMAGANIA |
| **Plandeka** | Rodzaj naczepy lub nadwozia samochodu ciężarowego ze zdejmowanym elastycznym pokryciem, wchodzący w skład floty firmy. | SPOTKANIE |
| **Busy i ciężarówki** | Środki transportu wchodzące w skład floty pojazdów firmy, dla których system optymalizuje ładunki FTL. | SPOTKANIE |
| **Shipment (Przesyłka)** | Pojedyncza paczka/jednostka ładunkowa przypisana do zlecenia. W strukturze danych jedno zlecenie może posiadać maksymalnie dwa powiązane numery shipment, które nie podlegają rozdzieleniu. | SPOTKANIE |
| **Zlecenie transportowe** | Zbiór danych definiujący parametry przewozu (kody dostaw, waga, liczba palet, miejsca załadunku/rozładunku, termin). | SPOTKANIE / WYMAGANIA |
| **Magazyn własny** | Magazyn przeładunkowy firmy zlokalizowany w odległości około 30 km od Antwerpii w Belgii, w którym realizowany jest proces rotacji paczek i grupowania. | SPOTKANIE / WYMAGANIA |
| **Przesyłka drobnica** | Przesyłka o mniejszej objętości lub wadze, która jest konsolidowana z innymi przesyłkami w celu utworzenia pełnego ładunku FTL. | SPOTKANIE |

---

## 6. Wymagania funkcjonalne

| ID | Wymaganie | Priorytet | Źródło | Kryterium akceptacji | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-001** | System MUSI automatycznie pobierać dane zleceń transportowych z zewnętrznego systemu TMS klienta. | MUST | OBA | Poprawne pobranie i zaimportowanie zlecenia do bazy danych systemu z zewnętrznego systemu TMS klienta. | POTWIERDZONE |
| **FR-002** | System MUSI automatycznie pobierać dane zleceń transportowych z innych zewnętrznych źródeł danych. | w przyszłości, obecnie musi korzystać z pliku Excel, który w wersji roboczej będzie po prostu dawany do przetworzenia | WYMAGANIA | Poprawne wczytanie zleceń transportowych z plików w zdefiniowanych formatach zewnętrznych. | POTWIERDZONE |
| **FR-003** | System MUSI modelować dane logistyczne zleceń poprzez zapisanie kodów dostaw. | MUST | WYMAGANIA | Prawidłowe zapisanie i wyświetlenie kodu dostawy dla każdego zlecenia w bazie danych. | POTWIERDZONE |
| **FR-004** | System MUSI modelować dane logistyczne zleceń poprzez zapisanie liczby palet. | MUST | WYMAGANIA | Prawidłowe zapisanie i wyświetlenie liczby palet w zleceniu. | POTWIERDZONE |
| **FR-005** | System MUSI modelować dane logistyczne zleceń poprzez zapisanie wagi palet. | Nie musi | WYMAGANIA | Prawidłowe zapisanie i wyświetlenie wagi palet w zleceniu. | POTWIERDZONE |
| **FR-006** | System MUSI modelować dane logistyczne zleceń poprzez zapisanie miejsca odbioru oraz miejsca dostawy. | MUST | WYMAGANIA | Prawidłowe zapisanie i wyświetlenie adresu/współrzędnych załadunku i rozładunku. | POTWIERDZONE |
| **FR-007** | System MUSI modelować dane logistyczne zleceń poprzez zapisanie terminu realizacji. | MUST | WYMAGANIA | Prawidłowe zapisanie i wyświetlenie wymaganej daty dostawy zlecenia. | POTWIERDZONE |
| **FR-008** | System MUSI automatycznie grupować przesyłki w magazynie przeładunkowym w celu realizacji procesu cross-dockingu. | MUSI | WYMAGANIA | Wygenerowanie przez system optymalnych grup przesyłek przeznaczonych do wspólnego przeładunku w magazynie. | POTWIERDZONE |
| **FR-009** | System MUSI automatycznie planować transporty całopojazdowe (FTL) z uwzględnieniem ograniczeń logistycznych. | MUSI | WYMAGANIA | Wygenerowanie planu załadunku pojazdów FTL zgodnie z regułami logistycznymi. | POTWIERDZONE |
| **FR-010** | System MUSI automatycznie planować transporty całopojazdowe (FTL) z uwzględnieniem ograniczeń geograficznych. | MUSI | WYMAGANIA | Wygenerowanie planu załadunku pojazdów FTL zgodnie z kierunkami i odległościami geograficznymi. | POTWIERDZONE |
| **FR-011** | System MUSI maksymalizować wykorzystanie przestrzeni ładunkowej pojazdów podczas tworzenia transportów FTL. | MUSI | WYMAGANIA | Wskaźnik zapełnienia zaplanowanych pojazdów FTL osiąga zoptymalizowaną wartość procentową. | POTWIERDZONE |
| **FR-012** | System POWINIEN minimalizować liczbę punktów rozładunkowych na zaplanowanych trasach. | MUSI | WYMAGANIA | Zaplanowana trasa FTL zawiera najmniejszą możliwą liczbę fizycznych miejsc rozładunku. | POTWIERDZONE |
| **FR-013** | System POWINIEN grupować dostawy według kierunku geograficznego. | MUSI | WYMAGANIA | Towary na jednej trasie są przypisane do punktów leżących w zbliżonym kierunku geograficznym. | POTWIERDZONE |
| **FR-014** | System POWINIEN minimalizować całkowity dystans tras transportowych. | POWINIEN | WYMAGANIA | Porównanie długości tras wyjściowych z trasami zoptymalizowanymi wykazuje spadek całkowitej liczby kilometrów. | POTWIERDZONE |
| **FR-015** | System POWINIEN minimalizować koszty transportu. | POWINIEN | WYMAGANIA | Porównanie kosztów wyjściowych z kosztami tras zoptymalizowanych wykazuje oszczędności finansowe. | POTWIERDZONE |
| **FR-016** | System POWINIEN prezentować wizualizację tras transportowych na mapie. | POWINIEN | WYMAGANIA | Wyświetlenie graficznej trasy przejazdu pojazdu na mapie w panelu dyspozytora. | POTWIERDZONE |
| **FR-017** | System POWINIEN generować raporty efektywności w zakresie uzyskanych oszczędności kosztowych. | POWINIEN | WYMAGANIA | Wyeksportowanie raportu zawierającego finansowe podsumowanie oszczędności wygenerowanych przez system. | POTWIERDZONE |
| **FR-018** | System POWINIEN generować raporty efektywności w zakresie stopnia wykorzystania pojazdów. | POWINIEN | WYMAGANIA | Wyeksportowanie raportu pokazującego stopień wykorzystania ładowności/objętości pojazdów. | POTWIERDZONE |
| **FR-019** | System MUSI uniemożliwić rozdzielenie paczek na różne transporty lub etapy magazynowania, jeśli pod jedno zlecenie podpięte są dwa numery przesyłek (shipment). | MUST | SPOTKANIE | Walidacja systemowa blokuje próby przypisania takich paczek do różnych pojazdów lub różnych harmonogramów wydań. | POTWIERDZONE |
| **FR-020** | System POWINIEN umożliwiać rotowanie paczkami w magazynie własnym. | COULD | SPOTKANIE | Użytkownik może w systemie zmienić priorytet lub status paczki oczekującej w magazynie w celu jej przestawienia w kolejce. | POTWIERDZONE |
| **FR-021** | System POWINIEN umożliwiać modyfikację liczby palet w zleceniu po jego zaakceptowaniu, a przed odbiorem z magazynu klienta. | SHOULD | SPOTKANIE | Możliwość edycji i zapisu nowej liczby palet dla zlecenia o statusie "zaakceptowane", pod warunkiem, że transport nie został odebrany. | POTWIERDZONE |
| **FR-022** | System POWINIEN tworzyć kolejkę zleceń w celu czasowego pozostawienia towaru w magazynie, gdy jest to bardziej opłacalne kosztowo. | SHOULD | SPOTKANIE | System identyfikuje zlecenia, które opłaca się opóźnić, i przetrzymuje je w buforze magazynowym na wskazany czas. | POTWIERDZONE |
| **FR-023** | System POWINIEN automatycznie udostępniać gotowe dane i plany transportowe na 4-5 dni przed planowaną wysyłką. | SHOULD | SPOTKANIE | Plany transportowe generowane są automatycznie i uzyskują status gotowości z wyprzedzeniem min. 4 dni przed wysyłką. | POTWIERDZONE |
| **FR-024** | System POWINIEN przyjmować domyślny 7-dniowy kalendarzowy termin dostawy dla nowo dodawanych zleceń. | MUST | SPOTKANIE | Nowo utworzone zlecenie bez określonej daty dostawy automatycznie otrzymuje termin realizacji równy data_bieżąca + 7 dni kalendarzowych. | WYWNIOSKOWANE |

---

## 7. Wymagania niefunkcjonalne

| ID | Kategoria | Wymaganie | Miara / próg | Priorytet | Źródło | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NFR-001** | wydajność | System musi automatycznie uruchamiać proces ładowania/importu danych dwa razy dziennie w zdefiniowanych przedziałach czasowych. | Dokładnie w przedziałach: 5:30 - 6:00 oraz 11:30 - 12:00 każdego dnia. | MUST, ale w formie roboczej ma być to wywołane z poziomu systemu | SPOTKANIE | POTWIERDZONE |
| **NFR-002** | kompatybilność | System musi integrować się bezpośrednio z systemem TMS klienta. | docelowo tak, obecnie plikiem wsadowym bedzie po prostu odpowiedni plik excel | must | SPOTKANIE | POTWIERDZONE |
| **NFR-003** | kompatybilność | System musi obsługiwać integrację na poziomie API, plików oraz systemów TMS. | tak, czekamy na dane do API, obecnie musimy zadowolic sie plikiem EXCEL | MUST | WYMAGANIA | POTWIERDZONE |
| **NFR-004** | użyteczność | Interfejs użytkownika musi być dostosowany do pracy dyspozytorów transportu. | [do doprecyzowania] (brak wymagań UX/UI w źródłach) | COULD | SPOTKANIE | POTWIERDZONE |
| **NFR-005** | wydajność | System musi optymalizować przepływ towarów, zapewniając ich szybkość i efektywność. | [do doprecyzowania] (nieostre sformułowania w źródłach) | SHOULD | WYMAGANIA | POTWIERDZONE |
| **NFR-006** | wydajność | System musi minimalizować emisję CO₂ w procesach transportowych. | [do doprecyzowania] (brak wartości progowych redukcji w źródłach) | SHOULD | WYMAGANIA | POTWIERDZONE |

---

## 8. Ograniczenia i założenia

### 8.1 Ograniczenia narzucone przez firmę
* **Infrastruktura transportowa (flota):** Flota własna firmy składa się wyłącznie z busy, ciężarówki oraz pojazdów z plandekami.
* **Lokalizacja:** Magazyn przeładunkowy zlokalizowany jest w odległości około 30 km od Antwerpii w Belgii.
* **Integracja:** System musi łączyć system TMS firmy z systemem TMS klienta oraz umożliwiać pobieranie danych z różnych źródeł (API, pliki).
* **Harmonogram zasilania danymi:** Wymagane docelowo sztywne okna czasowe na import danych: 5:30 - 6:00 oraz 11:30 - 12:00, ale na początek będzie to import manualny przez system excel.
* **Czas przygotowania planu:** Plany transportowe i dane muszą być gotowe do użycia 4-5 dni przed planowaną wysyłką.
* **Nierozdzielność przesyłek:** Całkowity zakaz rozdzielania przesyłek w przypadku, gdy pod jedno zlecenie podpięte są 2 lub wiecej numery shipment.
* **Kompetencje techniczne:** Sugerowane wykorzystanie technologii Python jako preferowanych języków programowania.

### 8.2 Założenia przyjęte przy opracowaniu notatki
* Przyjęto, że magazyn własny zlokalizowany pod Antwerpią pełni rolę magazynu przeładunkowego (cross-dockingowego) opisywanego w wymaganiach.
* Założono, że "zlecenia transportowe od jednego kontrahenta" są tożsame ze zleceniami importowanymi z systemu TMS klienta.
* Założono, że system nie wymaga modułu do planowania czasu pracy kierowców, ponieważ kwestie tachografów i przerw zostały jednoznacznie wykluczone z zakresu projektu.
* Założono, że standardowy czas realizacji dostawy towaru wynosi maksymalnie 7 dni kalendarzowych, chyba że parametry zlecenia określają to inaczej.

---

## 9. Rozbieżności, luki i pytania do klienta

### 9.1 SPRZECZNOŚCI
* W plikach źródłowych nie zidentyfikowano bezpośrednich sprzeczności. Treści zawarte w pliku ze spotkania uzupełniają o szczegóły techniczno-operacyjne cele ogólne sformułowane w wymaganiach.

### 9.2 SFORMUŁOWANIA NIEOSTRE
* **"szybkiego i efektywnego przepływu towarów przy jednoczesnej minimalizacji kosztów"** (WYMAGANIA, linia 4)
  * *Propozycja mierzalnej formy:* Zdefiniowanie maksymalnego czasu przejścia przesyłki przez magazyn (np. do 24h) oraz docelowego poziomu redukcji kosztów transportu (np. o 12% w skali miesiąca).
* **"niepełnego wykorzystania przestrzeni ładunkowej" / "maksymalizacja wykorzystania przestrzeni ładunkowej"** (WYMAGANIA, linia 10 i 34)
  * *Propozycja mierzalnej formy:* Ustalenie minimalnego progu zapełnienia przestrzeni ładunkowej dla każdego planowanego transportu FTL na poziomie min. 90% (objętościowo lub wagowo).
* **"zmniejszonej liczby transportów" / "minimalizacja liczby punktów rozładunkowych"** (WYMAGANIA, linia 10 i 36)
  * *Propozycja mierzalnej formy:* Ograniczenie liczby punktów rozładunku (drop-off) dla pojedynczej trasy FTL do maksymalnie 3 punktów.
* **"dużo bardziej opłaca się pozostać w magazynie jakiś towar i wysłać go po kilku dniach"** (SPOTKANIE, linia 11)
  * *Propozycja mierzalnej formy:* Wprowadzenie algorytmu decyzyjnego porównującego koszt magazynowania danej liczby palet przez X dni z kosztem wysyłki ładunku niepełnego (LTL) zamiast całopojazdowego (FTL). Opóźnienie wysyłki następuje, gdy koszt magazynowania + późniejszy FTL jest niższy o min. 15% od natychmiastowej wysyłki LTL.
* **"zazwyczaj 7 dni Kalendarzowych na dostarczenie"** (SPOTKANIE, linia 10)
  * *Propozycja mierzalnej formy:* Zapisanie w systemie twardego ograniczenia (SLA) dla dostawy: maksymalnie 7 dni kalendarzowych (168 godzin) od momentu zatwierdzenia zlecenia.
* **"czasem już po zaakceptowaniu zdarzają się zmiany w ilości palet"** (SPOTKANIE, linia 8)
  * *Propozycja mierzalnej formy:* Określenie granicznego czasu na wprowadzenie modyfikacji, np. do 12 godzin przed planowanym rozpoczęciem załadunku pojazdu u klienta.

### 9.3 LUKI
* Jakie konkretnie systemy TMS są używane przez klienta i firmę (np. SAP TMS, Oracle OTM, autorskie rozwiązanie) i jakimi interfejsami API dysponują?
* Jak system ma reagować w sytuacji, gdy zmiana liczby palet zgłoszona po akceptacji zlecenia spowoduje, że ładunek przestanie mieścić się w przypisanym pojeździe FTL?

