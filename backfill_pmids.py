import csv
import psycopg2
import sys

csv.field_size_limit(sys.maxsize)

DB_CONFIG = {
    'dbname': 'pharmacogenomic_data',
    'user': 'postgres',
    'password': '789#',
    'host': 'localhost',
    'port': 5432
}

TSV_DRUG  = 'clinpgx_data/variantAnnotations/var_drug_ann.tsv'

TSV_FA    = 'clinpgx_data/variantAnnotations/var_fa_ann.tsv'


def backfill_drug_and_pheno(cur):
    """
    clinpgx_drug_annotation already has annotation_id — just fill in pmid.
    Only var_drug_ann maps by Variant Annotation ID.
    """
    pmid_map = {}

    for path in [TSV_DRUG]:
        print(f"Reading {path}...")
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                ann_id = row.get('Variant Annotation ID', '').strip()
                pmid   = row.get('PMID', '').strip()
                if ann_id and pmid:
                    pmid_map[ann_id] = pmid

    print(f"  Found {len(pmid_map)} PMID mappings")

    updated = 0
    for ann_id, pmid in pmid_map.items():
        cur.execute(
            "UPDATE clinpgx_drug_annotation SET pmid = %s WHERE annotation_id = %s",
            (pmid, ann_id)
        )
        updated += cur.rowcount

    print(f"  Updated {updated} rows in clinpgx_drug_annotation")


def backfill_functional(cur):
    """
    functional_annotation has no annotation_id — match on sentence text,
    then store both annotation_id and pmid.
    """
    print(f"Reading {TSV_FA}...")

    # Build map: sentence -> (annotation_id, pmid)
    sentence_map = {}
    with open(TSV_FA, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            ann_id   = row.get('Variant Annotation ID', '').strip()
            pmid     = row.get('PMID', '').strip()
            sentence = row.get('Sentence', '').strip()
            if sentence and ann_id:
                sentence_map[sentence] = (ann_id, pmid)

    print(f"  Found {len(sentence_map)} sentence->PMID mappings")

    # Fetch all functional annotations
    cur.execute("SELECT id, effect FROM functional_annotation WHERE pmid IS NULL")
    rows = cur.fetchall()

    updated = 0
    unmatched = 0
    for fa_id, effect in rows:
        if not effect:
            continue
        match = sentence_map.get(effect.strip())
        if match:
            ann_id, pmid = match
            cur.execute(
                "UPDATE functional_annotation SET annotation_id = %s, pmid = %s WHERE id = %s",
                (ann_id, pmid, fa_id)
            )
            updated += cur.rowcount
        else:
            unmatched += 1

    print(f"  Updated {updated} rows in functional_annotation")
    if unmatched:
        print(f"  Could not match {unmatched} rows (sentence mismatch)")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    try:
        backfill_drug_and_pheno(cur)
        backfill_functional(cur)
        conn.commit()
        print("\n✓ Backfill completed successfully!")
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