import psycopg2
from psycopg2.extras import RealDictCursor
import os


def get_connection():
    """Return a new PostgreSQL connection."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "789#"),
        database=os.environ.get("DB_NAME", "pharmacogenomic_data"),
    )


def query_full_annotation(pos=None, ref=None, alt=None, rsid=None, chrom=None):
    """Query full variant annotation with all joins."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
    SELECT
        v.vcf_id,
        v.chrom,
        v.pos,
        v.ref,
        v.alt,
        v.rsid,
        vi.id AS identifier_id,
        vi.type AS identifier_type,
        vi.gene AS gene,
        fa.effect,
        fa.assay_type,
        fa.gene_product,
        fa.functional_terms,
        cda.annotation_id,
        cda.phenotype,
        cda.significance,
        cda.direction,
        cda.notes,
        cda.sentence,
        c.drug_id,
        c.name AS drug_name
    FROM vcf_variant v
    LEFT JOIN variant_identifier_dbsnp vid
        ON v.rsid = vid.rsid
    LEFT JOIN variant_identifier vi
        ON vid.id = vi.id
    LEFT JOIN functional_annotation fa
        ON fa.identifier_id = vi.id
    LEFT JOIN drug_annotation_variant dav
        ON dav.identifier_id = vi.id
    LEFT JOIN clinpgx_drug_annotation cda
        ON dav.annotation_entry = cda.id
    LEFT JOIN drug_annotation_chemical dac
        ON dac.annotation_entry = cda.id
    LEFT JOIN chemical c
        ON dac.drug_id = c.drug_id
    WHERE 1 = 1
    """

    params = []

    if chrom is not None:
        sql += " AND v.chrom = %s"
        params.append(str(chrom))

    if pos is not None:
        sql += " AND v.pos = %s"
        params.append(int(pos))

    if ref is not None:
        sql += " AND v.ref = %s"
        params.append(ref)

    if alt is not None:
        sql += " AND v.alt = %s"
        params.append(alt)

    if rsid is not None:
        sql += " AND v.rsid = %s"
        params.append(rsid)

    sql += " ORDER BY v.pos LIMIT 200;"

    cur.execute(sql, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows


def search_vcf(query):
    """Search vcf_variant table for matching records."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT vcf_id, chrom, pos, ref, alt, rsid
        FROM vcf_variant
        WHERE chrom::text ILIKE %s
           OR ref ILIKE %s
           OR alt ILIKE %s
           OR rsid ILIKE %s
           OR pos::text ILIKE %s
        ORDER BY pos
        LIMIT 50;
    """

    like = f"%{query}%"
    cur.execute(sql, (like, like, like, like, like))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows


def autocomplete_variants(query, limit=10):
    """Get autocomplete suggestions for variants."""
    if not query or len(query) < 2:
        return []

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
        SELECT vcf_id, chrom, pos, ref, alt, rsid
        FROM vcf_variant
        WHERE rsid ILIKE %s
           OR chrom::text ILIKE %s
           OR pos::text ILIKE %s
        ORDER BY
            CASE WHEN rsid ILIKE %s THEN 1 ELSE 2 END,
            pos
        LIMIT %s;
    """

    like = f"%{query}%"
    starts_with = f"{query}%"
    cur.execute(sql, (like, like, like, starts_with, limit))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows


def search_variant(chrom, pos, ref, alt):
    """Search for a specific variant."""
    return query_full_annotation(chrom=chrom, pos=pos, ref=ref, alt=alt)


def search_rsid(rsid):
    """Search by rsID."""
    return query_full_annotation(rsid=rsid)


def get_variant_detail(vcf_id):
    """Get detailed annotation for a specific variant by vcf_id."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
    SELECT
        v.vcf_id,
        v.chrom,
        v.pos,
        v.ref,
        v.alt,
        v.rsid,
        vi.id AS identifier_id,
        vi.type AS identifier_type,
        vi.gene AS gene,
        fa.effect,
        fa.assay_type,
        fa.gene_product,
        fa.functional_terms,
        cda.annotation_id,
        cda.phenotype,
        cda.significance,
        cda.direction,
        cda.notes,
        cda.sentence,
        c.drug_id,
        c.name AS drug_name
    FROM vcf_variant v
    LEFT JOIN variant_identifier_dbsnp vid ON v.rsid = vid.rsid
    LEFT JOIN variant_identifier vi         ON vid.id = vi.id
    LEFT JOIN functional_annotation fa      ON fa.identifier_id = vi.id
    LEFT JOIN drug_annotation_variant dav   ON dav.identifier_id = vi.id
    LEFT JOIN clinpgx_drug_annotation cda   ON dav.annotation_entry = cda.id
    LEFT JOIN drug_annotation_chemical dac  ON dac.annotation_entry = cda.id
    LEFT JOIN chemical c                    ON dac.drug_id = c.drug_id
    WHERE v.vcf_id = %s;
    """

    cur.execute(sql, (vcf_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def search_variants_batch(variants: list) -> list:
    if not variants:
        return []

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            CREATE TEMP TABLE tmp_variants (
                chrom TEXT,
                pos INT,
                ref TEXT,
                alt TEXT
            ) ON COMMIT DROP
        """)

        from psycopg2.extras import execute_values
        execute_values(
            cur,
            "INSERT INTO tmp_variants (chrom, pos, ref, alt) VALUES %s",
            [(v['chrom'], v['pos'], v['ref'], v['alt']) for v in variants]
        )

        cur.execute("""
            SELECT
                v.vcf_id, v.chrom, v.pos, v.ref, v.alt, v.rsid,
                vi.id AS identifier_id, vi.type AS identifier_type, vi.gene,
                fa.effect, fa.assay_type, fa.gene_product, fa.functional_terms,
                cda.annotation_id, cda.phenotype, cda.significance,
                cda.direction, cda.notes, cda.sentence,
                c.drug_id, c.name AS drug_name
            FROM tmp_variants t
            JOIN vcf_variant v
                ON v.chrom = t.chrom AND v.pos = t.pos AND v.ref = t.ref AND v.alt = t.alt
            LEFT JOIN variant_identifier_dbsnp vid ON v.rsid = vid.rsid
            LEFT JOIN variant_identifier vi         ON vid.id = vi.id
            LEFT JOIN functional_annotation fa      ON fa.identifier_id = vi.id
            LEFT JOIN drug_annotation_variant dav   ON dav.identifier_id = vi.id
            LEFT JOIN clinpgx_drug_annotation cda   ON dav.annotation_entry = cda.id
            LEFT JOIN drug_annotation_chemical dac  ON dac.annotation_entry = cda.id
            LEFT JOIN chemical c                    ON dac.drug_id = c.drug_id
            ORDER BY v.chrom, v.pos
        """)

        results = cur.fetchall()
        conn.commit()
        return results

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()