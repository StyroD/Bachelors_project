from datetime import datetime
import io

def create_variant_html(variant_data, annotations):
    """
    Create an HTML report for a variant with all annotations.
    
    Args:
        variant_data: Dict with basic variant info (chrom, pos, ref, alt, rsid, vcf_id)
        annotations: List of annotation rows from database
    
    Returns:
        String containing the HTML
    """
    
    chrom = variant_data.get('chrom', '?')
    pos = variant_data.get('pos', '?')
    ref = variant_data.get('ref', '?')
    alt = variant_data.get('alt', '?')
    rsid = variant_data.get('rsid', 'Not assigned')
    vcf_id = variant_data.get('vcf_id', '?')
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Variant Report - {chrom}:{pos}</title>
    <style>
        :root {{
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --success-color: #27ae60;
            --danger-color: #e74c3c;
            --bg-light: #f8f9fa;
            --border-color: #dee2e6;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: var(--bg-light);
        }}
        
        .header {{
            background: var(--primary-color);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2em;
        }}
        
        .timestamp {{
            color: #ecf0f1;
            font-size: 0.9em;
        }}
        
        .section {{
            background: white;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .section-title {{
            color: var(--primary-color);
            font-size: 1.5em;
            margin-top: 0;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid var(--secondary-color);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        th {{
            background: var(--secondary-color);
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        tr:nth-child(even) {{
            background: var(--bg-light);
        }}
        
        .label {{
            font-weight: 600;
            color: var(--primary-color);
            width: 200px;
        }}
        
        .value {{
            font-family: 'Courier New', monospace;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        
        .badge-success {{
            background: #d4edda;
            color: #155724;
        }}
        
        .badge-warning {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .badge-danger {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .annotation-block {{
            background: var(--bg-light);
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 15px;
            border-left: 4px solid var(--danger-color);
        }}
        
        .annotation-title {{
            font-weight: 600;
            color: var(--primary-color);
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        
        .footer {{
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid var(--border-color);
        }}
        
        @media print {{
            body {{
                background: white;
            }}
            .section {{
                box-shadow: none;
                border: 1px solid var(--border-color);
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Variant Annotation Report</h1>
        <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    
    <div class="section">
        <h2 class="section-title">Basic Information</h2>
        <table>
            <tr>
                <td class="label">Chromosome</td>
                <td class="value">{chrom}</td>
            </tr>
            <tr>
                <td class="label">Position</td>
                <td class="value">{pos:,}</td>
            </tr>
            <tr>
                <td class="label">Reference Allele</td>
                <td class="value">{ref}</td>
            </tr>
            <tr>
                <td class="label">Alternate Allele</td>
                <td class="value">{alt}</td>
            </tr>
            <tr>
                <td class="label">rsID</td>
                <td class="value">{rsid}</td>
            </tr>
            <tr>
                <td class="label">VCF ID</td>
                <td class="value">{vcf_id}</td>
            </tr>
        </table>
    </div>
"""
    
    if not annotations:
        html += """
    <div class="section">
        <p>No annotations found for this variant.</p>
    </div>
"""
    else:
        # Functional Annotation
        gene_info = [a for a in annotations if a.get('gene')]
        if gene_info:
            first = gene_info[0]
            html += """
    <div class="section">
        <h2 class="section-title">Functional Annotation</h2>
        <table>
"""
            if first.get('gene'):
                html += f"""
            <tr>
                <td class="label">Gene</td>
                <td class="value">{first['gene']}</td>
            </tr>
"""
            if first.get('effect'):
                html += f"""
            <tr>
                <td class="label">Effect</td>
                <td class="value">{first['effect']}</td>
            </tr>
"""
            if first.get('assay_type'):
                html += f"""
            <tr>
                <td class="label">Assay Type</td>
                <td class="value">{first['assay_type']}</td>
            </tr>
"""
            if first.get('gene_product'):
                html += f"""
            <tr>
                <td class="label">Gene Product</td>
                <td class="value">{first['gene_product']}</td>
            </tr>
"""
            if first.get('functional_terms'):
                html += f"""
            <tr>
                <td class="label">Functional Terms</td>
                <td class="value">{first['functional_terms']}</td>
            </tr>
"""
            html += """
        </table>
    </div>
"""
        
        # Clinical Annotations
        clinical_annotations = [a for a in annotations if a.get('phenotype') or a.get('drug_name')]
        if clinical_annotations:
            html += """
    <div class="section">
        <h2 class="section-title">Clinical & Pharmacogenomic Annotations</h2>
"""
            for idx, ann in enumerate(clinical_annotations, 1):
                html += f"""
        <div class="annotation-block">
            <div class="annotation-title">Annotation {idx}</div>
            <table>
"""
                if ann.get('phenotype'):
                    html += f"""
                <tr>
                    <td class="label">Phenotype</td>
                    <td class="value">{ann['phenotype']}</td>
                </tr>
"""
                if ann.get('significance'):
                    badge_class = "badge-success" if "beneficial" in ann['significance'].lower() else "badge-warning"
                    html += f"""
                <tr>
                    <td class="label">Significance</td>
                    <td><span class="badge {badge_class}">{ann['significance']}</span></td>
                </tr>
"""
                if ann.get('direction'):
                    html += f"""
                <tr>
                    <td class="label">Direction</td>
                    <td class="value">{ann['direction']}</td>
                </tr>
"""
                if ann.get('drug_name'):
                    html += f"""
                <tr>
                    <td class="label">Drug</td>
                    <td class="value">{ann['drug_name']}</td>
                </tr>
"""
                if ann.get('notes'):
                    html += f"""
                <tr>
                    <td class="label">Notes</td>
                    <td>{ann['notes']}</td>
                </tr>
"""
                if ann.get('sentence'):
                    html += f"""
                <tr>
                    <td class="label">Description</td>
                    <td>{ann['sentence']}</td>
                </tr>
"""
                html += """
            </table>
        </div>
"""
            html += """
    </div>
"""
    
    html += """
    <div class="footer">
        <p><em>Generated by Pharmacogenomics Variant Browser</em></p>
    </div>
</body>
</html>
"""
    
    return html