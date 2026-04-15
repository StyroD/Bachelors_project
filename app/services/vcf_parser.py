import gzip
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Iterator


def make_pypgx_variant_key(chrom: str, pos: int, ref: str, alt: str) -> str:
    """Normalize a VCF variant into PyPGx coordinate format."""
    chrom = chrom.lstrip('chr')
    return f"{chrom}-{pos}-{ref}-{alt}"


def _load_pypgx():
    try:
        import pypgx
        return pypgx
    except ImportError as e:
        raise ImportError(
            "pypgx is required for rsid-to-haplotype mapping. "
            "Install it with 'pip install pypgx' and make sure the bundle files are available."
        ) from e


def parse_vcf_file_stream(file_path: str, batch_size: int = 5000) -> Iterator[Tuple[List[Dict], List[str]]]:
    """
    Parse VCF file and yield variants in batches.
    
    Yields: (batch of variant dicts, list of errors for this batch)
    """
    try:
        # Detect if file is gzipped
        if file_path.endswith('.gz'):
            file_handle = gzip.open(file_path, 'rt')
        else:
            file_handle = open(file_path, 'r')
        
        line_num = 0
        current_batch = []
        batch_errors = []
        
        with file_handle as f:
            for line in f:
                line_num += 1
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Skip header lines
                if line.startswith('#'):
                    continue
                
                # Parse variant line
                try:
                    parts = line.split('\t')
                    if len(parts) < 5:
                        batch_errors.append(f"Line {line_num}: Not enough columns")
                        continue
                    
                    chrom = parts[0]
                    pos = parts[1]
                    variant_id = parts[2] if parts[2] != '.' else None
                    ref = parts[3]
                    alt = parts[4]
                    
                    # Normalize chromosome (add chr prefix if needed)
                    if not chrom.startswith('chr'):
                        chrom = f"chr{chrom}"
                    
                    # Handle multiple alternate alleles (comma-separated)
                    alt_alleles = alt.split(',')
                    
                    for alt_allele in alt_alleles:
                        variant_key = make_pypgx_variant_key(chrom, int(pos), ref.upper(), alt_allele.upper())
                        current_batch.append({
                            'chrom': chrom,
                            'pos': int(pos),
                            'ref': ref.upper(),
                            'alt': alt_allele.upper(),
                            'rsid': variant_id,
                            'variant_key': variant_key,
                            'line_num': line_num
                        })
                        
                        # Yield batch when it reaches batch_size
                        if len(current_batch) >= batch_size:
                            yield current_batch, batch_errors
                            current_batch = []
                            batch_errors = []
                
                except Exception as e:
                    batch_errors.append(f"Line {line_num}: {str(e)}")
                    continue
            
            # Yield remaining variants
            if current_batch:
                yield current_batch, batch_errors
    
    except Exception as e:
        yield [], [f"Failed to read file: {str(e)}"]


def parse_vcf_file(file_path: str, max_variants: int = -1) -> Tuple[List[Dict], List[str]]:
    """
    Parse VCF file and extract variants (kept for backward compatibility).
    Use parse_vcf_file_stream() for large files.
    
    Args:
        file_path: Path to VCF file
        max_variants: Maximum number of variants to parse. -1 = unlimited
    
    Returns: (list of variant dicts, list of errors)
    """
    variants = []
    errors = []
    
    try:
        # Detect if file is gzipped
        if file_path.endswith('.gz'):
            file_handle = gzip.open(file_path, 'rt')
        else:
            file_handle = open(file_path, 'r')
        
        line_num = 0
        variant_count = 0
        unlimited = (max_variants == -1)
        
        with file_handle as f:
            for line in f:
                line_num += 1
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Skip header lines
                if line.startswith('#'):
                    continue
                
                # Parse variant line
                try:
                    parts = line.split('\t')
                    if len(parts) < 5:
                        errors.append(f"Line {line_num}: Not enough columns")
                        continue
                    
                    chrom = parts[0]
                    pos = parts[1]
                    variant_id = parts[2] if parts[2] != '.' else None
                    ref = parts[3]
                    alt = parts[4]
                    
                    # Normalize chromosome (add chr prefix if needed)
                    if not chrom.startswith('chr'):
                        chrom = f"chr{chrom}"
                    
                    # Handle multiple alternate alleles (comma-separated)
                    alt_alleles = alt.split(',')
                    
                    for alt_allele in alt_alleles:
                        variant_key = make_pypgx_variant_key(chrom, int(pos), ref.upper(), alt_allele.upper())
                        variants.append({
                            'chrom': chrom,
                            'pos': int(pos),
                            'ref': ref.upper(),
                            'alt': alt_allele.upper(),
                            'rsid': variant_id,
                            'variant_key': variant_key,
                            'line_num': line_num
                        })
                        
                        variant_count += 1
                        
                        # Check limit (only if not unlimited)
                        if not unlimited and max_variants > 0 and variant_count >= max_variants:
                            errors.append(f"Stopped at {max_variants} variants (file contains more)")
                            return variants, errors
                
                except Exception as e:
                    errors.append(f"Line {line_num}: {str(e)}")
                    continue
        
        return variants, errors
    
    except Exception as e:
        errors.append(f"Failed to read file: {str(e)}")
        return [], errors


