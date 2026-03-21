import time
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="789#",
        database="pharmacogenomic_data"
    )

# Test 1: How many rows in vcf_variant?
print("=== Test 1: Table size ===")
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM vcf_variant")
print(f"vcf_variant rows: {cur.fetchone()[0]:,}")
cur.close()
conn.close()

# Test 2: Check indexes on vcf_variant
print("\n=== Test 2: Indexes on vcf_variant ===")
conn = get_connection()
cur = conn.cursor()
cur.execute("""
    SELECT indexname, indexdef 
    FROM pg_indexes 
    WHERE tablename = 'vcf_variant'
""")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()

# Test 3: Time a single small batch query (100 variants)
print("\n=== Test 3: Time single batch of 100 fake variants ===")
conn = get_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)
t = time.time()
cur.execute("SELECT chrom, pos, ref, alt FROM vcf_variant LIMIT 100")
sample = cur.fetchall()
cur.close()
conn.close()

if sample:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    t = time.time()
    cur.execute("""
        CREATE TEMP TABLE tmp_test (chrom TEXT, pos INT, ref TEXT, alt TEXT)
    """)
    execute_values(cur, "INSERT INTO tmp_test VALUES %s",
        [(r['chrom'], r['pos'], r['ref'], r['alt']) for r in sample])
    cur.execute("""
        SELECT v.vcf_id, v.chrom, v.pos, v.ref, v.alt
        FROM tmp_test t
        JOIN vcf_variant v ON v.chrom=t.chrom AND v.pos=t.pos AND v.ref=t.ref AND v.alt=t.alt
    """)
    results = cur.fetchall()
    elapsed = time.time() - t
    print(f"100 variants via temp table: {elapsed:.3f}s → {len(results)} results")
    cur.close()
    conn.close()

# Test 4: Time connecting to DB
print("\n=== Test 4: Connection overhead ===")
t = time.time()
for i in range(10):
    conn = get_connection()
    conn.close()
elapsed = time.time() - t
print(f"10 connections: {elapsed:.3f}s ({elapsed/10*1000:.1f}ms each)")

# Test 5: EXPLAIN the main query
print("\n=== Test 5: Query plan ===")
conn = get_connection()
cur = conn.cursor()
cur.execute("""
    EXPLAIN (ANALYZE false, COSTS true)
    SELECT v.vcf_id, v.chrom, v.pos, v.ref, v.alt
    FROM vcf_variant v
    WHERE v.chrom = 'chr1' AND v.pos = 100000 AND v.ref = 'A' AND v.alt = 'G'
""")
for row in cur.fetchall():
    print(row[0])
cur.close()
conn.close()