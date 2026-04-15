from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import io

def create_variant_pdf(variant_data, annotations):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18,
                            title="Variant Annotation Report")
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=30, alignment=TA_CENTER)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=16, spaceAfter=12, spaceBefore=12)

    elements.append(Paragraph("Variant Annotation Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<para align=center>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</para>", styles['Normal']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Basic Information", heading_style))

    basic_data = [
        ['Field', 'Value'],
        ['Chromosome', str(variant_data.get('chrom', '?'))],
        ['Position', f"{variant_data.get('pos', '?'):,}"],
        ['Reference Allele', variant_data.get('ref', '?')],
        ['Alternate Allele', variant_data.get('alt', '?')],
        ['rsID', variant_data.get('rsid', 'Not assigned')],
        ['VCF ID', str(variant_data.get('vcf_id', '?'))],
    ]

    # Only add Source VCF File row if variant came from a VCF upload
    vcf_filename = variant_data.get('vcf_filename')
    if vcf_filename:
        basic_data.append(['Source VCF File', vcf_filename])

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

    gene_info = [a for a in annotations if a.get('gene')]
    if gene_info:
        elements.append(Paragraph("Functional Annotation", heading_style))
        first = gene_info[0]
        func_data = [['Field', 'Value']]
        for field, label in [('gene','Gene'),('effect','Effect'),('assay_type','Assay Type'),('gene_product','Gene Product'),('functional_terms','Functional Terms')]:
            if first.get(field):
                func_data.append([label, first[field]])
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
            if ann.get('pmid'):
                pmid = ann['pmid']
                pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                clinical_data.append(['Publication', Paragraph(f'<link href="{pubmed_url}" color="blue">{pubmed_url}</link>', styles['Normal'])])
            if ann.get('notes'):
                clinical_data.append(['Notes', Paragraph(ann['notes'], styles['Normal'])])
            if ann.get('sentence'):
                clinical_data.append(['Description', Paragraph(ann['sentence'], styles['Normal'])])
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

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<para align=center><i>Generated by Pharmacogenomics Variant Browser</i></para>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer