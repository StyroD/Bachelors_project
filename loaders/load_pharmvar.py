#!/usr/bin/env python3

import os
import csv
import sys
import psycopg2
from psycopg2.extras import execute_values

PHARMVAR_DIR = "/tmp/pharmvar/pharmvar-6.2.22"
GENOME_BUILD = "GRCh38"

DB_CONFIG = {
    'dbname': 'pharmacogenomic_data',
    'user': 'postgres',
    'password': '789#',
    'host': 'localhost',
    'port': 5432
}

# Only load genes we have annotations for
TARGET_GENES = {
    'CYP1A2', 'CYP2A6', 'CYP2B6', 'CYP2C19', 'CYP2C8',
    'CYP2C9', 'CYP2D6', 'CYP3A4', 'CYP3A5', 'CYP4F2',
    'DPYD', 'NAT2', 'NUDT15', 'SLCO1B1'
}


def find_tsv_files():
    """Find all haplotypes.tsv files for GRCh38."""
    tsv_files = []
    for gene in os.listdir(PHARMVAR_DIR):
        gene_dir = os.path.join(PHARMVAR_DIR, gene, GENOME_BUILD)
        if not os.path.isdir(gene_dir):
            continue
        if gene not in TARGET_GENES:
            continue
        for fname in os.listdir(gene_dir):
            if fname.endswith('.haplotypes.tsv'):
                tsv_files.append((gene, os.path.join(gene_dir, fname)))
    return tsv_files


def parse_tsv(path):
    """Parse a haplotypes.tsv file. Returns list of (haplotype_name, gene, rsid)."""
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'):
                continue
            break
        # Reset and use DictReader
        f.seek(0)
        lines = [l for l in f if not l.startswith('#')]

    reader = csv.DictReader(lines, delimiter='\t')
    for row in reader:
        haplotype = row.get('Haplotype Name', '').strip()
        gene = row.get('Gene', '').strip()
        rsid = row.get('rsID', '').strip()

        if not haplotype or not gene or not rsid:
            continue
        # Skip suballeles (e.g. CYP2D6*1.001) - only keep main alleles
        # Uncomment below line if you want suballeles too
        # rows.append((haplotype, gene, rsid))

        # Only keep core alleles (no dot in the star number part)
        star_part = haplotype.split('*')[-1] if '*' in haplotype else ''
        if '.' not in star_part:
            rows.append((haplotype, gene, rsid))

    return rows


def load(conn, cur, rows):
    """Insert haplotypes and link them to variant_identifiers via rsID."""

    # Build unique haplotype list
    haplotypes = {}  # (name, gene) -> haplotype_id
    unique = list({(r[0], r[1]) for r in rows})

    print(f"  Inserting {len(unique)} unique haplotypes...")
    for name, gene in unique:
        cur.execute(
            """INSERT INTO haplotype (name, gene)
               VALUES (%s, %s)
               ON CONFLICT DO NOTHING
               RETURNING haplotype_id""",
            (name, gene)
        )
        result = cur.fetchone()
        if result:
            haplotypes[(name, gene)] = result[0]
        else:
            cur.execute(
                "SELECT haplotype_id FROM haplotype WHERE name = %s AND gene = %s",
                (name, gene)
            )
            haplotypes[(name, gene)] = cur.fetchone()[0]

    # Now link haplotypes to variant_identifiers
    # variant_identifier uses rsid as id when type='rsid'
    linked = 0
    skipped = 0
    for haplotype_name, gene, rsid in rows:
        haplotype_id = haplotypes.get((haplotype_name, gene))
        if not haplotype_id:
            continue

        # Find variant_identifier records linked to this rsid via variant_identifier_dbsnp
        cur.execute(
            """SELECT vi.id FROM variant_identifier vi
               JOIN variant_identifier_dbsnp vid ON vi.id = vid.id
               WHERE vid.rsid = %s""",
            (rsid,)
        )
        identifiers = cur.fetchall()

        if not identifiers:
            # Also try direct rsid match (some are stored directly)
            cur.execute(
                "SELECT id FROM variant_identifier WHERE id = %s",
                (rsid,)
            )
            identifiers = cur.fetchall()

        if identifiers:
            for (identifier_id,) in identifiers:
                cur.execute(
                    """INSERT INTO haplotype_identifier (haplotype_id, identifier_id)
                       VALUES (%s, %s)
                       ON CONFLICT DO NOTHING""",
                    (haplotype_id, identifier_id)
                )
            linked += 1
        else:
            skipped += 1

    return linked, skipped


def main():
    tsv_files = find_tsv_files()
    print(f"Found {len(tsv_files)} TSV files to process")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        total_linked = 0
        total_skipped = 0

        for gene, path in sorted(tsv_files):
            print(f"\nProcessing {gene}...")
            rows = parse_tsv(path)
            print(f"  Parsed {len(rows)} haplotype-rsID rows")

            linked, skipped = load(conn, cur, rows)
            total_linked += linked
            total_skipped += skipped
            print(f"  Linked: {linked}, No matching variant_identifier: {skipped}")

        conn.commit()
        print(f"\n Done! Total linked: {total_linked}, skipped: {total_skipped}")

    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()