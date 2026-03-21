from shiny import ui

app_ui = ui.page_navbar(
    ui.nav_panel(
        "Search",
        ui.div(
            ui.h2("Variant Search", class_="page-title"),
            ui.p("Search for genetic variants by rsID, position, or keyword", class_="subtitle"),
            
            ui.div(
                ui.input_radio_buttons(
                    "mode",
                    "Search mode:",
                    choices={
                        "fulltext": "Quick Search (rsID, position, etc.)",
                        "rsid": "Search by rsID",
                        "variant": "Exact Variant Match"
                    },
                    selected="fulltext",
                    inline=True
                ),
                class_="search-mode"
            ),

            ui.output_ui("dynamic_inputs"),
            
            ui.div(
                ui.input_action_button(
                    "search_btn", 
                    "Search", 
                    class_="btn-primary btn-lg"
                ),
                class_="search-button-container"
            ),

            ui.output_ui("results"),
            class_="search-container"
        )
    ),
    
    ui.nav_panel(
        "VCF Upload",
        ui.div(
            ui.h2("Upload VCF File", class_="page-title"),
            ui.p("Upload a VCF file to search for annotations of your variants", class_="subtitle"),
            
            ui.div(
                ui.input_file(
                    "vcf_file",
                    "Choose VCF file:",
                    accept=[".vcf", ".vcf.gz", "application/gzip", "application/x-gzip"],
                    multiple=False
                ),
                ui.tags.small(
                    "Supported formats: .vcf, .vcf.gz",
                    class_="form-text text-muted"
                ),
                class_="upload-section"
            ),
            
            ui.output_ui("vcf_upload_status"),
            ui.output_ui("vcf_results"),
            
            class_="search-container"
        )
    ),
    
    ui.nav_panel(
        "Variant Details",
        ui.div(
            ui.h2("Variant Annotation Details", class_="page-title"),
            ui.output_ui("variant_detail_content"),
            class_="detail-container"
        )
    ),
    
    title="Pharmacogenomics Variant Browser",
    id="navbar",
    
    header=ui.tags.head(
        ui.tags.style("""
            :root {
                --primary-color: #2c3e50;
                --secondary-color: #3498db;
                --accent-color: #e74c3c;
                --success-color: #27ae60;
                --bg-light: #f8f9fa;
                --bg-card: #ffffff;
                --border-color: #e0e0e0;
                --text-dark: #2c3e50;
                --text-muted: #7f8c8d;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: var(--bg-light);
                color: var(--text-dark);
            }
            
            .page-title {
                color: var(--primary-color);
                font-weight: 600;
                margin-bottom: 8px;
            }
            
            .subtitle {
                color: var(--text-muted);
                font-size: 1.1rem;
                margin-bottom: 30px;
            }
            
            .search-container, .detail-container {
                max-width: 900px;
                margin: 0 auto;
                padding: 30px 20px;
            }
            
            .search-mode {
                background: var(--bg-card);
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }
            
            .upload-section {
                background: var(--bg-card);
                padding: 30px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                border: 2px dashed var(--border-color);
                transition: all 0.3s;
            }
            
            .upload-section:hover {
                border-color: var(--secondary-color);
                box-shadow: 0 4px 12px rgba(52, 152, 219, 0.15);
            }
            
            .shiny-input-container {
                margin-bottom: 20px;
            }
            
            .form-control, .form-select {
                border: 2px solid var(--border-color);
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 1rem;
                transition: all 0.2s;
            }
            
            .form-control:focus, .form-select:focus {
                border-color: var(--secondary-color);
                box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
                outline: none;
            }
            
            .autocomplete-wrapper {
                position: relative;
                width: 100%;
            }
            
            .autocomplete-list {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 2px solid var(--border-color);
                border-top: none;
                border-radius: 0 0 8px 8px;
                max-height: 300px;
                overflow-y: auto;
                z-index: 1000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                margin-top: -2px;
            }
            
            .autocomplete-item {
                padding: 12px 16px;
                cursor: pointer;
                transition: background 0.15s;
                border-bottom: 1px solid var(--bg-light);
                user-select: none;
            }
            
            .autocomplete-item:hover {
                background: var(--secondary-color);
                color: white;
            }
            
            .autocomplete-item:last-child {
                border-bottom: none;
            }
            
            .search-button-container {
                margin: 30px 0;
            }
            
            .btn-primary {
                background: var(--secondary-color);
                border: none;
                padding: 14px 40px;
                font-size: 1.1rem;
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.2s;
                box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
            }
            
            .btn-primary:hover {
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(52, 152, 219, 0.4);
            }
            
            .results-header {
                margin: 30px 0 20px 0;
                padding-bottom: 15px;
                border-bottom: 3px solid var(--primary-color);
            }
            
            .results-count {
                color: var(--text-muted);
                font-size: 0.95rem;
                margin-top: 5px;
            }
            
            .vcf-item {
                background: var(--bg-card);
                border: 2px solid var(--border-color);
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 12px;
                transition: all 0.2s;
                cursor: pointer;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            
            .vcf-item:hover {
                border-color: var(--secondary-color);
                transform: translateX(4px);
                box-shadow: 0 4px 12px rgba(52, 152, 219, 0.2);
            }
            
            .vcf-main {
                font-family: 'Courier New', monospace;
                font-size: 1.1rem;
                color: var(--primary-color);
                font-weight: 600;
                margin-bottom: 8px;
            }
            
            .vcf-meta {
                display: flex;
                gap: 20px;
                font-size: 0.9rem;
                color: var(--text-muted);
            }
            
            .vcf-meta span {
                display: inline-flex;
                align-items: center;
            }
            
            .status-box {
                background: var(--bg-card);
                border-radius: 12px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }
            
            .status-success {
                border-left: 4px solid var(--success-color);
            }
            
            .status-error {
                border-left: 4px solid var(--accent-color);
            }
            
            .status-info {
                border-left: 4px solid var(--secondary-color);
            }
            
            .detail-card {
                background: var(--bg-card);
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                border-left: 4px solid var(--secondary-color);
            }
            
            .detail-header {
                font-size: 1.3rem;
                font-weight: 600;
                color: var(--primary-color);
                margin-bottom: 16px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .detail-row {
                display: grid;
                grid-template-columns: 200px 1fr;
                gap: 16px;
                margin-bottom: 12px;
                padding: 8px 0;
                border-bottom: 1px solid var(--bg-light);
            }
            
            .detail-row:last-child {
                border-bottom: none;
            }
            
            .detail-label {
                font-weight: 600;
                color: var(--text-muted);
            }
            
            .detail-value {
                font-family: 'Courier New', monospace;
                color: var(--text-dark);
            }
            
            .badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
            }
            
            .badge-success {
                background: #d4edda;
                color: #155724;
            }
            
            .badge-warning {
                background: #fff3cd;
                color: #856404;
            }
            
            .badge-danger {
                background: #f8d7da;
                color: #721c24;
            }
            
            .badge-info {
                background: #d1ecf1;
                color: #0c5460;
            }
            
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: var(--text-muted);
            }
            
            .empty-state-icon {
                font-size: 4rem;
                margin-bottom: 20px;
                opacity: 0.3;
            }
            
            @media (max-width: 768px) {
                .detail-row {
                    grid-template-columns: 1fr;
                    gap: 8px;
                }
                
                .vcf-meta {
                    flex-direction: column;
                    gap: 8px;
                }
            }
        """)
    )
)