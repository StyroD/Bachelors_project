#!/usr/bin/env python3
"""
Checks CPIC changelog for new entries since last sync.
If relevant changes are found, downloads fresh PharmGKB zip files
and reloads the affected PostgreSQL tables, then re-downloads dbSNP data,
and refreshes PharmVar haplotype mappings.
All downloaded files are cleaned up after a successful run.
"""

import csv
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from io import StringIO
from typing import Dict, List, Optional, Tuple

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import RealDictCursor, execute_values
import sys


# Config

csv.field_size_limit(sys.maxsize)
CHANGES_TSV_URL = "https://raw.githubusercontent.com/cpicpgx/cpic-data/main/data.tsv"
DBSNP_API_URL = "https://clinicaltables.nlm.nih.gov/api/snps/v3/search"
PHARMVAR_URL = "https://www.pharmvar.org/get-download-file?name=ALL&refSeq=ALL&fileType=zip&version=current"
GENOME_BUILD = "GRCh38"

PHARMGKB_DOWNLOADS = {
    "variants":    "https://api.pharmgkb.org/v1/download/file/data/variants.zip",
    "chemicals":   "https://api.pharmgkb.org/v1/download/file/data/chemicals.zip",
    "annotations": "https://api.pharmgkb.org/v1/download/file/data/variantAnnotations.zip",
}

DB_CONFIG = {
    "dbname": "pharmacogenomic_data",
    "user": "postgres",
    "password": "789#",
    "host": "localhost",
    "port": 5433,
}

RELEVANT_TYPES = {
    "ALLELE_DEFINITION",
    "ALLELE_FUNCTION_REFERENCE",
    "GENE_CDS",
    "RECOMMENDATION",
    "PAIR",
}

TARGET_GENES = {
    'CYP1A2', 'CYP2A6', 'CYP2B6', 'CYP2C19', 'CYP2C8',
    'CYP2C9', 'CYP2D6', 'CYP3A4', 'CYP3A5', 'CYP4F2',
    'DPYD', 'NAT2', 'NUDT15', 'SLCO1B1'
}

# Tracks all temp files/dirs to clean up at the end
_temp_paths = []


def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError:
        raise RuntimeError("Cannot connect to database. Make sure Docker is running: docker compose up -d db")


def get_last_synced_date():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT value FROM sync_state WHERE key = 'last_synced';")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return date(1970, 1, 1)
    return datetime.strptime(row["value"], "%Y-%m-%d").date()


