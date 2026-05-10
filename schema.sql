

CREATE TABLE IF NOT EXISTS dbsnp_variant (
    rsid VARCHAR(50) NOT NULL,
    chrom VARCHAR(10) NOT NULL,
    pos INTEGER NOT NULL,
    ref VARCHAR(1000) NOT NULL,
    alt VARCHAR(1000) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rsid, chrom, pos, ref, alt)
);

CREATE TABLE IF NOT EXISTS variant_identifier (
    id VARCHAR(100) PRIMARY KEY,
    type TEXT NOT NULL,   
    gene TEXT           

CREATE TABLE IF NOT EXISTS chemical (
    drug_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS haplotype (
    haplotype_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,  
    gene TEXT NOT NULL,  
    UNIQUE (name, gene)
);

CREATE TABLE IF NOT EXISTS clinpgx_drug_annotation (
    id SERIAL PRIMARY KEY,
    annotation_id TEXT,   
    phenotype TEXT,
    significance TEXT,
    direction TEXT,
    notes TEXT,
    sentence TEXT,
    pmid TEXT            
);



CREATE TABLE IF NOT EXISTS vcf_variant (
    vcf_id SERIAL PRIMARY KEY,
    chrom TEXT NOT NULL,
    pos INTEGER NOT NULL,
    ref TEXT NOT NULL,
    alt TEXT NOT NULL,
    rsid TEXT,
    UNIQUE (chrom, pos, ref, alt)
);

CREATE TABLE IF NOT EXISTS variant_identifier_dbsnp (
    id VARCHAR(100) NOT NULL,
    rsid VARCHAR(50) NOT NULL,
    PRIMARY KEY (id, rsid),
    FOREIGN KEY (id) REFERENCES variant_identifier(id) ON DELETE CASCADE
);



CREATE TABLE IF NOT EXISTS functional_annotation (
    id SERIAL PRIMARY KEY,
    identifier_id TEXT REFERENCES variant_identifier(id) ON DELETE CASCADE,
    effect TEXT,
    assay_type TEXT,
    gene_product TEXT,
    functional_terms TEXT,
    annotation_id TEXT,  
    pmid TEXT            
);

CREATE TABLE IF NOT EXISTS haplotype_identifier (
    haplotype_id INT REFERENCES haplotype(haplotype_id) ON DELETE CASCADE,
    identifier_id TEXT REFERENCES variant_identifier(id) ON DELETE CASCADE,
    PRIMARY KEY (haplotype_id, identifier_id)
);


CREATE TABLE IF NOT EXISTS drug_annotation_variant (
    annotation_entry INT REFERENCES clinpgx_drug_annotation(id) ON DELETE CASCADE,
    identifier_id TEXT REFERENCES variant_identifier(id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_entry, identifier_id)
);

CREATE TABLE IF NOT EXISTS drug_annotation_chemical (
    annotation_entry INT REFERENCES clinpgx_drug_annotation(id) ON DELETE CASCADE,
    drug_id TEXT REFERENCES chemical(drug_id) ON DELETE CASCADE,
    PRIMARY KEY (annotation_entry, drug_id)
);



CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);



CREATE INDEX IF NOT EXISTS idx_dbsnp_variant_rsid ON dbsnp_variant(rsid);
CREATE INDEX IF NOT EXISTS idx_dbsnp_variant_position ON dbsnp_variant(chrom, pos);
CREATE INDEX IF NOT EXISTS idx_variant_identifier_dbsnp_rsid ON variant_identifier_dbsnp(rsid);
CREATE INDEX IF NOT EXISTS idx_variant_identifier_dbsnp_id ON variant_identifier_dbsnp(id);
CREATE INDEX IF NOT EXISTS idx_vcf_variant_rsid ON vcf_variant(rsid);
CREATE INDEX IF NOT EXISTS idx_vcf_variant_position ON vcf_variant(chrom, pos);
CREATE INDEX IF NOT EXISTS idx_functional_annotation_identifier ON functional_annotation(identifier_id);
CREATE INDEX IF NOT EXISTS idx_drug_annotation_variant_identifier ON drug_annotation_variant(identifier_id);
CREATE INDEX IF NOT EXISTS idx_clinpgx_annotation_id ON clinpgx_drug_annotation(annotation_id);