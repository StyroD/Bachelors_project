"""
Script for downloading dbSNP data and populating the database
"""

import requests
import time
import json
import psycopg2
from psycopg2.extras import execute_values
import sys
from typing import List, Dict, Optional, Tuple

# Database connection
DB_CONFIG = {
    'dbname': 'pharmacogenomic_data',
    'user': 'postgres',
    'password': 'farkas',
    'host': 'localhost',
    'port': 5432
}

def fetch_dbsnp_rsid(rsid: str) -> Optional[Dict]:
    """
    Fetch SNP information from Clinical Tables API using rsID
    """
    # Remove 'rs' prefix if present
    rsid_clean = rsid.replace('rs', '').strip()
    
    # Clinical Tables API v3 - fetch without df to get all data
    url = f"https://clinicaltables.nlm.nih.gov/api/snps/v3/search"
    
    params = {
        'terms': rsid,
        'maxList': 1  # Only return exact matches
    }
    
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"  Error {r.status_code} for {rsid}")
            return None
        
        data = r.json()
        
        # API returns: [count, [rsids], null, [data_rows]]
        # Without df, data_rows should contain full information
        if len(data) < 4 or not data[3]:
            print(f"  No data returned for {rsid}")
            return None
        
        # Check if we got the exact rsID we searched for
        if len(data) >= 2 and data[1]:
            found_rsids = data[1]
            if rsid not in found_rsids:
                print(f"  Searched {rsid} but got different rsIDs: {found_rsids}")
        
        # Return both the data and the original rsid
        return {'data': data, 'rsid': rsid}
        
    except Exception as e:
        print(f"  Exception while fetching {rsid}: {e}")
        return None


def extract_variants_from_dbsnp(rsid: str, response: Dict) -> List[Tuple]:
    """
    Extract variant information from Clinical Tables API response
    Returns list of tuples: (rsid, chrom, pos, ref, alt)
    
    Handles multiple alternate alleles by creating separate entries for each
    """
    variants = []
    
    try:
        # Extract data from response
        data = response.get('data', response)
        original_rsid = response.get('rsid', rsid)
        
        # Data structure: [count, [rsids], null, [data_rows]]
        # Full data rows contain: [rsid, Chromosome, Position, AlleleString, Gene]
        
        if len(data) < 4 or not data[3]:
            return variants
        
        for row in data[3]:
            if not row or len(row) < 4:
                print(f"  Row too short: {row}")
                continue
            
            # Correct format: [rsid, Chromosome, Position, AlleleString, Gene]
            returned_rsid = row[0] if row[0] else original_rsid
            chromosome = row[1]
            position = row[2]
            allele_string = row[3]
            # row[4] is gene name (optional)
            
            # Parse allele string
            if not allele_string or '/' not in allele_string:
                print(f"  Invalid/empty allele string: '{allele_string}' for {returned_rsid}")
                continue
            
            # Handle multiple alternate alleles separated by comma
            # Example: "T/A, T/C" means ref=T with alts A and C
            allele_groups = allele_string.split(', ')
            
            for allele_group in allele_groups:
                alleles = allele_group.split('/')
                if len(alleles) < 2:
                    print(f"  Not enough alleles in group: {allele_group}")
                    continue
                
                # First allele is reference, rest are alternates
                ref = alleles[0]
                alts = alleles[1:]
                
                # Skip if ref is empty
                if not ref:
                    print(f"  Empty reference allele for {returned_rsid}")
                    continue
                
                # Normalize chromosome (add 'chr' prefix if not present)
                if not chromosome:
                    print(f"  Empty chromosome for {returned_rsid}")
                    continue
                    
                if str(chromosome).isdigit() or chromosome in ['X', 'Y', 'M', 'MT']:
                    chrom = f"chr{chromosome}"
                elif chromosome.startswith('chr'):
                    chrom = chromosome
                else:
                    chrom = f"chr{chromosome}"
                
                # Convert position to integer
                try:
                    pos_int = int(position)
                except (ValueError, TypeError):
                    print(f"  Invalid position: '{position}' for {returned_rsid}")
                    continue
                
                # Create separate variant entry for each alternate allele
                for alt in alts:
                    if alt and alt != ref:  # Skip if alt is empty or same as ref
                        variants.append((
                            original_rsid,
                            chrom,
                            pos_int,
                            ref.upper(),
                            alt.upper()
                        ))
        
        if not variants:
            print(f"  No valid variants extracted. Sample row: {data[3][0] if data[3] else 'none'}")
    
    except Exception as e:
        print(f"  Error parsing {rsid}: {e}")
        import traceback
        traceback.print_exc()
    
    return variants


def get_rsids_from_db(cursor) -> List[str]:
    """
    Get all rsIDs from variant_identifier table
    """
    cursor.execute("""
        SELECT DISTINCT id 
        FROM variant_identifier 
        WHERE type = 'rsid' AND id LIKE 'rs%'
        ORDER BY id
    """)
    
    rsids = [row[0] for row in cursor.fetchall()]
    return rsids


