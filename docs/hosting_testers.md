# Hosting — 4 równoległe środowiska testowe (Oracle VM + Docker)

Cel: cztery osoby testują jednocześnie z własnych komputerów, każda na osobnej
bazie SQLite. Jeden adres VM, różne porty.

Nie mylić z multi-tenantem „login = baza” — tu są **4 osobne kontenery**.

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

## Co powstało

- [`docker-compose.testers.yml`](../docker-compose.testers.yml) — 4 serwisy
- [`deploy/.env.tester.example`](../deploy/.env.tester.example) — szablon
- [`deploy/gen-tester-envs.sh`](../deploy/gen-tester-envs.sh) — generuje `.env.t1`–`.env.t4`
- [`deploy/bootstrap-testers.sh`](../deploy/bootstrap-testers.sh) — `up --build`

## Firewall (Oracle)

W Security List / Network Security Group otwórz **TCP 8081–8084** (ingress z internetu
lub tylko z IP zespołu). Port `8080` (główne demo) może zostać osobno.

Na VM (jeśli ufw):

```bash
sudo ufw allow 8081:8084/tcp
sudo ufw reload
```

## Pierwszy start na VM

```bash
cd ~/Crossdock   # lub katalog klonu
git pull

bash deploy/gen-tester-envs.sh
# opcjonalnie: nano deploy/.env.t1 … i zmień hasła

bash deploy/bootstrap-testers.sh
```

Sprawdzenie:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8081/login
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8082/login
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8083/login
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8084/login
```

Oczekiwane: `200` (lub inny kod HTML OK — ważne, że nie connection refused).

## Operacje

```bash
# status
docker compose -f docker-compose.testers.yml ps

# logi jednej osoby
docker compose -f docker-compose.testers.yml logs -f crossdock-t2

# restart wszystkich
docker compose -f docker-compose.testers.yml restart

# stop
docker compose -f docker-compose.testers.yml down
```

Główne demo na `:8080` (`docker-compose.yml`) może działać **równolegle** —
to osobny stack i osobny volume `./data`.

## Miejsce na dysku

Wspólny obraz Docker + 4 katalogi `data/tN` (baza, logi, backupy).
Przy danych demo zwykle **dziesiątki–setki MB łącznie**, nie gigabajty.

## OSRM (opcjonalnie)

Jeśli na VM stoi OSRM z `docker-compose.osrm.yml`, w każdym `deploy/.env.tN`:

```text
CROSSDOCK_USE_OSRM=true
CROSSDOCK_OSRM_URL=http://osrm:5000
```

i podepnij sieć Compose (albo wystaw OSRM na `host` / wspólnej network).
Na start testów funkcjonalnych **wystarczy haversine** (`USE_OSRM=false`).

## Co powiedzieć testerom

1. Twój link: `http://IP:808N` (przydzielony port).
2. Login `admin` / hasło od prowadzącego.
3. Import Excela, Generuj, mapa — tylko u Ciebie; inni tego nie widzą.
4. Nie używaj portu kolegi — to osobna baza.
