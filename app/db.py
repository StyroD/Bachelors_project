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
        dv.rsid AS vcf_id,
        dv.chrom,
        dv.pos,
        dv.ref,
        dv.alt,
        dv.rsid,
        vi.id AS identifier_id,
        vi.type AS identifier_type,
        COALESCE(vi.gene, h.gene) AS gene,
        fa.effect,
        fa.assay_type,
        fa.gene_product,
        fa.functional_terms,
        cda.annotation_id,
        cda.pmid,
        cda.phenotype,
        cda.significance,
        cda.direction,
        cda.notes,
        cda.sentence,
        c.drug_id,
        c.name AS drug_name
    FROM dbsnp_variant dv
    LEFT JOIN variant_identifier_dbsnp vid ON dv.rsid = vid.rsid
    LEFT JOIN variant_identifier vi         ON vid.id = vi.id
    LEFT JOIN functional_annotation fa      ON fa.identifier_id = vi.id
    LEFT JOIN haplotype_identifier hi       ON hi.identifier_id = vi.id
    LEFT JOIN haplotype h                   ON h.haplotype_id = hi.haplotype_id
    JOIN drug_annotation_variant dav        ON dav.identifier_id = vi.id
    JOIN clinpgx_drug_annotation cda        ON dav.annotation_entry = cda.id
    LEFT JOIN drug_annotation_chemical dac  ON dac.annotation_entry = cda.id
    LEFT JOIN chemical c                    ON dac.drug_id = c.drug_id
    WHERE 1 = 1
    """

    params = []

    if chrom is not None:
        sql += " AND dv.chrom = %s"
        params.append(str(chrom))

    if pos is not None:
        sql += " AND dv.pos = %s"
        params.append(int(pos))

    if ref is not None:
        sql += " AND dv.ref = %s"
        params.append(ref)

    if alt is not None:
        sql += " AND dv.alt = %s"
        params.append(alt)

    if rsid is not None:
        sql += " AND dv.rsid = %s"
        params.append(rsid)

    sql += " ORDER BY dv.pos LIMIT 200;"

    cur.execute(sql, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows


def search_vcf(query):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    sql = """
        SELECT DISTINCT dv.rsid AS vcf_id, dv.chrom, dv.pos, dv.ref, dv.alt, dv.rsid
        FROM dbsnp_variant dv
        JOIN variant_identifier_dbsnp vid ON dv.rsid = vid.rsid
        JOIN variant_identifier vi         ON vid.id = vi.id
        JOIN drug_annotation_variant dav   ON dav.identifier_id = vi.id
        JOIN clinpgx_drug_annotation cda   ON dav.annotation_entry = cda.id
        WHERE dv.chrom ILIKE %s
           OR dv.ref ILIKE %s
           OR dv.alt ILIKE %s
           OR dv.rsid ILIKE %s
           OR dv.pos::text ILIKE %s
        ORDER BY dv.pos
        LIMIT 50;
    """
    like = f"%{query}%"
    cur.execute(sql, (like, like, like, like, like))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def autocomplete_variants(query, limit=10):
    if not query or len(query) < 2:
        return []
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    sql = """
        SELECT DISTINCT dv.rsid AS vcf_id, dv.chrom, dv.pos, dv.ref, dv.alt, dv.rsid,
            CASE WHEN dv.rsid ILIKE %s THEN 1 ELSE 2 END AS sort_order
        FROM dbsnp_variant dv
        JOIN variant_identifier_dbsnp vid ON dv.rsid = vid.rsid
        JOIN variant_identifier vi         ON vid.id = vi.id
        JOIN drug_annotation_variant dav   ON dav.identifier_id = vi.id
        JOIN clinpgx_drug_annotation cda   ON dav.annotation_entry = cda.id
        WHERE dv.rsid ILIKE %s
           OR dv.chrom ILIKE %s
           OR dv.pos::text ILIKE %s
        ORDER BY sort_order, dv.pos
        LIMIT %s;
    """
    starts_with = f"{query}%"
    like = f"%{query}%"
    cur.execute(sql, (starts_with, like, like, like, limit))
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
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
    SELECT
        dv.rsid AS vcf_id,
        dv.chrom,
        dv.pos,
        dv.ref,
        dv.alt,
        dv.rsid,
        vi.id AS identifier_id,
        vi.type AS identifier_type,
        COALESCE(vi.gene, h.gene) AS gene,
        fa.effect,
        fa.assay_type,
        fa.gene_product,
        fa.functional_terms,
        cda.annotation_id,
        cda.pmid,
        cda.phenotype,
        cda.significance,
        cda.direction,
        cda.notes,
        cda.sentence,
        c.drug_id,
        c.name AS drug_name
    FROM dbsnp_variant dv
    LEFT JOIN variant_identifier_dbsnp vid ON dv.rsid = vid.rsid
    LEFT JOIN variant_identifier vi         ON vid.id = vi.id
    LEFT JOIN functional_annotation fa      ON fa.identifier_id = vi.id
    LEFT JOIN haplotype_identifier hi       ON hi.identifier_id = vi.id
    LEFT JOIN haplotype h                   ON h.haplotype_id = hi.haplotype_id
    JOIN drug_annotation_variant dav   ON dav.identifier_id = vi.id
    JOIN clinpgx_drug_annotation cda   ON dav.annotation_entry = cda.id
    LEFT JOIN drug_annotation_chemical dac  ON dac.annotation_entry = cda.id
    LEFT JOIN chemical c                    ON dac.drug_id = c.drug_id
    WHERE dv.rsid = %s;
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
                dv.rsid AS vcf_id, dv.chrom, dv.pos, dv.ref, dv.alt, dv.rsid,
                vi.id AS identifier_id, vi.type AS identifier_type, COALESCE(vi.gene, h.gene) AS gene,
                fa.effect, fa.assay_type, fa.gene_product, fa.functional_terms,
                cda.annotation_id, cda.pmid, cda.phenotype, cda.significance,
                cda.direction, cda.notes, cda.sentence,
                c.drug_id, c.name AS drug_name
            FROM tmp_variants t
            JOIN dbsnp_variant dv
                ON dv.chrom = t.chrom AND dv.pos = t.pos AND dv.ref = t.ref AND dv.alt = t.alt
            LEFT JOIN variant_identifier_dbsnp vid ON dv.rsid = vid.rsid
            LEFT JOIN variant_identifier vi         ON vid.id = vi.id
            LEFT JOIN functional_annotation fa      ON fa.identifier_id = vi.id
            LEFT JOIN haplotype_identifier hi       ON hi.identifier_id = vi.id
            LEFT JOIN haplotype h                   ON h.haplotype_id = hi.haplotype_id
            JOIN drug_annotation_variant dav   ON dav.identifier_id = vi.id
            JOIN clinpgx_drug_annotation cda   ON dav.annotation_entry = cda.id
            LEFT JOIN drug_annotation_chemical dac  ON dac.annotation_entry = cda.id
            LEFT JOIN chemical c                    ON dac.drug_id = c.drug_id
        ORDER BY dv.chrom, dv.pos
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


def get_haplotype_annotations(rsid):
    """
    Given an rsID, find all haplotypes it belongs to and return
    their drug annotations. This surfaces star-allele level annotations
    when browsing by rsID.
    """
    if not rsid:
        return []

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sql = """
    SELECT DISTINCT
        h.name      AS haplotype_name,
        h.gene      AS haplotype_gene,
        cda.annotation_id,
        cda.pmid,
        cda.phenotype,
        cda.significance,
        cda.direction,
        cda.notes,
        cda.sentence,
        c.drug_id,
        c.name      AS drug_name
    FROM haplotype h
    JOIN haplotype_identifier hi      ON h.haplotype_id = hi.haplotype_id
    JOIN variant_identifier vi        ON hi.identifier_id = vi.id
    JOIN variant_identifier_dbsnp vid ON vi.id = vid.id
    JOIN drug_annotation_variant dav  ON dav.identifier_id = vi.id
    JOIN clinpgx_drug_annotation cda  ON dav.annotation_entry = cda.id
    LEFT JOIN drug_annotation_chemical dac ON dac.annotation_entry = cda.id
    LEFT JOIN chemical c               ON dac.drug_id = c.drug_id
    WHERE vid.rsid = %s
    ORDER BY h.name, c.name;
    """

    cur.execute(sql, (rsid,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows