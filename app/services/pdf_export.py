from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io

def create_variant_pdf(variant_data, annotations):
    """
    Create a PDF report for a variant with all annotations.
    
    Args:
        variant_data: Dict with basic variant info (chrom, pos, ref, alt, rsid, vcf_id)
        annotations: List of annotation rows from database
    
    Returns:
        BytesIO buffer containing the PDF
    """
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18, title="Variant Annotation Report")
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title
    title = Paragraph("Variant Annotation Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Timestamp
    timestamp = Paragraph(
        f"<para align=center>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</para>",
        styles['Normal']
    )
    elements.append(timestamp)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Basic Information", heading_style))
    # Basic variant info table
    basic_data = [
        ['Field', 'Value'],
        ['Chromosome', str(variant_data.get('chrom', '?'))],
        ['Position', f"{variant_data.get('pos', '?'):,}"],
        ['Reference Allele', variant_data.get('ref', '?')],
        ['Alternate Allele', variant_data.get('alt', '?')],
        ['rsID', variant_data.get('rsid', 'Not assigned')],
        ['VCF ID', str(variant_data.get('vcf_id', '?'))],
    ]
    
    basic_table = Table(basic_data, colWidths=[2*inch, 4*inch])
    basic_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#fdfdfd")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))
    
    elements.append(basic_table)
    elements.append(Spacer(1, 20))
    
    if not annotations:
        elements.append(Paragraph("No annotations found for this variant.", styles['Normal']))
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    # gene-based annotations
    gene_info = [a for a in annotations if a.get('gene')]
    if gene_info:
        elements.append(Paragraph("Functional Annotation", heading_style))
        
        first = gene_info[0]
        func_data = [['Field', 'Value']]
        
        if first.get('gene'):
            func_data.append(['Gene', first['gene']])
        if first.get('effect'):
            func_data.append(['Effect', first['effect']])
        if first.get('assay_type'):
            func_data.append(['Assay Type', first['assay_type']])
        if first.get('gene_product'):
            func_data.append(['Gene Product', first['gene_product']])
        if first.get('functional_terms'):
            func_data.append(['Functional Terms', first['functional_terms']])
        
        if len(func_data) > 1:
            func_table = Table(func_data, colWidths=[2*inch, 4*inch])
            func_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f8f8f8")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ]))
            elements.append(func_table)
            elements.append(Spacer(1, 20))
    
    # Clinical  and drug annotations 
    clinical_annotations = [a for a in annotations if a.get('phenotype') or a.get('drug_name')]
    
    if clinical_annotations:
        elements.append(Paragraph("Clinical & Pharmacogenomic Annotations", heading_style))
        
        for idx, ann in enumerate(clinical_annotations, 1):
            elements.append(Paragraph(f"<b>Annotation {idx}</b>", styles['Heading3']))
            
            clinical_data = [['Field', 'Value']]
            
            if ann.get('phenotype'):
                clinical_data.append(['Phenotype', ann['phenotype']])
            if ann.get('significance'):
                clinical_data.append(['Significance', ann['significance']])
            if ann.get('direction'):
                clinical_data.append(['Direction', ann['direction']])
            if ann.get('drug_name'):
                clinical_data.append(['Drug', ann['drug_name']])
            if ann.get('notes'):
                # Wrap long text
                notes = Paragraph(ann['notes'], styles['Normal'])
                clinical_data.append(['Notes', notes])
            if ann.get('sentence'):
                sentence = Paragraph(ann['sentence'], styles['Normal'])
                clinical_data.append(['Description', sentence])
            
            if len(clinical_data) > 1:
                clinical_table = Table(clinical_data, colWidths=[2*inch, 4*inch])
                clinical_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#ffffff")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#ffffff")),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ]))
                elements.append(clinical_table)
                elements.append(Spacer(1, 12))
    
    # footer
    elements.append(Spacer(1, 30))
    footer = Paragraph(
        "<para align=center><i>Generated by Pharmacogenomics Variant Browser</i></para>",
        styles['Normal']
    )
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    
    # Return buffer
    buffer.seek(0)
    return buffer