def update_last_synced_date(new_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sync_state (key, value)
        VALUES ('last_synced', %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """,
        (new_date.strftime("%Y-%m-%d"),),
    )
    conn.commit()
    cur.close()
    conn.close()


# Changelog helpers

def download_changes_tsv():
    try:
        response = requests.get(CHANGES_TSV_URL, timeout=30)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Timed out while fetching changelog from {CHANGES_TSV_URL}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Could not connect to changelog URL: {CHANGES_TSV_URL}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching changelog ({e.response.status_code}): {CHANGES_TSV_URL}")

    # Save to temp file for cleanup later
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.tsv', mode='w', encoding='utf-8')
    tmp.write(response.text)
    tmp.close()
    _temp_paths.append(tmp.name)

    try:
        df = pd.read_csv(StringIO(response.text), sep="\t")
    except Exception as e:
        raise RuntimeError(f"Failed to parse changelog TSV: {e}")

    required_columns = {"Date of Change", "Type of Data", "Subject"}
    missing = required_columns - set(df.columns)
    if missing:
        raise RuntimeError(f"Changelog TSV is missing expected columns: {missing}")

    return df


def get_relevant_changes(df, last_synced):
    df["Date of Change"] = pd.to_datetime(df["Date of Change"], errors="coerce")
    new_rows = df[df["Date of Change"] > pd.Timestamp(last_synced)]
    return new_rows[new_rows["Type of Data"].isin(RELEVANT_TYPES)]


# PharmGKB zip downloader

def download_and_extract(url) -> Dict[str, bytes]:
    """Download a zip to a temp file, extract TSVs, register for cleanup."""
    print(f"  Downloading {url}...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()

    # Save zip to temp file
    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    tmp_zip.write(r.content)
    tmp_zip.close()
    _temp_paths.append(tmp_zip.name)

    tsv_files = {}
    with zipfile.ZipFile(tmp_zip.name) as z:
        for name in z.namelist():
            if name.endswith(".tsv"):
                tsv_files[os.path.basename(name)] = z.read(name)

    return tsv_files


# Table reloaders

def reload_chemicals(conn, cursor, tsv_bytes: bytes):
    print("Reloading chemicals...")
    reader = csv.DictReader(io.StringIO(tsv_bytes.decode("utf-8")), delimiter="\t")

    rows = [
        (row["PharmGKB Accession Id"], row["Name"], row.get("Type", ""))
        for row in reader
        if row.get("PharmGKB Accession Id") and row.get("Name")
    ]

    if not rows:
        raise RuntimeError("Chemicals data is empty or all rows were malformed. Aborting to avoid truncating the table.")

    cursor.execute("TRUNCATE TABLE drug_annotation_chemical, chemical CASCADE")
    execute_values(
        cursor,
        "INSERT INTO chemical (drug_id, name, description) VALUES %s ON CONFLICT (drug_id) DO NOTHING",
        rows,
    )
    conn.commit()
    print(f"  {len(rows)} chemicals loaded.")


def reload_variants(conn, cursor, tsv_bytes: bytes):
    print("Reloading variants...")
    reader = csv.DictReader(io.StringIO(tsv_bytes.decode("utf-8")), delimiter="\t")

    identifier_rows = []
    haplotype_rows = []
    seen_ids = set()

    for row in reader:
        name = row.get("Variant Name")
        gene_symbols = row.get("Gene Symbols", "")
        gene = gene_symbols.split(",")[0].strip() if gene_symbols else None

        if not name:
            continue

        variant_type = "star_allele" if "*" in name else "rsid" if name.startswith("rs") else "unknown"

        if name not in seen_ids:
            seen_ids.add(name)
            identifier_rows.append((name, variant_type, gene))

        if "*" in name and gene:
            haplotype_rows.append((name, gene))

    if not identifier_rows:
        raise RuntimeError("Variants data is empty or all rows were malformed. Aborting to avoid truncating the table.")

    cursor.execute(
        "TRUNCATE TABLE haplotype_identifier, haplotype, variant_identifier_dbsnp, variant_identifier CASCADE"
    )
    execute_values(
        cursor,
        "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
        identifier_rows,
    )
    if haplotype_rows:
        execute_values(
            cursor,
            "INSERT INTO haplotype (name, gene) VALUES %s ON CONFLICT DO NOTHING",
            haplotype_rows,
        )
    conn.commit()
    print(f"  {len(identifier_rows)} variant identifiers loaded.")
    print(f"  {len(haplotype_rows)} haplotypes loaded.")


def reload_functional_annotations(conn, cursor, tsv_bytes: bytes):
    print("Reloading functional annotations...")
    reader = csv.DictReader(io.StringIO(tsv_bytes.decode("utf-8")), delimiter="\t")

    rows = []
    variants_to_add = set()

    for row in reader:
        variant_string = row.get("Variant/Haplotypes", "")
        variants = [v.strip() for v in variant_string.split(",") if v.strip()]
        gene = row.get("Gene", "")
        assay_type = row.get("Assay type", "")
        functional_terms = row.get("Functional terms", "")
        gene_product = row.get("Gene/gene product", "")
        sentence = row.get("Sentence", "")

        for variant in variants:
            variant_type = "star_allele" if "*" in variant else "rsid" if variant.startswith("rs") else "unknown"
            variants_to_add.add((variant, variant_type, gene if gene else None))
            rows.append((variant, sentence, assay_type, gene_product, functional_terms))

    if not rows:
        raise RuntimeError("Functional annotation data is empty or all rows were malformed. Aborting to avoid truncating the table.")

    if variants_to_add:
        execute_values(
            cursor,
            "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
            list(variants_to_add),
        )

    cursor.execute("TRUNCATE TABLE functional_annotation CASCADE")
    execute_values(
        cursor,
        """INSERT INTO functional_annotation
           (identifier_id, effect, assay_type, gene_product, functional_terms)
           VALUES %s""",
        rows,
    )
    conn.commit()
    print(f"  {len(rows)} functional annotations loaded.")


def reload_drug_annotations(conn, cursor, tsv_bytes: bytes):
    print("Reloading drug annotations...")
    reader = csv.DictReader(io.StringIO(tsv_bytes.decode("utf-8")), delimiter="\t")

    variants_to_add = set()
    annotation_rows = []
    variant_links = []
    drug_links = []

    for row in reader:
        annotation_id = row.get("Variant Annotation ID", "")
        variant_string = row.get("Variant/Haplotypes", "")
        gene = row.get("Gene", "")
        drug_string = row.get("Drug(s)", "")
        phenotype = row.get("Phenotype Category", "")
        significance = row.get("Significance", "")
        direction = row.get("Direction of effect", "")
        notes = row.get("Notes", "")
        sentence = row.get("Sentence", "")
        pmid = row.get("PMID", "").strip()

        if not annotation_id:
            continue

        annotation_rows.append((annotation_id, phenotype, significance, direction, notes, sentence, pmid))

        for variant in [v.strip() for v in variant_string.split(",") if v.strip()]:
            variant_type = "star_allele" if "*" in variant else "rsid" if variant.startswith("rs") else "unknown"
            variants_to_add.add((variant, variant_type, gene if gene else None))
            variant_links.append((annotation_id, variant))

        for drug_name in [d.strip() for d in drug_string.split(",") if d.strip()]:
            drug_links.append((annotation_id, drug_name))

    if not annotation_rows:
        raise RuntimeError("Drug annotation data is empty or all rows were malformed. Aborting to avoid truncating the table.")

    if variants_to_add:
        execute_values(
            cursor,
            "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
            list(variants_to_add),
        )

    cursor.execute(
        "TRUNCATE TABLE drug_annotation_variant, drug_annotation_chemical, clinpgx_drug_annotation CASCADE"
    )
    execute_values(
        cursor,
        """INSERT INTO clinpgx_drug_annotation
           (annotation_id, phenotype, significance, direction, notes, sentence, pmid)
           VALUES %s""",
        annotation_rows,
    )

    cursor.execute("SELECT id, annotation_id FROM clinpgx_drug_annotation")
    id_map = {row[1]: row[0] for row in cursor.fetchall()}

    variant_link_rows = [
        (id_map[ann_id], variant)
        for ann_id, variant in variant_links
        if ann_id in id_map
    ]
    if variant_link_rows:
        execute_values(
            cursor,
            "INSERT INTO drug_annotation_variant (annotation_entry, identifier_id) VALUES %s ON CONFLICT DO NOTHING",
            variant_link_rows,
        )

    drug_link_rows = []
    for ann_id, drug_name in drug_links:
        if ann_id not in id_map:
            continue
        cursor.execute(
            "SELECT drug_id FROM chemical WHERE LOWER(name) = LOWER(%s) LIMIT 1",
            (drug_name,)
        )
        result = cursor.fetchone()
        if result:
            drug_link_rows.append((id_map[ann_id], result[0]))

    if drug_link_rows:
        execute_values(
            cursor,
            "INSERT INTO drug_annotation_chemical (annotation_entry, drug_id) VALUES %s ON CONFLICT DO NOTHING",
            drug_link_rows,
        )

    conn.commit()
    print(f"  {len(annotation_rows)} drug annotations loaded.")


# PharmVar reload

def download_pharmvar() -> str:
    """Download PharmVar zip to a temp dir, return the extracted directory path."""
    print(f"  Downloading PharmVar data...")
    r = requests.get(PHARMVAR_URL, timeout=120)
    r.raise_for_status()

    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    tmp_zip.write(r.content)
    tmp_zip.close()
    _temp_paths.append(tmp_zip.name)

    extract_dir = tempfile.mkdtemp()
    _temp_paths.append(extract_dir)

    with zipfile.ZipFile(tmp_zip.name) as z:
        z.extractall(extract_dir)

    return extract_dir


def find_haplotype_tsvs(extract_dir: str) -> List[Tuple[str, str]]:
    """Find all haplotypes.tsv files for GRCh38 for target genes."""
    tsv_files = []
    for root, dirs, files in os.walk(extract_dir):
        if GENOME_BUILD not in root:
            continue
        gene = os.path.basename(os.path.dirname(root)) if GENOME_BUILD in os.path.basename(root) else os.path.basename(root.rstrip('/').rsplit('/', 2)[-2])
        for fname in files:
            if fname.endswith('.haplotypes.tsv'):
                gene_name = fname.split('.')[0]
                if gene_name in TARGET_GENES:
                    tsv_files.append((gene_name, os.path.join(root, fname)))
    return tsv_files


def parse_haplotype_tsv(path: str) -> List[Tuple[str, str, str]]:
    """Parse a haplotypes.tsv, return list of (haplotype_name, gene, rsid) for core alleles only."""
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = [l for l in f if not l.startswith('#')]

    reader = csv.DictReader(lines, delimiter='\t')
    for row in reader:
        haplotype = row.get('Haplotype Name', '').strip()
        gene = row.get('Gene', '').strip()
        rsid = row.get('rsID', '').strip()
        if not haplotype or not gene or not rsid:
            continue
        star_part = haplotype.split('*')[-1] if '*' in haplotype else ''
        if '.' not in star_part:
            rows.append((haplotype, gene, rsid))
    return rows


def reload_pharmvar(conn, cursor, extract_dir: str):
    print("Reloading PharmVar haplotype mappings...")

    tsv_files = find_haplotype_tsvs(extract_dir)
    print(f"  Found {len(tsv_files)} haplotype TSV files")

    all_rows = []
    for gene, path in tsv_files:
        rows = parse_haplotype_tsv(path)
        all_rows.extend(rows)

    if not all_rows:
        print("  No PharmVar rows parsed, skipping.")
        return

    # Build unique haplotypes
    unique_haplotypes = list({(r[0], r[1]) for r in all_rows})
    haplotype_id_map = {}

    for name, gene in unique_haplotypes:
        cursor.execute(
            """INSERT INTO haplotype (name, gene)
               VALUES (%s, %s)
               ON CONFLICT (name, gene) DO NOTHING
               RETURNING haplotype_id""",
            (name, gene)
        )
        result = cursor.fetchone()
        if result:
            haplotype_id_map[(name, gene)] = result[0]
        else:
            cursor.execute(
                "SELECT haplotype_id FROM haplotype WHERE name = %s AND gene = %s",
                (name, gene)
            )
            haplotype_id_map[(name, gene)] = cursor.fetchone()[0]

    # Clear existing haplotype_identifier links and rebuild
    cursor.execute("TRUNCATE TABLE haplotype_identifier")

    linked = 0
    for haplotype_name, gene, rsid in all_rows:
        haplotype_id = haplotype_id_map.get((haplotype_name, gene))
        if not haplotype_id:
            continue
        cursor.execute(
            """SELECT vi.id FROM variant_identifier vi
               JOIN variant_identifier_dbsnp vid ON vi.id = vid.id
               WHERE vid.rsid = %s""",
            (rsid,)
        )
        identifiers = cursor.fetchall()
        if not identifiers:
            cursor.execute("SELECT id FROM variant_identifier WHERE id = %s", (rsid,))
            identifiers = cursor.fetchall()
        for (identifier_id,) in identifiers:
            cursor.execute(
                """INSERT INTO haplotype_identifier (haplotype_id, identifier_id)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                (haplotype_id, identifier_id)
            )
            linked += 1

    conn.commit()
    print(f"  PharmVar reload complete. {linked} haplotype-variant links created.")


# Dispatcher

def run_updates(tsvs: Dict[str, bytes]):
    conn = get_connection()
    cursor = conn.cursor()
    failed = []

    reloaders = [
        ("chemicals",    reload_chemicals,              tsvs["chemicals.tsv"]),
        ("variants",     reload_variants,               tsvs["variants.tsv"]),
        ("var_fa_ann",   reload_functional_annotations, tsvs["var_fa_ann.tsv"]),
        ("var_drug_ann", reload_drug_annotations,       tsvs["var_drug_ann.tsv"]),
    ]

    for name, reloader, tsv_bytes in reloaders:
        try:
            reloader(conn, cursor, tsv_bytes)
        except Exception as e:
            conn.rollback()
            print(f"Error reloading '{name}': {e}")
            failed.append((name, str(e)))

    # PharmVar — runs after variants are reloaded so haplotype table is fresh
    try:
        pharmvar_dir = download_pharmvar()
        reload_pharmvar(conn, cursor, pharmvar_dir)
    except Exception as e:
        conn.rollback()
        print(f"Error reloading PharmVar: {e}")
        failed.append(("pharmvar", str(e)))

    cursor.close()
    conn.close()

    if failed:
        summary = "; ".join(f"{t}: {e}" for t, e in failed)
        raise RuntimeError(f"The following table groups failed to reload: {summary}")


# Cleanup

def cleanup_temp_files():
    """Remove all temporary files and directories created during this run."""
    print("Cleaning up temporary files...")
    removed = 0
    for path in _temp_paths:
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
            removed += 1
        except Exception as e:
            print(f"  Could not remove {path}: {e}")
    print(f"  Removed {removed} temporary file(s)/director(ies).")


# dbSNP helpers

def fetch_dbsnp_rsid(rsid: str) -> Optional[Dict]:
    try:
        r = requests.get(
            DBSNP_API_URL,
            params={"terms": rsid, "maxList": 1},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  Error {r.status_code} for {rsid}")
            return None

        data = r.json()
        if len(data) < 4 or not data[3]:
            return None

        return {"data": data, "rsid": rsid}

    except Exception as e:
        print(f"  Exception while fetching {rsid}: {e}")
        return None


def extract_variants_from_dbsnp(rsid: str, response: Dict) -> List[Tuple]:
    variants = []
    try:
        data = response.get("data", response)
        original_rsid = response.get("rsid", rsid)

        if len(data) < 4 or not data[3]:
            return variants

        for row in data[3]:
            if not row or len(row) < 4:
                continue

            chromosome = row[1]
            position = row[2]
            allele_string = row[3]

            if not allele_string or "/" not in allele_string:
                continue

            for allele_group in allele_string.split(", "):
                alleles = allele_group.split("/")
                if len(alleles) < 2:
                    continue

                ref = alleles[0]
                alts = alleles[1:]

                if not ref or not chromosome:
                    continue

                if str(chromosome).isdigit() or chromosome in ["X", "Y", "M", "MT"]:
                    chrom = f"chr{chromosome}"
                elif chromosome.startswith("chr"):
                    chrom = chromosome
                else:
                    chrom = f"chr{chromosome}"

                try:
                    pos_int = int(position)
                except (ValueError, TypeError):
                    continue

                for alt in alts:
                    if alt and alt != ref:
                        variants.append((original_rsid, chrom, pos_int, ref.upper(), alt.upper()))

    except Exception as e:
        print(f"  Error parsing {rsid}: {e}")

    return variants


def get_rsids_from_db(cursor) -> List[str]:
    cursor.execute("""
        SELECT DISTINCT id
        FROM variant_identifier
        WHERE type = 'rsid' AND id LIKE 'rs%'
        ORDER BY id
    """)
    return [row[0] for row in cursor.fetchall()]


def process_rsid(rsid: str, index: int, total: int) -> Tuple[str, List]:
    response = fetch_dbsnp_rsid(rsid)
    if response is None:
        return rsid, []
    variants = extract_variants_from_dbsnp(rsid, response)
    if index % 50 == 0:
        print(f"  [{index}/{total}] {rsid} -> {len(variants)} variant(s)")
    return rsid, variants


def update_variant_identifier_dbsnp_links(conn, cursor):
    print("  Updating variant_identifier_dbsnp links...")
    cursor.execute("""
        INSERT INTO variant_identifier_dbsnp (id, rsid)
        SELECT DISTINCT vi.id, dv.rsid
        FROM variant_identifier vi
        JOIN dbsnp_variant dv ON vi.id = dv.rsid
        WHERE vi.type = 'rsid'
        ON CONFLICT DO NOTHING
    """)
    print(f"  {cursor.rowcount} links created in variant_identifier_dbsnp.")
    conn.commit()


def reload_dbsnp(conn, cursor):
    print("Reloading dbSNP variants...")

    rsids = get_rsids_from_db(cursor)
    if not rsids:
        print("  No rsIDs found in variant_identifier, skipping dbSNP reload.")
        return

    print(f"  Found {len(rsids)} rsIDs to fetch.")

    all_variants = []
    failed = []

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(process_rsid, rsid, i, len(rsids)): rsid
            for i, rsid in enumerate(rsids, 1)
        }
        for future in as_completed(futures):
            rsid, variants = future.result()
            if not variants:
                failed.append(rsid)
            else:
                all_variants.extend(variants)

    print(f"  Fetched {len(all_variants)} variant entries, {len(failed)} rsIDs failed.")

    if all_variants:
        execute_values(
            cursor,
            """INSERT INTO dbsnp_variant (rsid, chrom, pos, ref, alt)
               VALUES %s ON CONFLICT DO NOTHING""",
            all_variants,
        )
        vcf_data = [(v[1], v[2], v[3], v[4], v[0]) for v in all_variants]
        try:
            execute_values(
                cursor,
                """INSERT INTO vcf_variant (chrom, pos, ref, alt, rsid)
                   VALUES %s ON CONFLICT (chrom, pos, ref, alt) DO UPDATE SET rsid = EXCLUDED.rsid""",
                vcf_data,
            )
        except Exception as e:
            print(f"  vcf_variant insert issue: {e}")
            conn.rollback()

        conn.commit()

    update_variant_identifier_dbsnp_links(conn, cursor)

    if failed:
        print(f"  Failed rsIDs ({len(failed)}): {failed[:10]}{'...' if len(failed) > 10 else ''}")

    print("  dbSNP reload complete.")


# Docker sync

def update_docker_db():
    """Dump Docker DB to backup.sql."""
    print("Producing backup.sql...")
    backup_path = "/home/styrak/bc/backup.sql"
    try:
        dump = subprocess.run(
            ["docker", "compose", "-f", "/home/styrak/bc/docker-compose.yml",
             "exec", "-T", "db", "pg_dump", "-U", "postgres", "pharmacogenomic_data"],
            capture_output=True,
            check=True
        )
        with open(backup_path, 'wb') as f:
            f.write(dump.stdout)
        print(f"  backup.sql written ({len(dump.stdout) // 1024 // 1024} MB).")
    except subprocess.CalledProcessError as e:
        print(f"  pg_dump failed: {e}")
        print("  backup.sql was NOT updated.")
        return

    print("  backup.sql is up to date.")

# Entry point

def main(full_update=False):
    try:
        last_synced = get_last_synced_date()
    except Exception as e:
        print(f"Failed to read last synced date from DB: {e}")
        return
    print(f"Last synced: {last_synced}")

    try:
        df = download_changes_tsv()
    except RuntimeError as e:
        print(f"Failed to download changelog: {e}")
        return

    try:
        relevant_changes = get_relevant_changes(df, last_synced)
    except Exception as e:
        print(f"Failed to process changelog: {e}")
        return

    if relevant_changes.empty:
        print("No relevant changes found. Nothing to update.")
        cleanup_temp_files()
        return

    latest_date = relevant_changes["Date of Change"].max().date()
    print(f"Found {len(relevant_changes)} relevant change(s) up to {latest_date}.")

    print("Downloading PharmGKB zip files...")
    try:
        variant_tsvs  = download_and_extract(PHARMGKB_DOWNLOADS["variants"])
        chemical_tsvs = download_and_extract(PHARMGKB_DOWNLOADS["chemicals"])
        annotation_tsvs = download_and_extract(PHARMGKB_DOWNLOADS["annotations"])
    except Exception as e:
        print(f"Failed to download PharmGKB data: {e}")
        cleanup_temp_files()
        return

    tsvs = {
        "variants.tsv":     variant_tsvs["variants.tsv"],
        "chemicals.tsv":    chemical_tsvs["chemicals.tsv"],
        "var_fa_ann.tsv":   annotation_tsvs["var_fa_ann.tsv"],
        "var_drug_ann.tsv": annotation_tsvs["var_drug_ann.tsv"],
    }

    try:
        run_updates(tsvs)
    except RuntimeError as e:
        print(f"Update finished with errors: {e}")
        print("Sync date was NOT updated. Fix the errors above and re-run.")
        cleanup_temp_files()
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()
        reload_dbsnp(conn, cursor)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"dbSNP reload failed: {e}")
        print("PharmGKB tables are up to date but dbSNP/vcf data may be stale.")

    try:
        update_last_synced_date(latest_date)
    except Exception as e:
        print(f"All tables reloaded successfully, but failed to update sync date: {e}")
        print("Re-running will reload the same data again. Consider updating sync_state manually.")
        cleanup_temp_files()
        return

    cleanup_temp_files()
    update_docker_db()
    print(f"Sync date updated to {latest_date}. All done.")


if __name__ == "__main__":
    main(full_update=False)