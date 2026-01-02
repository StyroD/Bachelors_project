import requests
import json
from typing import Optional, Dict, List
import logging
"""
Script for testing ClinPGx REST API endpoints.
"""
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClinPGxClient:
    """Client for querying ClinPGx REST API endpoints."""
    
    BASE_URL = "https://api.clinpgx.org/v1"
    DEFAULT_TIMEOUT = 10
    
    def __init__(self):
        """Initialize API client."""
        self.session = requests.Session()
    
    # ========================
    # Gene Endpoints
    # ========================
    
    def get_gene(self, accession_id: str, view: str = "base") -> Optional[Dict]:
        """
        Retrieve a single gene by accession ID.
        
        Args:
            accession_id: ClinPGx gene ID (e.g., 'PA356')
            view: 'min', 'base', or 'max'
        
        Returns:
            Gene object or None
        """
        url = f"{self.BASE_URL}/data/gene"
        params = {
            'accessionId': accession_id,
            'view': view
        }
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        if result.get('status') == 'success' and result.get('data'):
            return result['data'][0]
        return None
    
    def query_genes(self, symbol: Optional[str] = None, 
                   accession_id: Optional[str] = None, 
                   view: str = "base") -> List[Dict]:
        """
        Query genes by symbol or accession ID.
        
        Args:
            symbol: HGNC gene symbol (e.g., 'TPMT')
            accession_id: ClinPGx ID
            view: 'min', 'base', or 'max'
        
        Returns:
            List of gene objects
        """
        url = f"{self.BASE_URL}/data/gene"
        params = {'view': view}
        
        if symbol:
            params['symbol'] = symbol
        if accession_id:
            params['accessionId'] = accession_id
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    def get_gene_cross_references(self, gene_id: str, view: str = "base") -> List[Dict]:
        """Get cross references for a gene."""
        url = f"{self.BASE_URL}/data/gene/{gene_id}/crossReferences"
        params = {'view': view}
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    def get_gene_ontology_terms(self, gene_id: str, view: str = "base") -> List[Dict]:
        """Get ontology terms for a gene."""
        url = f"{self.BASE_URL}/data/gene/{gene_id}/ontologyTerms"
        params = {'view': view}
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    # ========================
    # Chemical Endpoints
    # ========================
    
    def get_chemical(self, accession_id: str, view: str = "base") -> Optional[Dict]:
        """Retrieve a single chemical by accession ID."""
        url = f"{self.BASE_URL}/data/chemical"
        params = {
            'accessionId': accession_id,
            'view': view
        }
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result['data'][0] if result.get('data') else None
    
    def query_chemicals(self, name: Optional[str] = None, 
                       accession_id: Optional[str] = None, 
                       view: str = "base") -> List[Dict]:
        """Query chemicals by name or accession ID."""
        url = f"{self.BASE_URL}/data/chemical"
        params = {'view': view}
        
        if name:
            params['name'] = name
        if accession_id:
            params['accessionId'] = accession_id
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    # ========================
    # Disease Endpoints
    # ========================
    
    def get_disease(self, accession_id: str, view: str = "base") -> Optional[Dict]:
        """Retrieve a single disease by accession ID."""
        url = f"{self.BASE_URL}/data/disease"
        params = {
            'accessionId': accession_id,
            'view': view
        }
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result['data'][0] if result.get('data') else None
    
    def query_diseases(self, name: Optional[str] = None, 
                      accession_id: Optional[str] = None, 
                      view: str = "base") -> List[Dict]:
        """Query diseases by name or accession ID."""
        url = f"{self.BASE_URL}/data/disease"
        params = {'view': view}
        
        if name:
            params['name'] = name
        if accession_id:
            params['accessionId'] = accession_id
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    # ========================
    # Pathway Endpoints
    # ========================
    
    def get_pathway(self, accession_id: str, view: str = "base") -> Optional[Dict]:
        """Retrieve a single pathway by accession ID."""
        url = f"{self.BASE_URL}/data/pathway"
        params = {
            'accessionId': accession_id,
            'view': view
        }
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result['data'][0] if result.get('data') else None
    
    def query_pathways(self, name: Optional[str] = None, 
                      accession_id: Optional[str] = None, 
                      view: str = "base") -> List[Dict]:
        """Query pathways by name or accession ID."""
        url = f"{self.BASE_URL}/data/pathway"
        params = {'view': view}
        
        if name:
            params['name'] = name
        if accession_id:
            params['accessionId'] = accession_id
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    # ========================
    # Variant Endpoints
    # ========================
    
    def get_variant(self, variant_id: str, view: str = "base") -> Optional[Dict]:
        """Retrieve a single variant by ID."""
        url = f"{self.BASE_URL}/data/variant/{variant_id}"
        params = {'view': view}
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data') if result.get('status') == 'success' else None
    
    def query_variants(self, symbol: Optional[str] = None, 
                      view: str = "base") -> List[Dict]:
        """Query variants by symbol (e.g., rsID)."""
        url = f"{self.BASE_URL}/data/variant/"
        params = {'view': view}
        
        if symbol:
            params['symbol'] = symbol
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    # ========================
    # Annotation Endpoints
    # ========================
    
    def query_clinical_annotations(self, gene_symbol: Optional[str] = None,
                                  chemical_id: Optional[str] = None,
                                  variant_rsid: Optional[str] = None,
                                  level_of_evidence: Optional[str] = None,
                                  view: str = "base") -> List[Dict]:
        """
        Query clinical annotations.
        
        Args:
            gene_symbol: Gene symbol (e.g., 'TPMT')
            chemical_id: Chemical accession ID
            variant_rsid: Variant rsID
            level_of_evidence: '1A', '1B', '2A', '2B', '3', '4'
            view: 'min', 'base', or 'max'
        
        Returns:
            List of clinical annotations
        """
        url = f"{self.BASE_URL}/data/clinicalAnnotation"
        params = {'view': view}
        
        if gene_symbol:
            params['location.genes.symbol'] = gene_symbol
        if chemical_id:
            params['relatedChemicals.accessionId'] = chemical_id
        if variant_rsid:
            params['location.fingerprint'] = variant_rsid
        if level_of_evidence:
            params['levelOfEvidence.term'] = level_of_evidence
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    def query_variant_annotations(self, gene_symbol: Optional[str] = None,
                                 variant_rsid: Optional[str] = None,
                                 view: str = "base") -> List[Dict]:
        """Query variant annotations."""
        url = f"{self.BASE_URL}/data/variantAnnotation"
        params = {'view': view}
        
        if gene_symbol:
            params['location.genes.symbol'] = gene_symbol
        if variant_rsid:
            params['location.fingerprint'] = variant_rsid
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    def query_guideline_annotations(self, source: Optional[str] = None,
                                   chemical_id: Optional[str] = None,
                                   gene_id: Optional[str] = None,
                                   view: str = "base") -> List[Dict]:
        """
        Query guideline annotations.
        
        Args:
            source: 'cpic', 'dpwg', or 'pro'
            chemical_id: Chemical accession ID
            gene_id: Gene accession ID
            view: 'min', 'base', or 'max'
        """
        url = f"{self.BASE_URL}/data/guidelineAnnotation"
        params = {'view': view}
        
        if source:
            params['source'] = source
        if chemical_id:
            params['relatedChemicals.accessionId'] = chemical_id
        if gene_id:
            params['relatedGenes.accessionId'] = gene_id
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    def query_drug_labels(self, source: Optional[str] = None,
                         chemical_id: Optional[str] = None,
                         gene_symbol: Optional[str] = None,
                         view: str = "base") -> List[Dict]:
        """
        Query drug labels.
        
        Args:
            source: 'fda', 'ema', 'pmda', or 'hcsc'
            chemical_id: Chemical accession ID
            gene_symbol: Gene symbol
            view: 'min', 'base', or 'max'
        """
        url = f"{self.BASE_URL}/data/label"
        params = {'view': view}
        
        if source:
            params['source'] = source
        if chemical_id:
            params['relatedChemicals.accessionId'] = chemical_id
        if gene_symbol:
            params['relatedGenes.symbol'] = gene_symbol
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []
    
    # ========================
    # Report Endpoints
    # ========================
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        url = f"{self.BASE_URL}/report/stats"
        
        response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', {}) if result.get('status') == 'success' else {}
    
    def get_variant_frequency(self, fingerprint: str) -> Optional[Dict]:
        """Get variant frequency data for a given fingerprint (e.g., rsID)."""
        url = f"{self.BASE_URL}/report/variantFrequency"
        params = {'fp': fingerprint}
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data') if result.get('status') == 'success' else None
    
    def get_literature_id(self, pmid: str) -> Optional[int]:
        """Get ClinPGx literature ID from PubMed ID."""
        url = f"{self.BASE_URL}/report/literatureId/{pmid}"
        
        response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()
        return None
    
    def query_literature(self, resource_id: Optional[str] = None,
                        lit_type: Optional[str] = None,
                        view: str = "base") -> List[Dict]:
        """Query literature."""
        url = f"{self.BASE_URL}/data/literature"
        params = {'view': view}
        
        if resource_id:
            params['resourceId'] = resource_id
        if lit_type:
            params['type'] = lit_type
        
        response = self.session.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        
        return result.get('data', []) if result.get('status') == 'success' else []


# ========================
# Example Usage
# ========================

if __name__ == "__main__":
    client = ClinPGxClient()
    
    # Example 1: Get a single gene
    print("=== Get Single Gene ===")
    gene = client.get_gene('PA134877725', view='max')
    if gene:
        print(f"Gene: {gene.get('symbol')} ({gene.get('name')})")
        print(f"Version: {gene.get('version')}")
        print(f"Chromosome: {gene.get('chr', {}).get('name')}")
    
    # Example 2: Query genes by symbol
    print("\n=== Query Gene by Symbol ===")
    genes = client.query_genes(symbol='TPMT', view='base')
    for g in genes:
        print(f"  - {g.get('symbol')}: {g.get('name')}")
    
    # Example 3: Get chemical
    print("\n=== Get Chemical ===")
    chemicals = client.query_chemicals(name='warfarin', view='min')
    for chem in chemicals:
        print(f"  - {chem.get('name')} (ID: {chem.get('id')})")
    
    # Example 4: Query clinical annotations
    print("\n=== Clinical Annotations for TPMT ===")
    annotations = client.query_clinical_annotations(
        gene_symbol='TPMT',
        view='base'
    )
    print(f"Found {len(annotations)} annotations")
    for ann in annotations[:3]:  # Show first 3
        print(f"  - Level: {ann.get('levelOfEvidence', {}).get('term')}")
    
    # Example 5: Get guideline annotations
    print("\n=== CPIC Guidelines ===")
    guidelines = client.query_guideline_annotations(source='cpic', view='min')
    print(f"Found {len(guidelines)} CPIC guidelines")
    for gl in guidelines[:3]:
        print(f"  - {gl.get('name')}")
    
    # Example 6: Get database statistics
    print("\n=== Database Stats ===")
    stats = client.get_stats()
    print(json.dumps(stats, indent=2))
    
    # Example 7: Get variant frequency
    print("\n=== Variant Frequency ===")
    freq = client.get_variant_frequency('rs2228001')
    if freq:
        print(f"Found frequency data for rs2228001")
        print(json.dumps(freq, indent=2))