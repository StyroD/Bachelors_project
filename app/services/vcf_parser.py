import gzip
from typing import List, Dict, Tuple

def parse_vcf_file(file_path: str, max_variants: int = 1000) -> Tuple[List[Dict], List[str]]:
    """
    Parse VCF file and extract variants.
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
                        variants.append({
                            'chrom': chrom,
                            'pos': int(pos),
                            'ref': ref.upper(),
                            'alt': alt_allele.upper(),
                            'rsid': variant_id,
                            'line_num': line_num
                        })
                        
                        variant_count += 1
                        
                        # Limit number of variants to prevent memory issues
                        if variant_count >= max_variants:
                            errors.append(f"Stopped at {max_variants} variants (file may contain more)")
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