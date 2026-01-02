#!/usr/bin/env python3
"""
Script for importing ClinPGx data into a PostgreSQL database.
"""

import csv
import psycopg2
from psycopg2.extras import execute_values
import re
from typing import Set, List, Tuple, Optional
import sys

# Increase CSV field size limit for large annotation strings
csv.field_size_limit(sys.maxsize)

# Database configuration
DB_CONFIG = {
    'dbname': 'pharmacogenomic_data',
    'user': 'postgres',
    'password': 'farkas',
    'host': 'localhost',
    'port': 5432
}

# Paths for input files
VARIANTS_FILE = '/home/istvan/bc/clinpgx_data/variants/variants.tsv'
CHEMICALS_FILE = '/home/istvan/bc/clinpgx_data/chemicals/chemicals.tsv'
VAR_FA_ANN_FILE = '/home/istvan/bc/clinpgx_data/variantAnnotations/var_fa_ann.tsv'
VAR_DRUG_ANN_FILE = '/home/istvan/bc/clinpgx_data/variantAnnotations/var_drug_ann.tsv'


def extract_gene_from_variant(variant_name: str) -> Optional[str]:
    """
    Extracts the gene name from a variant (e.g., CYP2C19*17 -> CYP2C19).
    """
    match = re.match(r'^([A-Z0-9]+)\*', variant_name)
    if match:
        return match.group(1)
    return None


def parse_variants(variant_string: str) -> List[str]:
    """
    Parses a string of variants separated by commas.
    """
    if not variant_string or variant_string.strip() == '':
        return []
    return [v.strip() for v in variant_string.split(',') if v.strip()]


def extract_rsids(synonyms: str) -> List[str]:
    """
    Extracts rs identifiers from synonyms string.
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
    Determines the category of the variant based on naming convention.
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
    Imports chemical/drug data into the database.
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
    
    # Bulk insert with conflict handling
    execute_values(
        cursor,
        "INSERT INTO chemical (drug_id, name, description) VALUES %s ON CONFLICT (drug_id) DO NOTHING",
        chemicals
    )
    
    conn.commit()
    print(f"Successfully imported {len(chemicals)} chemicals.")


def import_variants(conn, cursor):
    """
    Imports variant identifiers and prepares links.
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
            
            if variant_name:
                variant_type = determine_variant_type(variant_name)
                gene = gene_symbols.split(',')[0].strip() if gene_symbols else None
                
                identifiers.append((variant_name, variant_type, gene))
                
                # Extract rsIDs from synonyms to create cross-references
                rsids = extract_rsids(synonyms)
                for rsid in rsids:
                    if rsid not in rsids_seen:
                        rsids_seen.add(rsid)
                        identifier_dbsnp_links.append((variant_name, rsid))
    
    # Bulk insert identifiers
    execute_values(
        cursor,
        "INSERT INTO variant_identifier (id, type, gene) VALUES %s ON CONFLICT (id) DO NOTHING",
        identifiers
    )
    
    print(f"Successfully imported {len(identifiers)} variant identifiers.")
    conn.commit()
    
    return identifier_dbsnp_links


def import_functional_annotations(conn, cursor):
    """
    Imports functional annotations for variants.
    """
    print("Importing functional annotations...")
    
    annotations = []
    variants_to_add = set()
    
    with open(VAR_FA_ANN_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            variant_string = row.get('Variant/Haplotypes', '')
            variants = parse