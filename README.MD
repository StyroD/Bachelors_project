# Pharmacogenomics Variant Browser

A clinical decision support tool for exploring pharmacogenomic variant annotations. The browser allows clinicians and researchers to search genetic variants by rsID, chromosomal position, or by uploading a patient VCF file, and instantly retrieve curated drug-gene interaction data from PharmGKB/ClinPGx — including drug annotations, functional effects, haplotype (star allele) classifications via PharmVar, and links to supporting literature on PubMed.

Understanding how a patient's genetic variants affect drug metabolism can directly influence prescribing decisions. This tool makes that data accessible without requiring database expertise.

---

## Requirements

- [Docker](https://www.docker.com/products/docker-desktop/) installed and running
- Git

---

## First time setup

Clone the repository and run the setup script — it handles everything automatically:

```bash
git clone <repository-url>
cd <repository-folder>
bash setup.sh
```

The script will start the database container, wait until it is healthy, restore the full pharmacogenomic dataset, register the automatic update cron job, and launch the application.

Open **http://localhost:8000** in your browser.

---

## Day-to-day startup

After the initial setup, use `start.sh` to bring everything up:

```bash
bash start.sh
```

This restores the latest database snapshot and starts the application.

---

## What the app does

**Variant Search** — Search by rsID (e.g. `rs12248560`), exact chromosomal coordinates, or free text. Results show drug annotations, functional effects, gene information, and PubMed links for every matched variant.

**Haplotype Annotations** — When a searched variant is a defining SNP of a known star allele (e.g. `CYP2C19*17`), the browser automatically surfaces haplotype-level drug annotations via PharmVar mappings. This means a simple rsID search can reveal clinically relevant pharmacogene classifications that would otherwise be invisible.

**VCF Upload** — Upload a patient or sample VCF file (plain or gzipped). The browser scans every variant in the file against the annotation database and returns a list of all variants with known pharmacogenomic significance.

**Export** — Every variant detail page can be exported as a PDF report or a standalone HTML file, suitable for clinical records or sharing with colleagues.

---

## Project structure

```
./
├── Dockerfile               -- builds the Python/Shiny application image
├── docker-compose.yml       -- wires the app and PostgreSQL together
├── setup.sh                 -- first-time setup: restores DB, registers cron, starts app
├── start.sh                 -- day-to-day startup: restores DB and starts app
├── .env                     -- database credentials
├── .dockerignore
├── backup.sql               -- full database dump, restored on every startup
├── requirements.txt
├── loaders/
│   └── updating_dates.py    -- automatic PharmGKB/dbSNP update script
└── app/
    ├── app.py               -- application entry point
    ├── db.py                -- all database queries
    ├── ui.py                -- user interface layout and styles
    ├── server.py            -- reactive server logic
    └── services/
        ├── vcf_service.py   -- VCF query parsing and formatting
        ├── vcf_parser.py    -- VCF file parsing (plain and gzipped)
        ├── html_export.py   -- HTML report generation
        └── pdf_export.py    -- PDF report generation
```

---

## Day-to-day commands

| What                          | Command                                                           |
|-------------------------------|-------------------------------------------------------------------|
| Start everything              | `docker compose up`                                               |
| Start in background           | `docker compose up -d`                                            |
| Stop                          | `docker compose down`                                             |
| Rebuild after code changes    | `docker compose up --build`                                       |
| View app logs                 | `docker compose logs app`                                         |
| View database logs            | `docker compose logs db`                                          |
| Open database shell           | `docker compose exec db psql -U postgres -d pharmacogenomic_data` |
| Wipe database and start fresh | `docker compose down -v`                                          |
| View update logs              | `cat logs/update.log`                                             |

---

## Automatic database updates

The database updates automatically every two months via a cron job registered during setup. It checks the CPIC changelog for new entries, downloads fresh data from PharmGKB, reloads all affected tables, re-fetches dbSNP variant coordinates, and writes a fresh `backup.sql`. The next startup will pick up the new snapshot automatically.

To run the update manually:

```bash
python3 loaders/updating_dates.py
```

---

## Updating the database manually

After making manual changes to the database, dump and commit:

```bash
docker compose exec -T db pg_dump -U postgres pharmacogenomic_data > backup.sql
```

Anyone pulling the updated repo just runs:

```bash
bash start.sh
```

---

## Changing the database password

Edit `.env`:

```
DB_PASSWORD=your_new_password
```

Then restart:

```bash
docker compose down && docker compose up --build
```

---

## Data sources

- **PharmGKB / ClinPGx** — curated variant-drug and variant-phenotype annotations
- **PharmVar** — haplotype (star allele) definitions mapping rsIDs to named alleles
- **PubMed** — all annotation links point to the original supporting publications