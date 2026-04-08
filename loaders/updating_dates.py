#!/usr/bin/env python3
"""
Checks CPIC changelog for new entries since last sync.
If relevant changes are found, downloads fresh PharmGKB zip files
and reloads the affected PostgreSQL tables, then re-downloads dbSNP data.
"""

import csv
import io
import subprocess
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
    "port": 5432,
}

RELEVANT_TYPES = {
    "ALLELE_DEFINITION",
    "ALLELE_FUNCTION_REFERENCE",
    "GENE_CDS",
    "RECOMMENDATION",
    "PAIR",
}


# Database helpers

def ensure_db_running():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        return True
    except psycopg2.OperationalError:
        try:
            subprocess.run(["sudo", "systemctl", "start", "postgresql"], check=True)
            return True
        except Exception:
            return False


def get_connection():
    if not ensure_db_running():
        raise RuntimeError("PostgreSQL is not running. Please start the service.")
    return psycopg2.connect(**DB_CONFIG)


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
    """Download a zip and return {filename: content} for all TSV files inside."""
    print(f"  Downloading {url}...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    tsv_files = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for name in z.namelist():
            if name.endswith(".tsv"):
                tsv_files[name] = z.read(name)
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

        if not annotation_id:
            continue

        annotation_rows.append((annotation_id, phenotype, significance, direction, notes, sentence))

        for variant in [v.strip() for v in variant_string.split(",") if v.strip()]:
            variant_type = "star_allele" if "*" in variant else "rsid" if variant.startswith("rs") else "unknown"
            variants_to_add.add((variant, variant_type, gene if gene else None))
            variant_links.append((annotation_id, variant))

        for drug_name in [d.strip() for d in drug_string.split(",") if d.strip()]:
            drug_links.append((annotation_id, drug_name))

    if not annotation_rows:
        raise RuntimeError("Drug annotation data is empty or all rows were malformed. Aborting to avoid truncating the table.")

    # Insert missing variants BEFORE truncating annotation tables and inserting links
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
           (annotation_id, phenotype, significance, direction, notes, sentence)
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

    cursor.close()
    conn.close()

    if failed:
        summary = "; ".join(f"{t}: {e}" for t, e in failed)
        raise RuntimeError(f"The following table groups failed to reload: {summary}")


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
        return

    latest_date = relevant_changes["Date of Change"].max().date()
    print(f"Found {len(relevant_changes)} relevant change(s) up to {latest_date}.")

    print("Downloading PharmGKB zip files...")
    try:
        variant_tsvs = download_and_extract(PHARMGKB_DOWNLOADS["variants"])
        chemical_tsvs = download_and_extract(PHARMGKB_DOWNLOADS["chemicals"])
        annotation_tsvs = download_and_extract(PHARMGKB_DOWNLOADS["annotations"])
    except Exception as e:
        print(f"Failed to download PharmGKB data: {e}")
        return

    tsvs = {
        "variants.tsv":    variant_tsvs["variants.tsv"],
        "chemicals.tsv":   chemical_tsvs["chemicals.tsv"],
        "var_fa_ann.tsv":  annotation_tsvs["var_fa_ann.tsv"],
        "var_drug_ann.tsv": annotation_tsvs["var_drug_ann.tsv"],
    }

    try:
        run_updates(tsvs)
    except RuntimeError as e:
        print(f"Update finished with errors: {e}")
        print("Sync date was NOT updated. Fix the errors above and re-run.")
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
        return

    print(f"Sync date updated to {latest_date}.")


if __name__ == "__main__":
    main(full_update=False)