def save_to_database(conn, cursor, variants: List[Tuple]):
    """
    Save variants to dbsnp_variant and vcf_variant tables
    Each variant (rsid, chrom, pos, ref, alt) gets its own row
    """
    if not variants:
        return 0
    
    # Insert into dbsnp_variant - one row per ref/alt combination
    # Uses composite primary key (rsid, chrom, pos, ref, alt)
    execute_values(
        cursor,
        """INSERT INTO dbsnp_variant (rsid, chrom, pos, ref, alt) 
           VALUES %s 
           ON CONFLICT (rsid, chrom, pos, ref, alt) DO NOTHING""",
        variants
    )
    
    rows_inserted = cursor.rowcount
    
    # Insert into vcf_variant (without rsid, just as variant records)
    # Assuming vcf_variant has a unique constraint on (chrom, pos, ref, alt)
    vcf_data = [(v[1], v[2], v[3], v[4], v[0]) for v in variants]
    
    try:
        execute_values(
            cursor,
            """INSERT INTO vcf_variant (chrom, pos, ref, alt, rsid) 
               VALUES %s
               ON CONFLICT (chrom, pos, ref, alt) DO UPDATE 
               SET rsid = EXCLUDED.rsid""",
            vcf_data
        )
    except Exception as e:
        # If vcf_variant doesn't have the right constraints, just insert
        print(f"  Note: vcf_variant insert issue (may already exist): {e}")
        conn.rollback()
        # Try without ON CONFLICT
        try:
            execute_values(
                cursor,
                """INSERT INTO vcf_variant (chrom, pos, ref, alt, rsid) 
                   VALUES %s""",
                vcf_data
            )
        except:
            pass  # Duplicates are okay
    
    conn.commit()
    return rows_inserted


def update_variant_identifier_dbsnp_links(conn, cursor):
    """
    Update variant_identifier_dbsnp table
    Link variant_identifier records with dbsnp_variant via rsid
    """
    print("\nUpdating variant_identifier_dbsnp links...")
    
    cursor.execute("""
        INSERT INTO variant_identifier_dbsnp (id, rsid)
        SELECT DISTINCT vi.id, dv.rsid
        FROM variant_identifier vi
        JOIN dbsnp_variant dv ON vi.id = dv.rsid
        WHERE vi.type = 'rsid'
        ON CONFLICT DO NOTHING
    """)
    
    rows_inserted = cursor.rowcount
    conn.commit()
    print(f"  Created {rows_inserted} links in variant_identifier_dbsnp")


def main():
    """
    Main function
    """
    print("Starting dbSNP data download...\n")
    print("Using Clinical Tables API v3")
    print("Each rsID will create separate entries for each alternate allele\n")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get rsIDs from database
        print("Fetching rsIDs from database...")
        rsids = get_rsids_from_db(cursor)
        print(f"Found {len(rsids)} rsIDs to process\n")
        
        if not rsids:
            print("No rsIDs to process!")
            return
        
        # Process each rsID
        total_variants = 0
        failed_rsids = []
        multi_alt_count = 0
        first_response_printed = False
        
        for i, rsid in enumerate(rsids, 1):
            print(f"[{i}/{len(rsids)}] Processing {rsid}...")
            
            # Download data
            response = fetch_dbsnp_rsid(rsid)
            
            if response is None:
                failed_rsids.append(rsid)
                time.sleep(0.33)  # Rate limiting
                continue
            
            # Debug: Print first successful response to understand structure
            if not first_response_printed and response:
                print("\n=== DEBUG: First API Response Structure ===")
                print(json.dumps(response.get('data', response), indent=2))
                print("===========================================\n")
                first_response_printed = True
            
            # Extract variants (will create multiple rows for multiple alts)
            variants = extract_variants_from_dbsnp(rsid, response)
            
            if variants:
                # Track multi-allelic variants
                if len(variants) > 1:
                    multi_alt_count += 1
                    print(f"  Multi-allelic: {len(variants)} alternate alleles")
                
                # Save to database
                count = save_to_database(conn, cursor, variants)
                total_variants += count
                print(f"  Saved {count} variant(s)")
                
                # Show what was saved for multi-allelic
                if len(variants) > 1:
                    for v in variants:
                        print(f"    - {v[1]}:{v[2]} {v[3]}>{v[4]}")
            else:
                print(f"  No variants extracted")
            
            # Rate limiting: ~3 requests per second
            time.sleep(0.33)
            
            # Print progress every 50 rsIDs
            if i % 50 == 0:
                print(f"\n--- Progress: {i}/{len(rsids)} rsIDs processed ---")
                print(f"    Total variants so far: {total_variants}")
                print(f"    Multi-allelic rsIDs: {multi_alt_count}\n")
        
        # Update links
        update_variant_identifier_dbsnp_links(conn, cursor)
        
        # Final statistics
        print("\n" + "="*60)
        print("SUMMARY:")
        print(f"  Total rsIDs: {len(rsids)}")
        print(f"  Successfully processed: {len(rsids) - len(failed_rsids)}")
        print(f"  Failed: {len(failed_rsids)}")
        print(f"  Total variant entries: {total_variants}")
        print(f"  Multi-allelic rsIDs: {multi_alt_count}")
        print(f"  Average alts per rsID: {total_variants / max(len(rsids) - len(failed_rsids), 1):.2f}")
        print("="*60)
        
        if failed_rsids:
            print("\nFailed rsIDs:")
            for rsid in failed_rsids[:10]:  # Show first 10
                print(f"  - {rsid}")
            if len(failed_rsids) > 10:
                print(f"  ... and {len(failed_rsids) - 10} more")
        
        cursor.close()
        conn.close()
        
        print("\nImport completed!")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()