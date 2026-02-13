export type SourceMode = 'pubmed' | 'bioproject';

export type RelevanceLabel = 'alta' | 'media' | 'baja';
export type EvidenceLevel = 'directa' | 'indirecta' | 'débil';
export type ModelSource = 'ollama' | 'heuristic';

export interface Classification {
  relevance_label: RelevanceLabel;
  relevance_score: number;
  reason_short: string;
  tags: string[];
  evidence_level: EvidenceLevel;
  model_source: ModelSource;
}

export interface QueryGeneration {
  user_input: string;
  extracted: {
    organism?: string | null;
    organism_variants?: string[];
    strategies?: string[];
    tissues?: string[];
    conditions?: string[];
    free_terms?: string[];
  };
  synonyms?: {
    organism?: string[];
    strategies?: string[];
    tissues?: string[];
    conditions?: string[];
  };
  ncbi_query: string;
  ready_to_use: boolean;
  clarification_needed: boolean;
  clarification_message: string;
}

export interface MineroMetadata {
  status: 'success' | 'partial-success' | 'empty';
  query: string;
  source: SourceMode;
  total_results: number;
  classification_version: string;
  classification_timestamp: string;
  llm_runtime_available: boolean;
  model_default: ModelSource;
}

export interface PubmedResult {
  pmid: string;
  title: string;
  abstract: string;
  authors?: string[];
  year?: string;
  journal?: string;
  publication_type?: string;
  doi?: string;
  pmcid?: string;
  url?: string;
  fetched_at?: string;
  classification: Classification;
}

export interface BioprojectResult {
  bioproject: string;
  title: string;
  submission_date?: string;
  organism?: string;
  project_type?: string;
  description?: string;
  sra_experiments_count?: number;
  biosamples_count?: number;
  sra_runs_count?: number;
  sra_hierarchy?: Record<string, unknown>;
  publications_found?: number;
  search_method?: string;
  papers_summary?: string;
  error?: string;
  classification: Classification;
}

export type MineroResult = PubmedResult | BioprojectResult;

export interface MineroResponse {
  metadata: MineroMetadata;
  query_generation: QueryGeneration;
  results: MineroResult[];
}

export interface SearchPayload {
  natural_query: string;
  source: SourceMode;
  max_results: number;
  use_llm: boolean;
}

export type AppView = 'buscar' | 'resultados' | 'analisis' | 'ayuda';
export type AppStatus = 'idle' | 'loading' | 'success' | 'partial-success' | 'empty' | 'error';

export type ProgressState = 'pending' | 'in_progress' | 'completed' | 'failed';

export interface ProgressStep {
  id: number;
  label: string;
  detail: string;
  state: ProgressState;
}
