import re

VCF_PATTERN = re.compile(
    r"^(chr)?(?P<chrom>\w+)[\s:]+(?P<pos>\d+)[\s]+(?P<ref>[ACGTN]+)[/\s>]+(?P<alt>[ACGTN]+)$",
    re.IGNORECASE
)
VCF_INLINE_PATTERN = re.compile(
    r"^(chr)?(?P<chrom>\w+):(?P<pos>\d+)(?P<ref>[ACGTN]+)[>/](?P<alt>[ACGTN]+)$",
    re.IGNORECASE
)

def parse_query(q: str):
    """Parse user query and return dict with search parameters."""
    q = q.strip()
    if not q:
        return {"query": ""}

    # RSID lookup
    if q.lower().startswith("rs"):
        return {"rsid": q}

    # VCF-style with chromosome
    m1 = VCF_PATTERN.match(q)
    if m1:
        g = m1.groupdict()
        return {
            "chrom": g["chrom"],
            "pos": int(g["pos"]),
            "ref": g["ref"].upper(),
            "alt": g["alt"].upper()
        }

    m2 = VCF_INLINE_PATTERN.match(q)
    if m2:
        g = m2.groupdict()
        return {
            "chrom": g["chrom"],
            "pos": int(g["pos"]),
            "ref": g["ref"].upper(),
            "alt": g["alt"].upper()
        }

    # Formats like "21967916 A>G" or "21967916 A G"
    parts = q.replace(",", " ").replace(">", " ").split()
    if len(parts) == 3:
        try:
            return {
                "pos": int(parts[0]),
                "ref": parts[1].upper(),
                "alt": parts[2].upper()
            }
        except ValueError:
            pass

    # Fallback to fulltext search
    return {"query": q}

def pretty_variant(rec):
    """Format a variant record for display."""
    rs = rec.get("rsid") or "—"
    chrom = rec.get("chrom", "?")
    pos = rec.get("pos", "?")
    ref = rec.get("ref", "?")
    alt = rec.get("alt", "?")
    return f"{chrom}:{pos} {ref}>{alt} ({rs})"

def format_autocomplete_option(rec):
    """Format variant for autocomplete dropdown."""
    rs = rec.get("rsid", "")
    chrom = rec.get("chrom", "")
    pos = rec.get("pos", "")
    ref = rec.get("ref", "")
    alt = rec.get("alt", "")
    
    if rs and rs != "":
        return f"{rs} - {chrom}:{pos} {ref}>{alt}"
    return f"{chrom}:{pos} {ref}>{alt}"