# Hosting — 4 równoległe środowiska testowe (Oracle VM + Docker + OSRM)

Cel: cztery osoby testują jednocześnie z własnych komputerów, każda na osobnej
bazie SQLite. Jeden adres VM, różne porty. **Wspólny OSRM** — trasy po drogach na mapie.

Nie mylić z multi-tenantem „login = baza” — tu są **4 osobne kontenery** + **1 OSRM**.

## Adresy

Po starcie (zastąp `PUBLIC_IP`):

| Tester | URL | Dane na dysku VM |
|--------|-----|------------------|
| t1 | `http://PUBLIC_IP:8081` | `data/t1/` |
| t2 | `http://PUBLIC_IP:8082` | `data/t2/` |
| t3 | `http://PUBLIC_IP:8083` | `data/t3/` |
| t4 | `http://PUBLIC_IP:8084` | `data/t4/` |

Login: `admin` + hasło z `deploy/.env.tN` (skrypt `gen-tester-envs.sh` ustawia
domyślnie `tester1` … `tester4` — zmień przed szerszym udostępnieniem).

## Pliki

- [`docker-compose.testers.yml`](../docker-compose.testers.yml) — 4 serwisy aplikacji
- [`docker-compose.osrm.yml`](../docker-compose.osrm.yml) — wspólny OSRM (profil `osrm`)
- [`deploy/bootstrap-testers.sh`](../deploy/bootstrap-testers.sh) — start wszystkiego
- [`deploy/verify-osrm-testers.sh`](../deploy/verify-osrm-testers.sh) — test czy OSRM działa
- [`deploy/patch-tester-env-osrm.sh`](../deploy/patch-tester-env-osrm.sh) — włącza OSRM w istniejących `.env.tN`

Stała komenda Compose (używana w skryptach):

```bash
docker compose -f docker-compose.testers.yml -f docker-compose.osrm.yml --profile osrm
```

---

## Krok po kroku na Oracle VM

### 0. Wymagania

- Ubuntu + Docker + Docker Compose v2
- **Graf OSRM** w `data/osrm/be-nl-de-fr.osrm` (+ pliki towarzyszące)
- Porty **8081–8084** otwarte w Oracle Security List (opcjonalnie **5000** do debugu OSRM)

### 1. Graf OSRM na VM

**Masz już zbudowany graf na PC (Windows)?** Skopiuj cały katalog na VM:

```bash
# Na PC (PowerShell) — przykład scp:
scp -r data/osrm ubuntu@PUBLIC_IP:~/Crossdock/data/
```

Na VM sprawdź:

```bash
ls -la ~/Crossdock/data/osrm/be-nl-de-fr.osrm*
```

**Nie masz grafu?** Zbuduj na VM lub lokalnie — patrz [`docs/osrm_local.md`](osrm_local.md).
Extract wymaga dużo RAM (~16 GB+) i plików PBF w `data/`.

### 2. Kod i env testerów

```bash
cd ~/Crossdock
git pull

bash deploy/gen-tester-envs.sh
# opcjonalnie: nano deploy/.env.t1 … i zmień hasła
```

Jeśli `.env.t1`–`t4` **już istnieją** ze starego setupu (USE_OSRM=false):

```bash
bash deploy/patch-tester-env-osrm.sh
```

### 3. Start (aplikacje + OSRM)

```bash
bash deploy/bootstrap-testers.sh
```

Skrypt:

1. Sprawdza `data/osrm/be-nl-de-fr.osrm`
2. Ustawia `CROSSDOCK_USE_OSRM=true` w każdym `deploy/.env.tN`
3. Uruchamia 4 kontenery + OSRM w **jednej sieci Compose** (`http://osrm:5000`)
4. Czeka aż OSRM odpowie na teście trasy Bruksela→Paryż

### 4. Weryfikacja

```bash
bash deploy/verify-osrm-testers.sh
```

Ręcznie:

```bash
# OSRM na hoście
curl "http://127.0.0.1:5000/route/v1/driving/4.35,50.85;2.35,48.85?overview=false"
# oczekiwane: "code":"Ok"

# Aplikacje
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8081/login
```

### 5. W UI — ważne

1. Zaloguj się na swój port (np. `:8081`).
2. Import Excela → **Generuj** (stare generacje sprzed OSRM mają linie proste).
3. Mapa — trasy powinny iść **po drogach** (gęsta polilinia, nie 3–4 odcinki).

---

## Firewall (Oracle)

```bash
sudo ufw allow 8081:8084/tcp
# opcjonalnie debug OSRM:
sudo ufw allow 5000/tcp
sudo ufw reload
```

W Security List / NSG: ingress TCP **8081–8084** (i ewentualnie 5000).

## Operacje

```bash
COMPOSE="docker compose -f docker-compose.testers.yml -f docker-compose.osrm.yml --profile osrm"

# status
$COMPOSE ps

# logi OSRM
$COMPOSE logs -f osrm

# logi jednego testera
$COMPOSE logs -f crossdock-t2

# restart wszystkich (po zmianie .env)
$COMPOSE up -d --build

# stop
$COMPOSE down
```

Główne demo na `:8080` (`docker-compose.yml`) może działać **równolegle** —
to osobny stack i osobny volume `./data`.

## Rozwiązywanie problemów

| Objaw | Przyczyna | Co zrobić |
|-------|-----------|-----------|
| Linie proste na mapie | Stara generacja lub `USE_OSRM=false` | `patch-tester-env-osrm.sh`, `bootstrap-testers.sh`, kliknij **Generuj** |
| `Brak grafu OSRM` przy starcie | Brak `data/osrm/be-nl-de-fr.osrm` | Skopiuj/zbuduj graf (krok 1) |
| Błąd połączenia z OSRM w logach | OSRM nie wystartował lub osobna sieć | Zawsze używaj **obu** plików compose + `--profile osrm` |
| `service "osrm" depends on undefined` | Sam `docker-compose.testers.yml` bez osrm | Użyj `bootstrap-testers.sh` lub pełnej komendy `$COMPOSE` |
| OSRM OOM na VM | Za mało RAM | Zwiększ RAM VM lub użyj mniejszego wycinka map |

## Miejsce na dysku

- Wspólny obraz Docker + **jeden** graf OSRM (`data/osrm/`, zwykle kilka–kilkanaście GB)
- 4 katalogi `data/tN` (bazy SQLite — zwykle MB–setki MB)

## Co powiedzieć testerom

1. Twój link: `http://IP:808N` (przydzielony port).
2. Login `admin` / hasło od prowadzącego.
3. Import Excela, **Generuj**, mapa — tylko u Ciebie; inni tego nie widzą.
4. Nie używaj portu kolegi — to osobna baza.
5. Po pierwszym włączeniu OSRM: **wygeneruj trasy od nowa**, żeby mapa pokazała drogi.