def format_vcf_summary(variants: List[Dict]) -> Dict:
    """
    Generate summary statistics for parsed VCF variants.
    """
    if not variants:
        return {
            'total_variants': 0,
            'chromosomes': [],
            'has_rsids': 0
        }
    
    chromosomes = set(v['chrom'] for v in variants)
    has_rsids = sum(1 for v in variants if v.get('rsid'))
    
    return {
        'total_variants': len(variants),
        'chromosomes': sorted(list(chromosomes)),
        'has_rsids': has_rsids,
        'chrom_counts': {chrom: sum(1 for v in variants if v['chrom'] == chrom) 
                        for chrom in chromosomes}
    }


def load_clinpgx_star_allele_aliases(variants_tsv_path: str) -> Dict[str, List[str]]:
    """Load rsid -> star allele alias mapping from ClinPGx variants.tsv."""
    rsid_re = re.compile(r'\brs\d+\b', re.IGNORECASE)
    star_re = re.compile(r'\b[A-Za-z0-9_]+\*[A-Za-z0-9:._-]+\b')
    alias_map: Dict[str, set] = defaultdict(set)

    with open(variants_tsv_path, 'r', encoding='utf-8', errors='replace') as f:
        header_line = f.readline()
        header_columns = header_line.rstrip('\n').split('\t')
        if len(header_columns) < 11:
            raise ValueError(f"Unexpected ClinPGx variants.tsv header: {header_columns}")

        for raw_line in f:
            line = raw_line.rstrip('\n')
            if not line:
                continue

            columns = line.split('\t')
            if len(columns) < 11:
                continue

            variant_name = columns[1]
            synonyms = columns[10]
            rsids = set(rsid_re.findall(variant_name or '')) | set(rsid_re.findall(synonyms or ''))
            if not rsids:
                continue

            stars = set(star_re.findall(variant_name or '')) | set(star_re.findall(synonyms or ''))
            if not stars:
                continue

            for rsid in rsids:
                alias_map[rsid].update(stars)

    return {rsid: sorted(stars) for rsid, stars in alias_map.items()}


def map_rsids_to_clinpgx_star_alleles(
    variants: List[Dict],
    variants_tsv_path: str
) -> Dict[str, List[str]]:
    """Return ClinPGx star allele aliases for rsids seen in the parsed VCF."""
    alias_map = load_clinpgx_star_allele_aliases(variants_tsv_path)
    result: Dict[str, List[str]] = {}

    for variant in variants:
        rsid = variant.get('rsid')
        if not rsid:
            continue
        result[rsid] = alias_map.get(rsid, [])

    return result


def get_pypgx_allele_variants(gene: str, alleles: List[str], assembly: str = 'GRCh37') -> Dict[str, List[str]]:
    """Return PyPGx variant definitions for each allele."""
    pypgx = _load_pypgx()
    allele_variants: Dict[str, List[str]] = {}

    for allele in alleles:
        allele_variants[allele] = pypgx.list_variants(gene, alleles=[allele], assembly=assembly)

    return allele_variants


def map_rsids_to_pypgx_alleles(
    variants: List[Dict],
    gene: str,
    alleles: List[str],
    assembly: str = 'GRCh37'
) -> Dict[str, List[str]]:
    """Map VCF rsIDs to PyPGx star alleles using allele variant definitions."""
    allele_variants = get_pypgx_allele_variants(gene, alleles, assembly)
    variant_index = {v['variant_key']: v for v in variants if v.get('variant_key')}
    allele_rsid_map: Dict[str, List[str]] = {}

    for allele, variant_keys in allele_variants.items():
        allele_rsid_map[allele] = [
            variant_index[key]['rsid']
            for key in variant_keys
            if key in variant_index and variant_index[key].get('rsid')
        ]

    return allele_rsid_map
