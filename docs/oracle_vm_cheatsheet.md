# Crossdock — ściągawka Oracle VM (SSH + Docker)

Tymczasowe demo na Oracle Cloud Always Free.
Publiczny adres (aktualny): `http://158.180.59.192:8080`

---

## 1. Połączenie z VM (Windows / PowerShell)

### Klucz SSH
Zalecana lokalizacja klucza:

```text
C:\Users\sewer\.ssh\oracle-crossdock.key
```

Jeśli klucz był w `data\` i miał złe uprawnienia, użyj wersji z `.ssh`.

### Logowanie

```powershell
ssh -i "$HOME\.ssh\oracle-crossdock.key" ubuntu@158.180.59.192
```

Przy pierwszym połączeniu wpisz `yes`.

Po udanym logowaniu prompt wygląda tak:

```bash
ubuntu@primary-vnic:~$
```

Wylogowanie:

```bash
exit
```

### Jeśli klucz ma złe uprawnienia (Windows)

```powershell
$user = whoami
takeown /f "ścieżka\do\klucza.key"
icacls "ścieżka\do\klucza.key" /inheritance:r
icacls "ścieżka\do\klucza.key" /remove "Authenticated Users"
icacls "ścieżka\do\klucza.key" /remove "Users"
icacls "ścieżka\do\klucza.key" /grant:r "${user}:(R)"
```

---

## 2. Ważne: zawsze wchodź do katalogu projektu

`docker compose` działa tylko w katalogu, w którym jest `docker-compose.yml`.

```bash
cd ~/Crossdock
```

Bez tego dostaniesz:

```text
no configuration file provided: not found
```

---

## 3. Docker — status, logi, restart

### Status kontenerów

```bash
cd ~/Crossdock
docker compose ps
```

### Logi (ostatnie linie)

```bash
docker compose logs --tail=80
```

### Logi na żywo

```bash
docker compose logs -f
```

Wyjdź z logów: `Ctrl+C` (aplikacja dalej działa).

### Restart aplikacji

```bash
docker compose restart
```

### Zatrzymanie

```bash
docker compose down
```

### Start / rebuild

```bash
docker compose up -d --build
```

---

## 4. Pierwsze uruchomienie (jeśli robisz od zera)

### Docker (jednorazowo)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
exit
```

Zaloguj się ponownie przez SSH, potem:

```bash
docker --version
docker compose version
```

### Kod

```bash
cd ~
git clone https://github.com/Seweryn-L/Crossdock.git
cd Crossdock
git checkout seweryn-l-stunning-guide
```

### Konfiguracja `.env`

```bash
cp deploy/.env.demo.example .env
nano .env
```

Uzupełnij:

- `CROSSDOCK_STORAGE_SECRET=` — losowy sekret
- `CROSSDOCK_ADMIN_PASSWORD=` — hasło do logowania `admin`

Zapis w nano: `Ctrl+O`, Enter. Wyjście: `Ctrl+X`.

### Start

```bash
mkdir -p data
bash deploy/oracle-bootstrap.sh
```

albo:

```bash
docker compose up -d --build
```

---

## 5. Test, czy aplikacja działa na serwerze

```bash
cd ~/Crossdock
curl http://localhost:8080/login
```

Jeśli dostajesz HTML — app działa lokalnie na VM.

Uwaga: `curl -I` może zwrócić `405 Method Not Allowed` — to OK (HEAD nie jest wspierane; GET działa).

---

## 6. Wejście z przeglądarki (Twój komputer / zespół)

```text
http://158.180.59.192:8080
```

- Login: `admin`
- Hasło: wartość `CROSSDOCK_ADMIN_PASSWORD` z `.env` na VM

---

## 7. Firewall Oracle (port 8080)

Jeśli strona nie otwiera się z internetu, a `curl localhost` działa:

1. **Networking** → **Virtual cloud networks** → Twoja VCN
2. **Security Lists** → domyślna lista subnetu
3. **Add Ingress Rule**:

| Pole | Wartość |
|------|---------|
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| **Source Port Range** | **PUSTE** |
| Destination Port Range | `8080` |

Źródłowy port musi zostać pusty. Destination = `8080`.

---

## 8. Aktualizacja kodu na VM

```bash
cd ~/Crossdock
git pull
docker compose up -d --build
docker compose logs -f
```

---

## 9. Typowe problemy

| Objaw | Co zrobić |
|-------|-----------|
| `no configuration file provided` | `cd ~/Crossdock` |
| `Permission denied (publickey)` | zły klucz / złe uprawnienia pliku `.key` |
| Strona nie otwiera się z internetu | otwórz port 8080 w Security List (Source Port pusty) |
| Kontener Restarting | `docker compose logs --tail=80` |
| Po restarcie VM app nie działa | `cd ~/Crossdock && docker compose up -d` |

---

## 10. Czy kontener musi działać na Twoim PC?

**Nie.** Aplikacja działa na Oracle VM. Twój komputer może być wyłączony — wystarczy, że VM i kontener na serwerze są uruchomione.

Sprawdzenie na VM:

```bash
cd ~/Crossdock
docker compose ps
```

Status `Up` = demo działa.
