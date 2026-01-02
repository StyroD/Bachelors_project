import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess

def get_connection():
    """Return a new PostgreSQL connection."""
    if not ensure_db_running():
        raise RuntimeError("PostgreSQL is not running. Please start the service.")
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="farkas",
        database="pharmacogenomic_data"
    )

def ensure_db_running():
    """Check if PostgreSQL is running; if not, try to start it."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="farkas",
            database="pharmacogenomic_data"
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        try:
            subprocess.run(
                ["sudo", "systemctl", "start", "postgresql"],
                check=True
            )
            return True
        except Exception:
            return False

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
    """
    Search for multiple variants at once.
    variants: list of dicts with keys: chrom, pos, ref, alt
    Returns: list of dicts with variant info + annotations
    """
    if not variants:
        return []
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    results = []
    
    # Search in batches of 100 to avoid huge queries
    batch_size = 100
    for i in range(0, len(variants), batch_size):
        batch = variants[i:i+batch_size]
        
        # Build WHERE clause for batch
        conditions = []
        params = []
        
        for v in batch:
            conditions.append("(v.chrom = %s AND v.pos = %s AND v.ref = %s AND v.alt = %s)")
            params.extend([v['chrom'], v['pos'], v['ref'], v['alt']])
        
        where_clause = " OR ".join(conditions)
        
        sql = f"""
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
        WHERE {where_clause}
        ORDER BY v.chrom, v.pos;
        """
        
        cur.execute(sql, params)
        batch_results = cur.fetchall()
        results.extend(batch_results)
    
    cur.close()
    conn.close()
    
    return results