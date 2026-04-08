#!/usr/bin/env python3
"""
Script for importing ClinPGx data into a PostgreSQL database
"""

import csv
import psycopg2
from psycopg2.extras import execute_values
import re
from typing import Set, List, Tuple, Optional
import sys


# Increase limit for CSV field size
csv.field_size_limit(sys.maxsize)

# Database connection - adjust as needed
DB_CONFIG = {
    'dbname': 'pharmacogenomics',
    'user': 'postgres',
    'password': 'your_password',
    'host': 'localhost',
    'port': 5432
}

# File paths
VARIANTS_FILE = '/home/istvan/bc/clinpgx_data/variants/variants.tsv'
CHEMICALS_FILE = '/home/istvan/bc/clinpgx_data/chemicals/chemicals.tsv'
VAR_FA_ANN_FILE = '/home/istvan/bc/clinpgx_data/variantAnnotations/var_fa_ann.tsv'
VAR_DRUG_ANN_FILE = '/home/istvan/bc/clinpgx_data/variantAnnotations/var_drug_ann.tsv'


def extract_gene_from_variant(variant_name: str) -> Optional[str]:
    """
    Extracts gene name from variant (e.g. CYP2C19*17 -> CYP2C19)
    """
    match = re.match(r'^([A-Z0-9]+)\*', variant_name)
    if match:
        return match.group(1)
    return None


def parse_variants(variant_string: str) -> List[str]:
    """
    Parses a comma-separated variant string
    """
    if not variant_string or variant_string.strip() == '':
        return []
    return [v.strip() for v in variant_string.split(',') if v.strip()]


def extract_rsids(synonyms: str) -> List[str]:
    """
    Extracts rs identifiers from synonyms
    """
    if not synonyms:
        return []
    rsids = []
    for syn in synonyms.split(','):
        syn = syn.strip()
        if syn.startswith('rs') and syn[2:].isdigit():
            rsids.append(syn)
    return rsids


def determine_variant_type(variant_name: str) -> str:
    """
    Determines variant type
    """
    if variant_name.startswith('rs'):
        return 'rsid'
    elif '*' in variant_name:
        return 'star_allele'
    elif '/' in variant_name:
        return 'diplotype'
    else:
        return 'unknown'


