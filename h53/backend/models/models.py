from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import func

db = SQLAlchemy()

def generate_uuid():
    return str(uuid.uuid4())

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    uploads = db.relationship('UploadFile', backref='user', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('AnalysisTask', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class UploadFile(db.Model):
    __tablename__ = 'upload_files'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    metadata = db.Column(db.JSON, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'metadata': self.metadata,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

class AnalysisTask(db.Model):
    __tablename__ = 'analysis_tasks'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='queued')
    parameters = db.Column(db.JSON, nullable=False)
    progress = db.Column(db.Float, default=0.0)
    current_stage = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    gwas_result = db.relationship('GWASResult', backref='task', uselist=False, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'current_stage': self.current_stage,
            'error_message': self.error_message,
            'parameters': self.parameters,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class GWASResult(db.Model):
    __tablename__ = 'gwas_results'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    task_id = db.Column(db.String(36), db.ForeignKey('analysis_tasks.id'), nullable=False)
    model_type = db.Column(db.String(10), nullable=False)
    phenotype = db.Column(db.String(100), nullable=False)
    inflation_factor = db.Column(db.Float)
    significant_snp_count = db.Column(db.Integer, default=0)
    manhattan_data = db.Column(db.JSON)
    qq_data = db.Column(db.JSON)
    notes = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    significant_snps = db.relationship('SignificantSNP', backref='result', lazy=True, cascade='all, delete-orphan')
    visualization_files = db.relationship('VisualizationFile', backref='result', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'model_type': self.model_type,
            'phenotype': self.phenotype,
            'inflation_factor': self.inflation_factor,
            'significant_snp_count': self.significant_snp_count,
            'manhattan_data': self.manhattan_data,
            'qq_data': self.qq_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SignificantSNP(db.Model):
    __tablename__ = 'significant_snps'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    result_id = db.Column(db.String(36), db.ForeignKey('gwas_results.id'), nullable=True)
    multiphenotype_result_id = db.Column(db.String(36), db.ForeignKey('multiphenotype_results.id'), nullable=True)
    snp_id = db.Column(db.String(100), nullable=False)
    chromosome = db.Column(db.String(20), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    ref_allele = db.Column(db.String(50), nullable=False)
    alt_allele = db.Column(db.String(50), nullable=False)
    p_value = db.Column(db.Float, nullable=False)
    log10_p = db.Column(db.Float, nullable=False)
    effect_size = db.Column(db.Float)
    maf = db.Column(db.Float)
    gene = db.Column(db.String(100))
    annotation = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'snp': self.snp_id,
            'chr': self.chromosome,
            'pos': self.position,
            'ref': self.ref_allele,
            'alt': self.alt_allele,
            'pValue': self.p_value,
            'log10P': self.log10_p,
            'effectSize': self.effect_size,
            'maf': self.maf,
            'gene': self.gene,
            'annotation': self.annotation
        }

class VisualizationFile(db.Model):
    __tablename__ = 'visualization_files'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    result_id = db.Column(db.String(36), db.ForeignKey('gwas_results.id'), nullable=True)
    multiphenotype_result_id = db.Column(db.String(36), db.ForeignKey('multiphenotype_results.id'), nullable=True)
    enrichment_result_id = db.Column(db.String(36), db.ForeignKey('enrichment_results.id'), nullable=True)
    finemapping_result_id = db.Column(db.String(36), db.ForeignKey('finemapping_results.id'), nullable=True)
    file_type = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_type': self.file_type,
            'file_path': self.file_path,
            'width': self.width,
            'height': self.height,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ReferenceGenome(db.Model):
    __tablename__ = 'reference_genomes'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    fasta_path = db.Column(db.String(500), nullable=False)
    gff_path = db.Column(db.String(500))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    gene_annotations = db.relationship('GeneAnnotation', backref='genome', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'species': self.species,
            'version': self.version,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class GeneAnnotation(db.Model):
    __tablename__ = 'gene_annotations'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    genome_id = db.Column(db.String(50), db.ForeignKey('reference_genomes.id'), nullable=False)
    gene_id = db.Column(db.String(50), nullable=False)
    gene_name = db.Column(db.String(100))
    chromosome = db.Column(db.String(20), nullable=False)
    start_pos = db.Column(db.Integer, nullable=False)
    end_pos = db.Column(db.Integer, nullable=False)
    strand = db.Column(db.String(1))
    description = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'gene_id': self.gene_id,
            'gene_name': self.gene_name,
            'chromosome': self.chromosome,
            'start_pos': self.start_pos,
            'end_pos': self.end_pos,
            'strand': self.strand,
            'description': self.description
        }


class MultiPhenotypeResult(db.Model):
    __tablename__ = 'multiphenotype_results'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    task_id = db.Column(db.String(36), db.ForeignKey('analysis_tasks.id'), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    phenotypes = db.Column(db.JSON, nullable=False)
    n_phenotypes = db.Column(db.Integer, nullable=False)
    inflation_factor = db.Column(db.Float)
    significant_snp_count = db.Column(db.Integer, default=0)
    manhattan_data = db.Column(db.JSON)
    qq_data = db.Column(db.JSON)
    canonical_correlations = db.Column(db.JSON)
    canonical_weights = db.Column(db.JSON)
    loading_scores = db.Column(db.JSON)
    f_statistics = db.Column(db.JSON)
    wilks_lambda = db.Column(db.JSON)
    notes = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    significant_snps = db.relationship('SignificantSNP', backref='multiphenotype_result', lazy=True, cascade='all, delete-orphan', foreign_keys='SignificantSNP.multiphenotype_result_id')
    visualization_files = db.relationship('VisualizationFile', backref='multiphenotype_result', lazy=True, cascade='all, delete-orphan', foreign_keys='VisualizationFile.multiphenotype_result_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'method': self.method,
            'phenotypes': self.phenotypes,
            'nPhenotypes': self.n_phenotypes,
            'inflationFactor': self.inflation_factor,
            'significantSNPCount': self.significant_snp_count,
            'manhattanData': self.manhattan_data,
            'qqData': self.qq_data,
            'canonicalCorrelations': self.canonical_correlations,
            'canonicalWeights': self.canonical_weights,
            'loadingScores': self.loading_scores,
            'fStatistics': self.f_statistics,
            'wilksLambda': self.wilks_lambda,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class EnrichmentResult(db.Model):
    __tablename__ = 'enrichment_results'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    task_id = db.Column(db.String(36), db.ForeignKey('analysis_tasks.id'), nullable=False)
    enrichment_type = db.Column(db.String(10), nullable=False)
    total_terms_analyzed = db.Column(db.Integer, default=0)
    significant_terms_count = db.Column(db.Integer, default=0)
    enrichment_data = db.Column(db.JSON)
    barplot_data = db.Column(db.JSON)
    network_data = db.Column(db.JSON)
    snp_gene_mapping = db.Column(db.JSON)
    candidate_genes = db.Column(db.JSON)
    notes = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    visualization_files = db.relationship('VisualizationFile', backref='enrichment_result', lazy=True, cascade='all, delete-orphan', foreign_keys='VisualizationFile.enrichment_result_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'type': self.enrichment_type,
            'totalTermsAnalyzed': self.total_terms_analyzed,
            'significantTermsCount': self.significant_terms_count,
            'enrichmentData': self.enrichment_data,
            'barplotData': self.barplot_data,
            'networkData': self.network_data,
            'snpGeneMapping': self.snp_gene_mapping,
            'candidateGenes': self.candidate_genes,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class FineMappingResult(db.Model):
    __tablename__ = 'finemapping_results'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    task_id = db.Column(db.String(36), db.ForeignKey('analysis_tasks.id'), nullable=False)
    region_chromosome = db.Column(db.String(20), nullable=False)
    region_start = db.Column(db.Integer, nullable=False)
    region_end = db.Column(db.Integer, nullable=False)
    n_variants = db.Column(db.Integer, nullable=False)
    lead_variant = db.Column(db.JSON)
    credible_sets = db.Column(db.JSON)
    posterior_inclusion_probs = db.Column(db.JSON)
    model_posteriors = db.Column(db.JSON)
    ld_matrix = db.Column(db.JSON)
    z_scores = db.Column(db.JSON)
    functional_scores = db.Column(db.JSON)
    manhattan_data = db.Column(db.JSON)
    credible_set_table = db.Column(db.JSON)
    notes = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    visualization_files = db.relationship('VisualizationFile', backref='finemapping_result', lazy=True, cascade='all, delete-orphan', foreign_keys='VisualizationFile.finemapping_result_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'taskId': self.task_id,
            'regionChromosome': self.region_chromosome,
            'regionStart': self.region_start,
            'regionEnd': self.region_end,
            'nVariants': self.n_variants,
            'leadVariant': self.lead_variant,
            'credibleSets': self.credible_sets,
            'posteriorInclusionProbs': self.posterior_inclusion_probs,
            'modelPosteriors': self.model_posteriors,
            'ldMatrix': self.ld_matrix,
            'zScores': self.z_scores,
            'functionalScores': self.functional_scores,
            'manhattanData': self.manhattan_data,
            'credibleSetTable': self.credible_set_table,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
