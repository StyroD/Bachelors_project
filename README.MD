=== Nastavenie virtuálneho prostredia ===
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

=== Nastavenie databázy ===
Je potrebné mať nainštalovanú postgreSQL databázu
V repozitári je uložený dump databázy s názvom pharmacogenic.sql 
Na restornutie databázy stačí zadať tieto príkazy do databázy
createdb pharmacogenomic_data && psql pharmacogenomic_data < pharmacogenomic_data.sql

Na konfiguráciu databázy s aplikáciou je potrebné zmeniť prikaz psycopg2.connect() vo funkciách get_connection() a ensure_db_running()
typu:
 psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres", 
        password="heslo123",
        database="pharmacogenomic_data"
    )
na základe údajov vašich z databázy.

=== Upravenie spracovávania ===
Kód bol upravený na batch systém a limity sa nastavujú v server.py (line 481) 
momentálne nastavenie:
            MAX_ANNOTATED = -1
            MAX_TOTAL = -1
nemá žiadne limitácie. 
line 486:
 for batch_variants, batch_errors in parse_vcf_file_stream(tmp_path, batch_size=50000):
tu sa nastavuje batch_size na základe veľkosti RAMKY- t.j. pri väčší RAMkách je kľude možné nastaviť väčší batch.

=== Spustenie aplikácie ===
Aplikácia sa zapína príkazom:
shiny run app/app.py

# Pharmacogenomics Variant Browser — Docker Setup
 
## Your project structure should look like this
 
```
~/bc/
├── Dockerfile
├── docker-compose.yml
├── .env
├── .dockerignore
├── requirements.txt
└── app/
    ├── app.py
    ├── db.py              ← replace with the updated version
    ├── ui.py
    ├── server.py
    └── services/
        ├── vcf_service.py
        ├── vcf_parser.py
        ├── html_export.py
        └── pdf_export.py
```
 
## First time setup
 
### 1. Copy these Docker files into ~/bc/ (project root)
Place `Dockerfile`, `docker-compose.yml`, `.env`, `.dockerignore` in `~/bc/`, not inside `app/`.
 
### 2. Replace app/db.py
Use the updated `db.py` provided — it reads DB credentials from environment
variables instead of hardcoding them. Your local password is preserved as the default.
 
### 3. Start everything
```bash
docker compose up --build
```
 
Open **http://localhost:8000** — your app is running.
 
---
 
## What about my existing database data?
 
The Docker Postgres starts **empty**. You need to restore your existing data.
 
### Option A — pg_dump from your local Postgres (recommended)
 
On your machine (before running Docker), dump your database:
```bash
pg_dump -U postgres pharmacogenomic_data > backup.sql
```
 
Then restore into the Docker container:
```bash
# Make sure the container is running first
docker compose up -d db
 
# Restore
docker compose exec -T db psql -U postgres -d pharmacogenomic_data < backup.sql
```
 
### Option B — Mount your existing Postgres data directory
Only works if you know where your local Postgres stores data (risky, not recommended).
 
---
 
## Day-to-day commands
 
| What                        | Command                          |
|-----------------------------|----------------------------------|
| Start everything            | `docker compose up`              |
| Start in background         | `docker compose up -d`           |
| Stop                        | `docker compose down`            |
| Rebuild after code changes  | `docker compose up --build`      |
| View app logs               | `docker compose logs app`        |
| Connect to DB with psql     | `docker compose exec db psql -U postgres -d pharmacogenomic_data` |
| Delete all data (fresh start)| `docker compose down -v`        |
 
## Changing the password
Edit `.env`:
```
DB_PASSWORD=your_new_password
```
Then restart: `docker compose down && docker compose up --build`
 