def import_chemicals(conn, cursor):
    """
    Imports chemicals/drugs
    """
    print("Importing chemicals...")
    
    with open(CHEMICALS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        chemicals = []
        
        for row in reader:
            drug_id = row['PharmGKB Accession Id']
            name = row['Name']
            description = row.get('Type', '')
            
            chemicals.append((drug_id, name, description))
    
    # Bulk insert
    execute_values(
        cursor,
        "INSERT INTO chemical (drug_id, name, description) VALUES %s ON CONFLICT (drug_id) DO NOTHING",
        chemicals
    )
    
    conn.commit()
    print(f"Imported {len(chemicals)} chemicals")


def import_variants(conn, cursor):
    """
    Imports variants and creates variant_identifier records
    """
    print("Importing variants...")
    
    identifiers = []
    identifier_dbsnp_links = []
    rsids_seen = set()
    
    with open(VARIANTS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            variant_id = row['Variant ID']
            variant_name = row['Variant Name']
            gene_symbols = row.get('Gene Symbols', '')
            synonyms = row.get('Synonyms', '')
            
            # Main variant
            if variant_name:
                variant_type = determine_variant_type(variant_name)
                gene = gene_symbols.split(',')[0].strip() if gene_symbols else None
                
                identifiers.append((variant_name, variant_type, gene))
                
                # Add rsid links
                rsids = extract_rsids(synonyms)
                for rsid in rsids:
                    if rsid not in rsids_seen:
                        rsids_seen.add(rsid)
                        identifier_dbsnp_links.append((variant_name, rsid))
    
    # Insert identifiers
    execute_values(
        cursor,
        "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
        identifiers
    )
    
    print(f"Imported {len(identifiers)} variant identifiers")
    
    # rsid links require dbsnp_variant records first
    # Those will be created later, so we only prepare data here
    conn.commit()
    
    return identifier_dbsnp_links


def import_functional_annotations(conn, cursor):
    """
    Imports functional annotations
    """
    print("Importing functional annotations...")
    
    annotations = []
    variants_to_add = set()
    
    with open(VAR_FA_ANN_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            variant_string = row.get('Variant/Haplotypes', '')
            variants = parse_variants(variant_string)
            gene = row.get('Gene', '')
            assay_type = row.get('Assay type', '')
            functional_terms = row.get('Functional terms', '')
            gene_product = row.get('Gene/gene product', '')
            sentence = row.get('Sentence', '')
            
            for variant in variants:
                variants_to_add.add((variant, determine_variant_type(variant), gene if gene else extract_gene_from_variant(variant)))
                
                annotations.append((
                    variant,
                    sentence,
                    assay_type,
                    gene_product,
                    functional_terms
                ))
    
    # Add new variants
    if variants_to_add:
        execute_values(
            cursor,
            "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
            list(variants_to_add)
        )
    
    # Insert annotations
    execute_values(
        cursor,
        """INSERT INTO functional_annotation 
           (identifier_id, effect, assay_type, gene_product, functional_terms) 
           VALUES %s""",
        annotations
    )
    
    conn.commit()
    print(f"Imported {len(annotations)} functional annotations")


def import_drug_annotations(conn, cursor):
    """
    Imports drug annotations
    """
    print("Importing drug annotations...")
    
    annotations = []
    drug_links = []
    variant_links = []
    variants_to_add = set()
    
    with open(VAR_DRUG_ANN_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            annotation_id = row.get('Variant Annotation ID', '')
            variant_string = row.get('Variant/Haplotypes', '')
            gene = row.get('Gene', '')
            drug_string = row.get('Drug(s)', '')
            phenotype = row.get('Phenotype Category', '')
            significance = row.get('Significance', '')
            direction = row.get('Direction of effect', '')
            notes = row.get('Notes', '')
            sentence = row.get('Sentence', '')
            
            variants = parse_variants(variant_string)
            drugs = parse_variants(drug_string)
            
            # Create annotation
            cursor.execute(
                """INSERT INTO clinpgx_drug_annotation 
                   (annotation_id, phenotype, significance, direction, notes, sentence)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (annotation_id, phenotype, significance, direction, notes, sentence)
            )
            
            db_annotation_id = cursor.fetchone()[0]
            
            # Add variants
            for variant in variants:
                variant_type = determine_variant_type(variant)
                variant_gene = gene if gene else extract_gene_from_variant(variant)
                variants_to_add.add((variant, variant_type, variant_gene))
                variant_links.append((db_annotation_id, variant))
            
            # Add drugs (lookup by name in chemical table)
            for drug_name in drugs:
                cursor.execute(
                    "SELECT drug_id FROM chemical WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                    (drug_name,)
                )
                result = cursor.fetchone()
                if result:
                    drug_links.append((db_annotation_id, result[0]))
    
    # Add new variants
    if variants_to_add:
        execute_values(
            cursor,
            "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
            list(variants_to_add)
        )
    
    # Insert links
    if variant_links:
        execute_values(
            cursor,
            """INSERT INTO drug_annotation_variant (annotation_entry, identifier_id) 
               VALUES %s ON CONFLICT DO NOTHING""",
            variant_links
        )
    
    if drug_links:
        execute_values(
            cursor,
            """INSERT INTO drug_annotation_chemical (annotation_entry, drug_id) 
               VALUES %s ON CONFLICT DO NOTHING""",
            drug_links
        )
    
    conn.commit()
    print(f"Imported {len(annotations)} drug annotations")


def download_and_extract(url) -> dict[str, bytes]:
    """Download a zip and return {filename: content} for all TSV files inside."""
    print(f"  Downloading {url}...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    
    tsv_files = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for name in z.namelist():
            if name.endswith(".tsv"):
                tsv_files[name] = z.read(name)
    return tsv_files

def main():
    """
    Main function
    """
    print("Starting ClinPGx data import...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Import in correct order due to foreign keys
        import_chemicals(conn, cursor)
        import_variants(conn, cursor)
        import_functional_annotations(conn, cursor)
        import_drug_annotations(conn, cursor)
        
        cursor.close()
        conn.close()
        
        print("\n✓ Import completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error during import: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()