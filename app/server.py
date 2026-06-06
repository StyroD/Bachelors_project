from shiny import render, ui, reactive
from db import search_vcf, search_rsid, search_variant, autocomplete_variants, get_variant_detail, query_full_annotation, search_variants_batch, get_haplotype_annotations
from services.vcf_service import parse_query, pretty_variant, format_autocomplete_option
from services.vcf_parser import parse_vcf_file, format_vcf_summary
from services.html_export import create_variant_html
from services.pdf_export import create_variant_pdf
import os
import tempfile
import io

def server(input, output, session):
    selected_variant = reactive.Value(None)
    autocomplete_suggestions = reactive.Value([])
    vcf_variants = reactive.Value([])
    vcf_annotations = reactive.Value([])
    vcf_source_filename = reactive.Value(None)

    @output
    @render.ui
    def dynamic_inputs():
        mode = input.mode()
        if mode == "rsid":
            return ui.div(
                ui.input_text("rsid_value", "rsID:", placeholder="e.g., rs12345", width="100%"),
                ui.tags.small("Enter a reference SNP ID", class_="form-text text-muted")
            )
        elif mode == "variant":
            return ui.div(
                ui.row(
                    ui.column(3, ui.input_text("chrom", "Chromosome:", placeholder="1")),
                    ui.column(3, ui.input_numeric("pos", "Position:", value=None)),
                    ui.column(3, ui.input_text("ref", "Ref:", placeholder="A")),
                    ui.column(3, ui.input_text("alt", "Alt:", placeholder="G"))
                ),
                ui.tags.small("Enter exact variant coordinates", class_="form-text text-muted")
            )
        else:
            return ui.div(
                ui.div(
                    ui.input_text("query", "Search:", placeholder="rsID (rs12345), position (chr1:12345), or keyword...", width="100%"),
                    ui.output_ui("autocomplete_dropdown"),
                    class_="autocomplete-wrapper"
                ),
                ui.tags.small("Supported formats: rs12345, chr1:12345 A>G, 21967916 A>G, or keyword search", class_="form-text text-muted")
            )

    @reactive.Effect
    def update_autocomplete():
        if input.mode() != "fulltext":
            autocomplete_suggestions.set([])
            return
        query = input.query()
        if query and len(query) >= 2:
            try:
                suggestions = autocomplete_variants(query, limit=10)
                autocomplete_suggestions.set(suggestions)
            except Exception as e:
                print(f"Autocomplete error: {e}")
                autocomplete_suggestions.set([])
        else:
            autocomplete_suggestions.set([])

    @output
    @render.ui
    def autocomplete_dropdown():
        suggestions = autocomplete_suggestions.get()
        if not suggestions or input.mode() != "fulltext":
            return ui.div(style="display: none;")
        items = []
        for sug in suggestions:
            label = format_autocomplete_option(sug)
            vcf_id = sug.get('vcf_id')
            chrom = sug.get('chrom', '')
            pos = sug.get('pos', '')
            ref = sug.get('ref', '')
            alt = sug.get('alt', '')
            rsid = sug.get('rsid', '')
            display_val = rsid if rsid else f"{chrom}:{pos} {ref}>{alt}"
            items.append(
                ui.tags.div(
                    label,
                    class_="autocomplete-item",
                    onmousedown=f"event.preventDefault(); Shiny.setInputValue('query', '{display_val}'); Shiny.setInputValue('select_autocomplete', '{vcf_id}', {{priority: 'event'}});"
                )
            )
        return ui.tags.div(*items, class_="autocomplete-list")

    @reactive.Effect
    @reactive.event(input.select_autocomplete)
    def handle_autocomplete_selection():
        vcf_id = input.select_autocomplete()
        if vcf_id:
            selected_variant.set(vcf_id)
            autocomplete_suggestions.set([])
            ui.update_navset("navbar", selected="Variant Details")

    @output
    @render.ui
    def results():
        search_count = input.search_btn()
        if search_count < 1:
            return ui.div(
                ui.h4("Ready to search"),
                ui.p("Enter your search criteria and click the Search button"),
                class_="empty-state"
            )
        mode = input.mode()
        rows = []
        try:
            if mode == "rsid":
                rsid = input.rsid_value()
                if not rsid:
                    return ui.div(ui.p("Please enter an rsID", class_="text-warning"), class_="empty-state")
                rows = search_rsid(rsid)
            elif mode == "variant":
                chrom = input.chrom()
                pos = input.pos()
                ref = input.ref()
                alt = input.alt()
                if not all([chrom, pos, ref, alt]):
                    return ui.div(ui.p("Please fill in all variant fields", class_="text-warning"), class_="empty-state")
                rows = search_variant(chrom, pos, ref, alt)
            else:
                query = input.query()
                if not query:
                    return ui.div(ui.p("Please enter a search query", class_="text-warning"), class_="empty-state")
                parsed = parse_query(query)
                if "rsid" in parsed:
                    rows = search_rsid(parsed["rsid"])
                elif all(k in parsed for k in ["pos", "ref", "alt"]):
                    rows = query_full_annotation(pos=parsed["pos"], ref=parsed["ref"], alt=parsed["alt"], chrom=parsed.get("chrom"))
                else:
                    rows = search_vcf(parsed.get("query", ""))
        except Exception as e:
            return ui.div(ui.div("⚠", class_="empty-state-icon"), ui.h4("Search Error"), ui.p(f"An error occurred: {str(e)}"), class_="empty-state")

        if not rows:
            return ui.div(ui.h4("No Results Found"), ui.p("Try adjusting your search criteria"), class_="empty-state")

        result_items = []
        for r in rows:
            vcf_id = r.get('vcf_id')
            chrom = r.get('chrom', '?')
            pos = r.get('pos', '?')
            ref = r.get('ref', '?')
            alt = r.get('alt', '?')
            rsid = r.get('rsid') or '—'
            result_items.append(
                ui.tags.div(
                    ui.tags.div(f"{chrom}:{pos} {ref} → {alt}", class_="vcf-main"),
                    ui.tags.div(ui.tags.span(f"rsID: {rsid}"), ui.tags.span(f"VCF ID: {vcf_id}"), class_="vcf-meta"),
                    class_="vcf-item",
                    onclick=f"Shiny.setInputValue('select_variant', '{vcf_id}', {{priority: 'event'}})"
                )
            )
        return ui.div(
            ui.div(ui.h3("Search Results", class_="results-header"), ui.p(f"Found {len(rows)} variant(s)", class_="results-count")),
            *result_items
        )

    @render.download(filename=lambda: f"variant_report_{selected_variant.get() or 'unknown'}.pdf")
    def download_pdf():
        vcf_id = selected_variant.get()
        if not vcf_id:
            return io.BytesIO(b"")
        try:
            rows = get_variant_detail(vcf_id)
            if not rows:
                return io.BytesIO(b"")
            first = rows[0]
            variant_data = {
                'vcf_id': vcf_id,
                'chrom': first.get('chrom', '?'),
                'pos': first.get('pos', '?'),
                'ref': first.get('ref', '?'),
                'alt': first.get('alt', '?'),
                'rsid': first.get('rsid') or 'Not assigned',
                'vcf_filename': vcf_source_filename.get()  # None if regular browsing
            }
            pdf_buffer = create_variant_pdf(variant_data, rows)
            return pdf_buffer
        except Exception as e:
            print(f"PDF generation error: {e}")
            import traceback
            traceback.print_exc()
            return io.BytesIO(b"")

    @render.download(filename=lambda: f"variant_report_{selected_variant.get() or 'unknown'}.html")
    def download_html():
        vcf_id = selected_variant.get()
        if not vcf_id:
            yield ""
            return
        try:
            rows = get_variant_detail(vcf_id)
            if not rows:
                yield ""
                return
            first = rows[0]
            variant_data = {
                'vcf_id': vcf_id,
                'chrom': first.get('chrom', '?'),
                'pos': first.get('pos', '?'),
                'ref': first.get('ref', '?'),
                'alt': first.get('alt', '?'),
                'rsid': first.get('rsid') or 'Not assigned'
            }
            html_content = create_variant_html(variant_data, rows)
            yield html_content
        except Exception as e:
            print(f"HTML generation error: {e}")
            import traceback
            traceback.print_exc()
            yield ""

    @reactive.Effect
    @reactive.event(input.select_variant)
    def handle_variant_selection():
        vcf_id = input.select_variant()
        if vcf_id:
            selected_variant.set(vcf_id)
            ui.update_navset("navbar", selected="Variant Details")

    @output
    @render.ui
    def variant_detail_content():
        vcf_id = selected_variant.get()
        if not vcf_id:
            return ui.div(ui.h4("No Variant Selected"), ui.p("Search for a variant and click on it to view details"), class_="empty-state")
        try:
            rows = get_variant_detail(vcf_id)
            if not rows:
                return ui.div(ui.h4("Variant Not Found"), ui.p(f"Could not find details for variant ID: {vcf_id}"), class_="empty-state")
            first = rows[0]
            chrom = first.get('chrom', '?')
            pos = first.get('pos', '?')
            ref = first.get('ref', '?')
            alt = first.get('alt', '?')
            rsid = first.get('rsid') or 'Not assigned'
            gene = first.get('gene')
            sections = []
            sections.append(
                ui.div(
                    ui.download_button("download_pdf", "Download PDF Report", class_="btn-primary", style="margin-right: 10px;"),
                    ui.download_button("download_html", "Download HTML Report", class_="btn-primary"),
                    style="margin-bottom: 20px;"
                )
            )
            sections.append(
                ui.div(
                    ui.div("Basic Information", class_="detail-header"),
                    ui.div(
                        ui.div(ui.div("Chromosome:", class_="detail-label"), ui.div(chrom, class_="detail-value"), class_="detail-row"),
                        ui.div(ui.div("Position:", class_="detail-label"), ui.div(f"{pos:,}", class_="detail-value"), class_="detail-row"),
                        ui.div(ui.div("Reference:", class_="detail-label"), ui.div(ref, class_="detail-value"), class_="detail-row"),
                        ui.div(ui.div("Alternate:", class_="detail-label"), ui.div(alt, class_="detail-value"), class_="detail-row"),
                        ui.div(ui.div("rsID:", class_="detail-label"), ui.div(rsid, class_="detail-value"), class_="detail-row"),
                        ui.div(ui.div("VCF ID:", class_="detail-label"), ui.div(vcf_id, class_="detail-value"), class_="detail-row"),
                        ui.div(ui.div("Gene", class_="detail-label"), ui.div(gene, class_="detail-value"), class_="detail-row")
                    ),
                    class_="detail-card"
                )
            )
            gene_info = [r for r in rows if r.get('gene')]
            if gene_info:
                gene_rows = []
                for field, label in [('gene','Gene'),('effect','Effect'),('assay_type','Assay Type'),('gene_product','Gene Product'),('functional_terms','Functional Terms')]:
                    val = gene_info[0].get(field)
                    if val:
                        gene_rows.append(ui.div(ui.div(f"{label}:", class_="detail-label"), ui.div(val, class_="detail-value"), class_="detail-row"))
                if gene_rows:
                    sections.append(ui.div(ui.div("Functional Annotation", class_="detail-header"), ui.div(*gene_rows), class_="detail-card"))
            clinical_rows = [r for r in rows if r.get('phenotype') or r.get('drug_name')]
            if clinical_rows:
                clinical_items = []
                for idx, cr in enumerate(clinical_rows):
                    item_rows = []
                    if cr.get('phenotype'):
                        item_rows.append(ui.div(ui.div("Phenotype:", class_="detail-label"), ui.div(cr['phenotype'], class_="detail-value"), class_="detail-row"))
                    if cr.get('significance'):
                        badge_class = "badge-success" if "beneficial" in cr['significance'].lower() else "badge-warning"
                        item_rows.append(ui.div(ui.div("Significance:", class_="detail-label"), ui.div(ui.span(cr['significance'], class_=f"badge {badge_class}"), class_="detail-value"), class_="detail-row"))
                    if cr.get('direction'):
                        item_rows.append(ui.div(ui.div("Direction:", class_="detail-label"), ui.div(cr['direction'], class_="detail-value"), class_="detail-row"))
                    if cr.get('drug_name'):
                        item_rows.append(ui.div(ui.div("Drug:", class_="detail-label"), ui.div(cr['drug_name'], class_="detail-value"), class_="detail-row"))
                    if cr.get('pmid'):
                        pmid = cr['pmid']
                        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                        item_rows.append(ui.div(
                            ui.div("Publication:", class_="detail-label"),
                            ui.div(
                                ui.tags.a(f"PMID: {pmid}", href=pubmed_url, target="_blank", class_="pubmed-link"),
                                class_="detail-value"
                            ),
                            class_="detail-row"
                        ))
                    if cr.get('notes'):
                        item_rows.append(ui.div(ui.div("Notes:", class_="detail-label"), ui.div(cr['notes'], class_="detail-value"), class_="detail-row"))
                    if cr.get('sentence'):
                        item_rows.append(ui.div(ui.div("Description:", class_="detail-label"), ui.div(cr['sentence'], class_="detail-value"), class_="detail-row"))
                    if item_rows:
                        clinical_items.append(ui.div(ui.tags.strong(f"Annotation {idx + 1}"), ui.div(*item_rows), ui.tags.hr(style="margin: 16px 0;")))
                if clinical_items:
                    sections.append(ui.div(ui.div("Clinical & Drug Annotations", class_="detail-header"), ui.div(*clinical_items), class_="detail-card"))
            sections.append(ui.div(ui.input_action_button("back_to_search", "← Back to Search", class_="btn-secondary"), style="margin-top: 30px;"))
            return ui.div(*sections)
        except Exception as e:
            return ui.div(ui.h4("Error Loading Details"), ui.p(f"An error occurred: {str(e)}"), class_="empty-state")

    @reactive.Effect
    @reactive.event(input.back_to_search)
    def go_back():
        ui.update_navset("navbar", selected="Search")

    @output
    @render.ui
    def vcf_upload_status():
        file_info = input.vcf_file()

        if not file_info:
            return None

        try:
            file_data = file_info[0]
            vcf_source_filename.set(file_data['name'])  # ← AFTER file_data is assigned

            # Detect if uploaded file is gzipped
            file_name = file_data['name']
            is_gzipped = file_name.endswith('.gz')
            suffix = '.vcf.gz' if is_gzipped else '.vcf'

            print(f"DEBUG: Uploading {file_name}, gzipped: {is_gzipped}")

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='wb') as tmp:
                # Always read as binary
                if hasattr(file_data['datapath'], 'read_bytes'):
                    content = file_data['datapath'].read_bytes()
                else:
                    with open(file_data['datapath'], 'rb') as f:
                        content = f.read()

                tmp.write(content)
                tmp_path = tmp.name

            print(f"DEBUG: Saved to {tmp_path}, size: {len(content)} bytes")

            from services.vcf_parser import parse_vcf_file_stream

            total_variants = 0
            total_annotated = 0
            all_annotations = []
            all_errors = []
            chromosomes = set()
            has_rsids = 0
            MAX_ANNOTATED = float('inf')
            MAX_TOTAL = float('inf')

            batch_num = 0
            # Process file in batches of 1000000 variants
            for batch_variants, batch_errors in parse_vcf_file_stream(tmp_path, batch_size=1000000):
                batch_num += 1
                print(f"Processing batch {batch_num} ({len(batch_variants)} variants)...")
                if batch_errors:
                    all_errors.extend(batch_errors)
                if not batch_variants:
                    continue
                total_variants += len(batch_variants)
                chromosomes.update(v['chrom'] for v in batch_variants)
                has_rsids += sum(1 for v in batch_variants if v.get('rsid'))
                print(f"  Searching annotations in database...")
                batch_annotations = search_variants_batch(batch_variants)
                if batch_annotations:
                    all_annotations.extend(batch_annotations)
                    annotated_in_batch = len(set((a['chrom'], a['pos'], a['ref'], a['alt']) for a in batch_annotations if a.get('drug_name') or a.get('phenotype')))
                    total_annotated += annotated_in_batch
                    print(f"  Found {annotated_in_batch} annotated variants (total: {total_annotated})")
                if total_annotated >= MAX_ANNOTATED:
                    all_errors.append(f"Stopped after finding {total_annotated} annotated variants (file may contain more)")
                    break
                if total_variants >= MAX_TOTAL:
                    all_errors.append(f"Stopped after processing {total_variants} variants (file may contain more)")
                    break

            os.unlink(tmp_path)

            if total_variants == 0:
                return ui.div(
                    ui.h4("No variants found"),
                    ui.p("The file does not contain valid variant data."),
                    ui.tags.ul(*[ui.tags.li(err) for err in all_errors[:10]]) if all_errors else None,
                    class_="status-box status-error"
                )

            vcf_annotations.set(all_annotations)
            status_class = "status-success" if total_annotated > 0 else "status-info"

            return ui.div(
                ui.h4("VCF File Processed"),
                ui.p(f"Filename: {file_data['name']}"),
                ui.p(f"Processed variants: {total_variants:,}"),
                ui.p(f"Chromosomes: {', '.join(sorted(chromosomes))}"),
                ui.p(f"Variants with rsIDs: {has_rsids:,}"),
                ui.p(f"Variants with annotations: {total_annotated:,}"),
                ui.tags.ul(*[ui.tags.li(err) for err in all_errors[:5]]) if all_errors else None,
                ui.p(f"({len(all_errors)} messages total)" if len(all_errors) > 5 else "", class_="text-muted") if all_errors else None,
                class_=f"status-box {status_class}"
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return ui.div(ui.h4("Error Processing VCF File"), ui.p(f"Error: {str(e)}"), class_="status-box status-error")

    @output
    @render.ui
    def vcf_results():
        annotations = vcf_annotations.get()
        if not annotations:
            variants = vcf_variants.get()
            if variants:
                return ui.div(ui.h4("No Annotations Found"), ui.p("None of the variants in your VCF file have annotations in our database."), class_="empty-state")
            return None
        variant_groups = {}
        for ann in annotations:
            key = (ann['chrom'], ann['pos'], ann['ref'], ann['alt'])
            if key not in variant_groups:
                variant_groups[key] = []
            variant_groups[key].append(ann)
        result_items = []
        for (chrom, pos, ref, alt), group in sorted(variant_groups.items()):
            first = group[0]
            vcf_id = first.get('vcf_id')
            rsid = first.get('rsid') or '—'
            has_clinical = any(g.get('phenotype') or g.get('drug_name') for g in group)
            badge_class = "badge-success" if has_clinical else "badge-info"
            badge_text = "Clinical Data" if has_clinical else "Basic Info"
            result_items.append(
                ui.tags.div(
                    ui.tags.div(f"{chrom}:{pos} {ref} → {alt}", class_="vcf-main"),
                    ui.tags.div(ui.tags.span(f"rsID: {rsid}"), ui.tags.span(ui.tags.span(badge_text, class_=f"badge {badge_class}")), class_="vcf-meta"),
                    class_="vcf-item",
                    onclick=f"Shiny.setInputValue('select_variant', '{vcf_id}', {{priority: 'event'}})"
                )
            )
        return ui.div(
            ui.div(ui.h3("Annotated Variants", class_="results-header"), ui.p(f"Found {len(variant_groups)} annotated variant(s)", class_="results-count")),
            *result_items
        )