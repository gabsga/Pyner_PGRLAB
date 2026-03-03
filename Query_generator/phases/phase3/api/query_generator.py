"""
Pyner Phase 3 - Query Generator
================================
Generador de queries booleanas para NCBI a partir de lenguaje natural

Flujo:
1. Usuario input → Extraer términos
2. Validar términos contra KB (organismos, estrategias)
3. LLM genera query booleana optimizada
4. Retorna query lista para NCBI
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
import requests

logger = logging.getLogger(__name__)


# Dynamic translation dictionary (for common Spanish-English terms)
SPANISH_TO_EN = {
    # Tissues
    'raíz': 'root',
    'raices': 'root',
    'raíces': 'root',
    'hoja': 'leaf',
    'hojas': 'leaf',
    'flor': 'flower',
    'flores': 'flower',
    'tallo': 'stem',
    'tallos': 'stem',
    'semilla': 'seed',
    'semillas': 'seed',
    'fruto': 'fruit',
    'frutos': 'fruit',
    # Conditions
    'sequía': 'drought',
    'sequia': 'drought',
    'estrés': 'stress',
    'estres': 'stress',
    'infección': 'infection',
    'infeccion': 'infection',
    'enfermedad': 'disease',
    'crecimiento': 'growth',
    'desarrollo': 'development',
    # General keywords
    'genómico': 'genomic',
    'genómicos': 'genomic',
    'genomico': 'genomic',
    'genomicos': 'genomic',
    'expresión': 'expression',
    'expresion': 'expression',
    'mutación': 'mutation',
    'mutacion': 'mutation',
}


# Noise words to ignore in keywords and free terms
GLOBAL_NOISE_WORDS = {
    # English
    'find', 'targets', 'look', 'for', 'please', 'search', 'data', 'genomic', 
    'want', 'show', 'results', 'help', 'lookup', 'paper', 'papers', 'study',
    'related', 'about', 'information', 'describe', 'provide', 'list',
    # Spanish
    'encontrar', 'buscar', 'targets', 'para', 'por', 'favor', 'datos', 
    'genómicos', 'genomicos', 'quiero', 'mostrar', 'resultados', 'ayuda',
    'información', 'informacion', 'artículo', 'articulos', 'estudio',
    'relacionados', 'sobre', 'acerca', 'lista', 'gen', 'genes'
}


def _load_gene_aliases_from_tsv(tsv_path: Path) -> Dict[str, List[str]]:
    """
    Parse a gene annotation TSV file and return a gene aliases dict.
    
    Expected format (tab-separated, no header):
        Column 1: Gene ID (e.g., Solyc01g008950)
        Column 2: Symbol (e.g., SlCaM1)
        Column 3: Full name (e.g., Calmodulin 1)
    
    Returns:
        dict: {lowercase_term: [term1, term2, ...]}
    """
    from collections import defaultdict
    import csv as csv_mod
    
    gene_groups = defaultdict(set)
    try:
        with open(tsv_path, 'r', encoding='utf-8') as f:
            reader = csv_mod.reader(f, delimiter='\t')
            for row in reader:
                if len(row) < 3:
                    continue
                gene_id = row[0].strip()
                symbol = row[1].strip()
                name = row[2].strip()
                if not gene_id or not symbol:
                    continue
                gene_groups[gene_id].add(gene_id)
                gene_groups[gene_id].add(symbol)
                if name and name != symbol:
                    gene_groups[gene_id].add(name)
    except Exception as e:
        logger.warning(f"⚠️ Error loading gene aliases from {tsv_path}: {e}")
        return {}
    
    aliases = {}
    for gene_id, terms in gene_groups.items():
        term_list = sorted(terms)
        for term in terms:
            key = term.lower()
            if key not in aliases:
                aliases[key] = term_list
            else:
                existing = set(aliases[key])
                existing.update(term_list)
                aliases[key] = sorted(existing)
    
    return aliases


def load_technical_vocabulary(cache_dir: Path) -> Dict:
    """Load technical vocabulary from JSON file and gene alias TSV files"""
    vocab_path = cache_dir / "technical_vocabulary.json"
    vocab = None
    if vocab_path.exists():
        try:
            with open(vocab_path, 'r', encoding='utf-8') as f:
                vocab = json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Error loading technical vocabulary: {e}")
    
    if vocab is None:
        vocab = {
            "plant_tissues": [],
            "animal_tissues": [],
            "generic_tissues": [],
            "process_keywords": [],
            "organism_markers": {"plant": {"markers": []}, "animal": {"markers": []}, 
                                "microbe": {"markers": []}, "virus": {"markers": []}},
            "organism_aliases": {},
            "strategy_keywords": {},
            "gene_aliases": {}
        }
    
    # Load organism-specific gene alias files (gene_aliases_*.tab)
    # Search in support_dictionary and project root
    gene_aliases = vocab.get("gene_aliases", {})
    search_dirs = [cache_dir]
    
    # Also search in the project root (4 levels up from support_dictionary)
    project_root = cache_dir.parent.parent.parent.parent
    if project_root.exists() and project_root != cache_dir:
        search_dirs.append(project_root)
    
    for search_dir in search_dirs:
        for tsv_file in sorted(search_dir.glob("gene_aliases_*.tab")):
            logger.info(f"📖 Loading gene aliases from: {tsv_file.name}")
            organism_aliases = _load_gene_aliases_from_tsv(tsv_file)
            gene_aliases.update(organism_aliases)
            logger.info(f"   ✓ Loaded {len(organism_aliases)} gene alias entries")
    
    vocab["gene_aliases"] = gene_aliases
    return vocab


class KnowledgeBaseValidator:
    """Validador de términos contra el Knowledge Base"""
    
    def __init__(self, kb_path: Path, query_cache_path: Optional[Path] = None, cache_dir: Optional[Path] = None):
        self.kb_path = kb_path
        self.query_cache_path = query_cache_path
        self.cache_dir = cache_dir or kb_path.parent.parent / "support_dictionary"
        self.organisms = {}
        self.strategies = set()
        self.sources = set()
        self.selections = set()
        self.diseases = set()
        self.gene_aliases = {}
        
        # Load technical vocabulary
        self.vocab = load_technical_vocabulary(self.cache_dir)
        self.plant_tissues = set(self.vocab.get("plant_tissues", []))
        self.animal_tissues = set(self.vocab.get("animal_tissues", []))
        self.generic_tissues = set(self.vocab.get("generic_tissues", []))
        self.process_keywords = set(self.vocab.get("process_keywords", []))
        self.gene_aliases = self.vocab.get("gene_aliases", {})
        self.organism_aliases = self.vocab.get("organism_aliases", {})
        self.strategy_keywords = self.vocab.get("strategy_keywords", {})
        
        # Extract organism markers by domain
        markers = self.vocab.get("organism_markers", {})
        self.plant_markers = set(markers.get("plant", {}).get("markers", []))
        self.animal_markers = set(markers.get("animal", {}).get("markers", []))
        self.microbe_markers = set(markers.get("microbe", {}).get("markers", []))
        self.virus_markers = set(markers.get("virus", {}).get("markers", []))
        
        self._load_kb()
    
    def _load_kb(self):
        """Cargar Knowledge Base"""
        try:
            # Cargar KB principal (stage3)
            with open(self.kb_path, 'r') as f:
                kb = json.load(f)
            
            # Cargar organismos (con nombres y sinónimos)
            self.organisms = {org.lower(): org for org in kb.get('organisms', {}).keys()}
            
            # Cargar estrategias (puede ser dict o list en KB reducida)
            strategies = kb.get('strategies', {})
            if isinstance(strategies, dict):
                self.strategies = set(strategies.keys())
            else:
                self.strategies = set(strategies)

            # Cargar sources y selections (no existen en KB reducida)
            sources = kb.get('sources', {})
            selections = kb.get('selections', {})
            self.sources = set(sources.keys()) if isinstance(sources, dict) else set()
            self.selections = set(selections.keys()) if isinstance(selections, dict) else set()
            
            # Intentar cargar KB extendido de Stage 2 (mas organismos)
            stage2_kb = self.kb_path.parent / "stage2_knowledge_base.json"
            if stage2_kb.exists():
                try:
                    with open(stage2_kb, 'r') as f:
                        kb2 = json.load(f)
                    for org_name in kb2.get('organisms', {}).keys():
                        self.organisms.setdefault(org_name.lower(), org_name)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load stage2 KB: {e}")

            # Cargar query_cache.json (organismos y enfermedades)
            if self.query_cache_path and self.query_cache_path.exists():
                try:
                    with open(self.query_cache_path, 'r') as f:
                        cache = json.load(f)
                    for item in cache.get('queries', []):
                        if item.get('type') == 'organism' and item.get('organism'):
                            org = item['organism']
                            self.organisms.setdefault(org.lower(), org)
                        if item.get('type') == 'disease' and item.get('disease'):
                            self.diseases.add(item['disease'].lower())
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load query cache: {e}")

            logger.info(f"✅ KB loaded: {len(self.organisms)} organisms, {len(self.strategies)} strategies")
            
        except Exception as e:
            logger.error(f"❌ Error loading KB: {e}")
    
    def find_organism(self, text: str) -> Optional[str]:
        """Buscar organismo en el texto (retorna 1 solo)"""
        text_lower = text.lower()
        
        # Búsqueda exacta primero
        for org_key, org_name in self.organisms.items():
            if org_key in text_lower:
                return org_name
        
        # Búsqueda fuzzy (palabras clave)
        words = text_lower.split()
        for org_key, org_name in self.organisms.items():
            org_words = org_key.split()
            if len(org_words) >= 2:  # Nombres científicos (genus species)
                if org_words[0] in words and org_words[1] in words:
                    return org_name

        # Alias comunes (ej. arabidopsis -> Arabidopsis thaliana)
        for alias, canonical in self.organism_aliases.items():
            if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                if canonical.lower() in self.organisms:
                    return self.organisms[canonical.lower()]
                return canonical
        
        return None
    
    def find_organism_variants(self, text: str) -> List[str]:
        """Buscar TODAS las variantes de un organismo en la KB
        
        Ej: 'mouse' -> ['Mus musculus', 'Mus musculus musculus', 'Mus musculus castaneus']
        """
        text_lower = text.lower()
        variants = []
        
        # Primero buscar si hay alias
        canonical = None
        for alias, org in self.organism_aliases.items():
            if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                canonical = org
                break
        
        # Si no hay alias, buscar directamente en texto
        if not canonical:
            # Buscar cualquier match en organismos
            for org_key, org_name in self.organisms.items():
                if org_key in text_lower:
                    canonical = org_name
                    break
        
        if canonical:
            # Buscar todas las variantes EXACTAS del canonical
            # Ej: "Mus musculus" debe encontrar:
            #   - "Mus musculus" (exacto)
            #   - "Mus musculus musculus" (subspecie)
            #   - "Mus musculus castaneus" (subspecie)
            # NO debe encontrar: "Mustela" (otro género)
            canonical_words = canonical.lower().split()
            if len(canonical_words) >= 2:
                # Buscar genus + species exacto
                genus_species = ' '.join(canonical_words[:2])
                for org_key, org_name in self.organisms.items():
                    # Match: debe comenzar con "genus species"
                    if org_key.startswith(genus_species) and org_name not in variants:
                        variants.append(org_name)
            elif len(canonical_words) == 1:
                # Solo género (menos común, pero buscar exacto)
                genus = canonical_words[0]
                for org_key, org_name in self.organisms.items():
                    if org_key.split()[0] == genus and org_name not in variants:
                        variants.append(org_name)
        
        return variants

    def find_genes(self, text: str) -> Dict[str, List[str]]:
        """Buscar genes y sus alias en el texto"""
        text_lower = text.lower()
        found = {}
        for gene_key, aliases in self.gene_aliases.items():
            # Match gene key or any of its aliases
            gene_terms = [gene_key] + aliases
            for term in gene_terms:
                if re.search(rf"\b{re.escape(term.lower())}\b", text_lower):
                    if gene_key not in found:
                        found[gene_key] = aliases
                    break
        return found

    def find_tissues(self, text: str, tissue_vocab: Dict[str, str]) -> List[str]:
        text_lower = text.lower()
        found = []
        for key, canonical in tissue_vocab.items():
            if re.search(rf"\b{re.escape(key)}\b", text_lower):
                if canonical not in found:
                    found.append(canonical)
        return found

    def find_conditions(self, text: str, condition_vocab: Dict[str, str]) -> List[str]:
        text_lower = text.lower()
        found = []
        for key, canonical in condition_vocab.items():
            if re.search(rf"\b{re.escape(key)}\b", text_lower):
                if canonical not in found:
                    found.append(canonical)
        return found
    
    def find_strategies(self, text: str) -> List[str]:
        """Buscar estrategias en el texto"""
        text_lower = text.lower()
        found = []
        
        # Keywords desde vocabulario tecnico
        for strategy, keywords in self.strategy_keywords.items():
            if strategy not in self.strategies:
                continue
            for term in keywords:
                if term in text_lower:
                    if strategy not in found:
                        found.append(strategy)
                    break
        
        # Fallback: mapeo basico si no hay vocab
        if not found:
            strategy_mappings = {
                'rna-seq': 'RNA-Seq',
                'rnaseq': 'RNA-Seq',
                'rna seq': 'RNA-Seq',
                'transcriptome': 'RNA-Seq',
                'wgs': 'WGS',
                'whole genome': 'WGS',
                'genome sequencing': 'WGS',
                'chip-seq': 'ChIP-Seq',
                'chipseq': 'ChIP-Seq',
                'amplicon': 'AMPLICON',
                '16s': 'AMPLICON',
                'metagenome': 'WGS',
                'exome': 'WXS',
            }
            
            for term, strategy in strategy_mappings.items():
                if term in text_lower and strategy in self.strategies:
                    if strategy not in found:
                        found.append(strategy)
        
        return found
    
    def extract_free_terms(
        self,
        text: str,
        organism: str = None,
        strategies: List[str] = None,
        tissues: List[str] = None,
        conditions: List[str] = None,
        organism_synonyms: List[str] = None,
        strategy_synonyms: List[str] = None,
        tissue_synonyms: List[str] = None,
        condition_synonyms: List[str] = None,
        gene_synonyms: List[str] = None
    ) -> List[str]:
        """Extraer términos libres (no organismos ni estrategias ni genes)"""
        terms = []
        organism_synonyms = organism_synonyms or []
        strategy_synonyms = strategy_synonyms or []
        tissue_synonyms = tissue_synonyms or []
        condition_synonyms = condition_synonyms or []
        gene_synonyms = gene_synonyms or []
        
        # Remover organismo del texto
        text_clean = text
        if organism:
            text_clean = text_clean.replace(organism, '')
        
        # Remover sinónimos del organismo
        for syn in organism_synonyms:
            text_clean = text_clean.replace(syn, '')
            text_clean = text_clean.replace(syn.lower(), '')

        # Remover estrategias
        if strategies:
            for strat in strategies:
                text_clean = text_clean.replace(strat, '')
                text_clean = text_clean.replace(strat.lower(), '')

        # Remover sinónimos de estrategias
        for syn in strategy_synonyms:
            text_clean = text_clean.replace(syn, '')
            text_clean = text_clean.replace(syn.lower(), '')

        if tissues:
            for tissue in tissues:
                text_clean = text_clean.replace(tissue, '')
                text_clean = text_clean.replace(tissue.lower(), '')

        # Remover sinónimos de tejidos
        for syn in tissue_synonyms:
            text_clean = text_clean.replace(syn, '')
            text_clean = text_clean.replace(syn.lower(), '')

        if conditions:
            for cond in conditions:
                text_clean = text_clean.replace(cond, '')
                text_clean = text_clean.replace(cond.lower(), '')

        # Remover sinónimos de condiciones
        for syn in condition_synonyms:
            text_clean = text_clean.replace(syn, '')
            text_clean = text_clean.replace(syn.lower(), '')
        
        # Remover sinónimos de genes
        for syn in gene_synonyms:
            text_clean = text_clean.replace(syn, '')
            text_clean = text_clean.replace(syn.lower(), '')
        
        # Extraer palabras clave (usando GLOBAL_NOISE_WORDS como base)
        stopwords = {
            'and', 'or', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'using', 'studies', 'study', 'research', 'analysis', 'sequencing',
            'sequence', 'whole', 'single', 'cell', 'data', 'information', 'para',
            'de', 'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas'
        }
        stopwords.update(GLOBAL_NOISE_WORDS)
        words = re.findall(r'\b\w+\b', text_clean.lower())
        
        for word in words:
            if len(word) > 3 and word not in stopwords:
                if word not in terms:
                    terms.append(word)
        
        return terms


class NCBIQueryBuilder:
    """Constructor de queries booleanas para NCBI"""
    
    def __init__(self, ollama_client=None):
        self.ollama_client = ollama_client
    
    def build_query(
        self,
        organism: str = None,
        organisms: List[str] = None,
        organism_synonyms: List[str] = None,
        strategies: List[str] = None,
        strategy_synonyms: List[str] = None,
        free_terms: List[str] = None,
        tissues: List[str] = None,
        conditions: List[str] = None,
        tissue_synonyms: List[str] = None,
        condition_synonyms: List[str] = None,
        genes: Dict[str, List[str]] = None,
        use_llm: bool = True
    ) -> str:
        """
        Construir query booleana para NCBI
        
        Args:
            organism: Nombre del organismo (single)
            organisms: Lista de variantes del organismo (para query amplio)
            strategies: Lista de estrategias de secuenciación
            free_terms: Términos libres adicionales
            use_llm: Si usar LLM para optimizar
        
        Returns:
            Query booleana lista para NCBI
        """
        
        # Construir query básica
        query_parts = []
        free_terms = free_terms or []
        tissues = tissues or []
        conditions = conditions or []
        strategies = strategies or []
        organism_synonyms = organism_synonyms or []
        strategy_synonyms = strategy_synonyms or []
        tissue_synonyms = tissue_synonyms or []
        condition_synonyms = condition_synonyms or []
        
        # Organismos (priorizar lista de variantes)
        org_clause = None
        if organisms and len(organisms) > 0:
            if len(organisms) == 1:
                org_clause = f'"{organisms[0]}"[Organism]'
            else:
                org_query = ' OR '.join([f'"{org}"[Organism]' for org in organisms])
                org_clause = f'({org_query})'
        elif organism:
            org_clause = f'"{organism}"[Organism]'

        if org_clause:
            if organism_synonyms:
                syn_query = ' OR '.join([f'"{s}"[All Fields]' for s in organism_synonyms])
                org_clause = f'({org_clause} OR {syn_query})'
            query_parts.append(org_clause)
        
        # Deduplicar y excluir terminos ya cubiertos por categorias
        exclude_terms = set()
        for term in strategies + strategy_synonyms + tissues + tissue_synonyms + conditions + condition_synonyms:
            if term:
                exclude_terms.add(term.lower())
        
        # Add generic noise words to exclude
        for word in GLOBAL_NOISE_WORDS:
            exclude_terms.add(word)

        filtered_free = []
        for term in free_terms:
            if term and term.lower() not in exclude_terms and term not in filtered_free:
                filtered_free.append(term)

        # Estrategias (usar All Fields para ampliar match)
        combined_strategy_terms = []
        for term in strategies + strategy_synonyms:
            if term and term not in combined_strategy_terms:
                combined_strategy_terms.append(term)
        if combined_strategy_terms:
            if len(combined_strategy_terms) == 1:
                query_parts.append(f'"{combined_strategy_terms[0]}"[All Fields]')
            else:
                strat_query = ' OR '.join([f'"{s}"[All Fields]' for s in combined_strategy_terms])
                query_parts.append(f'({strat_query})')

        # Tejidos
        combined_tissue_terms = []
        for term in tissues + tissue_synonyms:
            if term and term not in combined_tissue_terms:
                combined_tissue_terms.append(term)
        if combined_tissue_terms:
            if len(combined_tissue_terms) == 1:
                query_parts.append(f'"{combined_tissue_terms[0]}"[All Fields]')
            else:
                tissue_query = ' OR '.join([f'"{t}"[All Fields]' for t in combined_tissue_terms])
                query_parts.append(f'({tissue_query})')

        # Condiciones
        combined_condition_terms = []
        for term in conditions + condition_synonyms:
            if term and term not in combined_condition_terms:
                combined_condition_terms.append(term)
        if combined_condition_terms:
            if len(combined_condition_terms) == 1:
                query_parts.append(f'"{combined_condition_terms[0]}"[All Fields]')
            else:
                cond_query = ' OR '.join([f'"{c}"[All Fields]' for c in combined_condition_terms])
                query_parts.append(f'({cond_query})')

        # Genes — deduplicate: multiple keys may point to the same gene alias set
        seen_gene_sets = set()
        for gene_key, aliases in genes.items():
            if aliases:
                # Use frozenset to identify unique gene groups
                alias_key = frozenset(a.lower() for a in aliases)
                if alias_key in seen_gene_sets:
                    continue  # Skip duplicate gene group
                seen_gene_sets.add(alias_key)
                gene_query = ' OR '.join([f'"{a}"[All Fields]' for a in aliases])
                query_parts.append(f'({gene_query})')
            else:
                if gene_key.lower() not in seen_gene_sets:
                    seen_gene_sets.add(frozenset([gene_key.lower()]))
                    query_parts.append(f'"{gene_key}"[All Fields]')

        # Términos libres
        for term in filtered_free:
            query_parts.append(f'"{term}"[All Fields]')
        
        # Unir con AND
        basic_query = ' AND '.join(query_parts)
        
        # Optimizar con LLM si está disponible
        if use_llm and self.ollama_client:
            try:
                # Solo validar y limpiar, no reinventar la query
                cleaned = self._clean_query_with_llm(basic_query)
                return cleaned
            except Exception as e:
                logger.warning(f"⚠️ LLM cleanup failed, using basic query: {e}")
                return basic_query
        
        return basic_query
    
    def _clean_query_with_llm(self, basic_query: str) -> str:
        """Validar que la query sea correcta"""
        # La query básica ya está bien formada
        return basic_query
    
    def _optimize_with_llm(
        self,
        basic_query: str,
        organism: str,
        strategies: List[str],
        free_terms: List[str],
        tissues: List[str],
        conditions: List[str]
    ) -> str:
        """Legacy method - kept for compatibility"""
        return basic_query


class QueryGeneratorService:
    """Servicio principal de generación de queries"""
    
    def __init__(self, kb_path: Path, ollama_client=None, query_cache_path: Optional[Path] = None, cache_dir: Optional[Path] = None):
        self.validator = KnowledgeBaseValidator(kb_path, query_cache_path=query_cache_path, cache_dir=cache_dir)
        self.query_builder = NCBIQueryBuilder(ollama_client)
        self.ollama_client = ollama_client
        self.tissue_vocab = self._build_tissue_vocab()
        self.condition_vocab = self._build_condition_vocab()

    def _build_tissue_vocab(self) -> Dict[str, str]:
        vocab = {}
        # Use loaded vocabularies from validator
        all_tissues = self.validator.plant_tissues | self.validator.animal_tissues | self.validator.generic_tissues
        for term in all_tissues:
            vocab[term] = term
        # Add Spanish translations
        for es, en in SPANISH_TO_EN.items():
            if en in self.validator.plant_tissues | self.validator.generic_tissues:
                vocab[es] = en
        return vocab

    def _build_condition_vocab(self) -> Dict[str, str]:
        vocab = {term: term for term in self.validator.process_keywords}
        # Añadir enfermedades del cache
        for disease in self.validator.diseases:
            vocab[disease] = disease
        return vocab

    def _collect_organism_synonyms(self, organism: Optional[str]) -> List[str]:
        if not organism:
            return []
        org_lower = organism.lower()
        synonyms = []
        
        # Buscar aliases exactos primero
        for alias, canonical in self.validator.organism_aliases.items():
            if canonical.lower() == org_lower and alias.lower() != org_lower:
                if alias not in synonyms:
                    synonyms.append(alias)
        
        # Si el organismo es un género (como "Vitis"), también buscar aliases de especies del mismo género
        # que apunten a miembros de ese género (ej: "Vitis vinifera")
        if ' ' not in org_lower:  # Es probablemente un género (single word)
            for alias, canonical in self.validator.organism_aliases.items():
                # Buscar si el canonical (ej: "Vitis vinifera") empieza con el organismo (ej: "Vitis")
                if canonical.lower().startswith(org_lower + ' ') or canonical.lower().startswith(org_lower):
                    if alias.lower() != org_lower and alias not in synonyms:
                        synonyms.append(alias)
        
        return synonyms

    def _collect_strategy_synonyms(self, strategies: List[str]) -> List[str]:
        synonyms = []
        if not strategies:
            return synonyms
        for strategy in strategies:
            for term in self.validator.strategy_keywords.get(strategy, []):
                if term.lower() == strategy.lower():
                    continue
                if term not in synonyms:
                    synonyms.append(term)
        return synonyms

    def _collect_tissue_synonyms(self, tissues: List[str]) -> List[str]:
        synonyms = []
        if not tissues:
            return synonyms
        for tissue in tissues:
            for key, canonical in self.tissue_vocab.items():
                if canonical == tissue and key != tissue:
                    if key not in synonyms:
                        synonyms.append(key)
        return synonyms

    def _collect_condition_synonyms(self, conditions: List[str]) -> List[str]:
        synonyms = []
        if not conditions:
            return synonyms
        for es, en in SPANISH_TO_EN.items():
            if en in conditions and es not in synonyms:
                synonyms.append(es)

        drought_terms = {
            "drought",
            "drought stress",
            "water deficit",
            "water stress",
            "water deprivation",
            "water scarcity",
            "dehydration",
            "deficit hidrico",
            "deficit hídrico",
            "sequía",
            "sequia"
        }
        if "drought" in conditions:
            for term in self.validator.process_keywords:
                if term.lower() in drought_terms and term not in synonyms:
                    synonyms.append(term)
        return synonyms

    def _normalize_terms(self, terms: List[str]) -> List[str]:
        normalized = []
        for term in terms:
            if not term:
                continue
            term_lower = term.lower()
            # Buscar traducción con lowercase
            translated = SPANISH_TO_EN.get(term_lower, None)
            if translated:
                if translated not in normalized:
                    normalized.append(translated)
            else:
                # Si no está en el diccionario, usar como está o intenta con LLM si es corta
                if self.ollama_client and len(term_lower) > 2:
                    try:
                        # Quick LLM translation for unknown terms
                        prompt = f'Translate this word to English (return only the word): {term}'
                        translated_llm = self.ollama_client.generate(prompt).strip().lower()
                        if translated_llm and len(translated_llm) < 20:  # Validar que es una palabra
                            if translated_llm not in normalized:
                                normalized.append(translated_llm)
                        else:
                            # Fallback a como está
                            if term_lower not in normalized:
                                normalized.append(term_lower)
                    except:
                        if term_lower not in normalized:
                            normalized.append(term_lower)
                else:
                    # Sin LLM, usar como está
                    if term_lower not in normalized:
                        normalized.append(term_lower)
        return normalized

    def _classify_organism_domain(self, organism: str) -> str:
        if not organism:
            return 'unknown'

        org_lower = organism.lower()

        if self.ollama_client:
            try:
                prompt = (
                    "Classify this organism into one of: plant, animal, microbe, virus, unknown. "
                    "Return ONLY the label. Organism: " + organism
                )
                label = self.ollama_client.generate(prompt).strip().lower()
                if label in {'plant', 'animal', 'microbe', 'virus'}:
                    return label
            except Exception:
                pass

        if any(marker in org_lower for marker in self.validator.plant_markers):
            return 'plant'
        if any(marker in org_lower for marker in self.validator.animal_markers):
            return 'animal'
        if any(marker in org_lower for marker in self.validator.microbe_markers):
            return 'microbe'
        if any(marker in org_lower for marker in self.validator.virus_markers):
            return 'virus'

        return 'unknown'

    def _tissue_domain(self, tissue: str) -> str:
        t = tissue.lower()
        if t in self.validator.plant_tissues:
            return 'plant'
        if t in self.validator.animal_tissues:
            return 'animal'
        return 'generic'

    def _extract_with_llm(self, user_input: str) -> Dict[str, List[str]]:
        if not self.ollama_client:
            return {}

        prompt = f"""Extract and categorize scientific query terms. Accept Spanish or English input. ALWAYS output ENGLISH terms.

User Query: "{user_input}"

Extract these fields and return ONLY valid JSON (no markdown, no text):
- organism: (string) scientific name or null (e.g., "Arabidopsis thaliana")
- genes: (list) specific gene names (e.g., "myb60", "brca1")
- tissues: (list) body parts or tissues in ENGLISH
- conditions: (list) stress/disease/process in ENGLISH  
- strategies: (list) sequencing methods (RNA-Seq, ChIP-Seq, WGS, etc.)
- keywords: (list) other important scientific terms in ENGLISH

Strict Rules:
1. TRANSLATE ALL Spanish to ENGLISH in all outputs (except gene names)
2. Use standardized scientific terms (e.g., "raíz"→"root", "sequía"→"drought")
3. IGNORE generic filler words like "find", "search", "lookup", "targets", "look", "for", "please", "want", "help", "show", "data", "genomic", "results"
4. Do NOT invent organisms - leave null if unsure
5. Tissues: leaf, root, flower, stem, liver, brain, heart, kidney, etc.
6. Conditions: drought, stress, disease, heat, cold, growth, infection, etc.
7. Return ONLY valid JSON, no extra text

Example Input: "quiero encontrar los targets de arabidopsis en sequía para el gen myb60"
Example Output: {{"organism": "Arabidopsis thaliana", "genes": ["myb60"], "tissues": [], "conditions": ["drought"], "strategies": [], "keywords": []}}"""

        try:
            raw = self.ollama_client.generate(prompt)
            raw = raw.strip()
            # Extraer JSON (permite markdown ```json ... ``` o JSON directo)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                logger.warning(f"⚠️ LLM extraction failed - no JSON found in: {raw[:100]}")
                return {}
            
            try:
                data = json.loads(match.group(0))
                result = {
                    'organism': data.get('organism'),
                    'genes': [g for g in (data.get('genes') or [])],
                    'tissues': [t.lower() if isinstance(t, str) else t for t in (data.get('tissues') or [])],
                    'conditions': [c.lower() if isinstance(c, str) else c for c in (data.get('conditions') or [])],
                    'strategies': [s for s in (data.get('strategies') or [])],
                    'keywords': [k.lower() if isinstance(k, str) else k for k in (data.get('keywords') or [])],
                }
                # Final check for noise in all categorical fields that might contain filler
                result['keywords'] = [k for k in result['keywords'] if k.lower() not in GLOBAL_NOISE_WORDS]
                
                logger.info(f"✅ LLM extraction: {result}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ LLM JSON parse failed: {e}")
                return {}
        except Exception as e:
            logger.warning(f"⚠️ LLM extraction error: {e}")
            return {}
    
    def refine_query(self, previous_result: Dict, feedback: str) -> Dict:
        """Refine extraction results based on user feedback"""
        logger.info(f"🔄 Refining query with feedback: {feedback}")
        
        current_extracted = previous_result.get('extracted', {})
        
        prompt = f"""You are refining biological search results based on user feedback.
Current Extraction:
{json.dumps(current_extracted, indent=2)}

User Feedback: "{feedback}"

ADJUST the extraction based on the feedback and return ONLY the updated JSON.
Rules:
1. Maintain the JSON structure (organism, genes, tissues, conditions, strategies, keywords)
2. If the user asks to remove a word, remove it from the corresponding list.
3. If the user asks to add a term, translate it to English and add it to the correct category.
4. Keep other terms that were not mentioned in feedback.
5. NO noise words like "find", "targets", "for".
6. Return ONLY valid JSON.

Updated JSON:"""
        
        try:
            raw = self.ollama_client.generate(prompt).strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return previous_result # Return original if LLM failed
                
            updated_data = json.loads(match.group(0))
            
            # Apply GLOBAL_NOISE_WORDS to the updated JSON as well
            if 'keywords' in updated_data:
                updated_data['keywords'] = [k for k in updated_data['keywords'] if k.lower() not in GLOBAL_NOISE_WORDS]
            
            # Re-run full generation pipeline with these manual overrides
            return self.generate_query(
                previous_result['user_input'], 
                use_llm=True, 
                overrides=updated_data
            )
        except Exception as e:
            logger.error(f"⚠️ Query refinement failed: {e}")
            return previous_result

    def generate_query(self, user_input: str, use_llm: bool = True, overrides: Dict = None) -> Dict:
        """
        Generar query NCBI desde input en lenguaje natural
        
        Args:
            user_input: Texto del usuario
            use_llm: Si usar LLM para optimizar
        
        Returns:
            Dict con query y metadata
        """
        
        logger.info(f"📝 Processing user input: {user_input}")
        
        # Paso 1: Extraer con LLM (si esta disponible)
        if use_llm and not overrides:
            llm_data = self._extract_with_llm(user_input)
        else:
            llm_data = overrides or {}

        # Paso 2: Buscar organismo con todas sus variantes
        organism_variants = self.validator.find_organism_variants(user_input)
        
        # Si no encuentra variantes en input, buscar en lo que extrajo el LLM
        if not organism_variants and llm_data.get('organism'):
            organism_variants = self.validator.find_organism_variants(llm_data['organism'])
        
        # También buscar en keywords del LLM (ej: "mouse" puede estar ahí)
        if not organism_variants and llm_data.get('keywords'):
            for keyword in llm_data['keywords']:
                variants = self.validator.find_organism_variants(keyword)
                if variants:
                    organism_variants = variants
                    break
        
        organism = organism_variants[0] if organism_variants else None
        logger.info(f"🔍 Organism variants found: {organism_variants or 'None'}")
        if len(organism_variants) > 1:
            logger.info(f"   Using all {len(organism_variants)} variants for broad search")

        # Paso 3: Buscar estrategias
        strategies = self.validator.find_strategies(user_input)
        if llm_data.get('strategies'):
            for s in llm_data['strategies']:
                if s in self.validator.strategies and s not in strategies:
                    strategies.append(s)
        logger.info(f"🔍 Strategies found: {strategies or 'None'}")

        # Paso 4: Buscar tejidos y condiciones
        tissues = self.validator.find_tissues(user_input, self.tissue_vocab)
        conditions = self.validator.find_conditions(user_input, self.condition_vocab)
        llm_tissues = llm_data.get('tissues', []) if use_llm else []
        llm_conditions = llm_data.get('conditions', []) if use_llm else []
        
        # Fusionar con LLM si está disponible
        for t in llm_tissues:
            if t and t not in tissues:
                tissues.append(t)
        for c in llm_conditions:
            if c and c not in conditions:
                conditions.append(c)

        tissues = self._normalize_terms(tissues)
        conditions = self._normalize_terms(conditions)

        logger.info(f"🔍 Tissues found: {tissues or 'None'}")
        logger.info(f"🔍 Conditions found: {conditions or 'None'}")

        # Paso 4.2: Buscar genes
        genes = self.validator.find_genes(user_input)
        llm_genes = llm_data.get('genes', []) if use_llm else []
        for g in llm_genes:
            g_lower = g.lower()
            if g_lower not in genes:
                # Si el LLM encontró un gen que no está en el dict, añadirlo sin alias
                genes[g_lower] = []
        logger.info(f"🔍 Genes found: {list(genes.keys()) or 'None'}")

        # Paso 4.5: Recolectar sinónimos ANTES de extraer términos libres
        organism_synonyms = self._collect_organism_synonyms(organism)
        strategy_synonyms = self._collect_strategy_synonyms(strategies)
        tissue_synonyms = self._collect_tissue_synonyms(tissues)
        condition_synonyms = self._collect_condition_synonyms(conditions)
        
        gene_synonyms = []
        for aliases in genes.values():
            for alias in aliases:
                if alias not in gene_synonyms:
                    gene_synonyms.append(alias)

        # Paso 5: Extraer términos libres (eliminando también sinónimos)
        free_terms = self.validator.extract_free_terms(
            user_input, organism, strategies, tissues, conditions,
            organism_synonyms=organism_synonyms,
            strategy_synonyms=strategy_synonyms,
            tissue_synonyms=tissue_synonyms,
            condition_synonyms=condition_synonyms,
            gene_synonyms=gene_synonyms
        )
        # Traducir y usar el set de keywords del LLM para deduplicar
        free_terms = self._normalize_terms(free_terms)
        llm_keywords = set(llm_data.get('keywords', [])) if use_llm else set()
        
        # Crear un conjunto de términos a excluir (organismos y sus sinónimos)
        exclude_llm_keywords = set()
        
        # Excluir organismos y sus sinónimos
        if organism:
            exclude_llm_keywords.add(organism.lower())
        for syn in organism_synonyms:
            exclude_llm_keywords.add(syn.lower())
        
        # Excluir estrategias y sus sinónimos
        for strat in strategies:
            exclude_llm_keywords.add(strat.lower())
        for syn in strategy_synonyms:
            exclude_llm_keywords.add(syn.lower())
        
        # Excluir tejidos identificados y sus sinónimos
        for tissue in tissues:
            exclude_llm_keywords.add(tissue.lower())
        for syn in tissue_synonyms:
            exclude_llm_keywords.add(syn.lower())
        
        # Excluir también TODOS los tejidos conocidos del vocabulario
        for tissue in self.validator.plant_tissues | self.validator.animal_tissues | self.validator.generic_tissues:
            if tissue:
                exclude_llm_keywords.add(tissue.lower())
        
        # Excluir condiciones identificadas y sus sinónimos
        for cond in conditions:
            exclude_llm_keywords.add(cond.lower())
        for syn in condition_synonyms:
            exclude_llm_keywords.add(syn.lower())
        
        # Excluir también TODOS los process keywords conocidos (condiciones/procesos)
        for process in self.validator.process_keywords:
            if process:
                exclude_llm_keywords.add(process.lower())
        
        # Excluir TODAS las estrategias conocidas (para evitar variaciones)
        for strat in self.validator.strategies:
            if strat:
                exclude_llm_keywords.add(strat.lower())
        
        # Excluir genes identificados y sus sinónimos
        for gene in genes.keys():
            exclude_llm_keywords.add(gene.lower())
        for syn in gene_synonyms:
            exclude_llm_keywords.add(syn.lower())

        # Excluir tambíen TODOS los alias de organismos (términos que apuntan a organismos)
        for alias in self.validator.organism_aliases.keys():
            if alias:
                exclude_llm_keywords.add(alias.lower())
        
        # Excluir GLOBAL_NOISE_WORDS para asegurar que no se filtren
        for noise in GLOBAL_NOISE_WORDS:
            exclude_llm_keywords.add(noise.lower())
        
        # No incluir keywords que el LLM ya extrajo o que pertenecen a categorias conocidas
        filtered_keywords = []
        for kw in llm_keywords:
            if kw and kw.lower() not in exclude_llm_keywords:
                filtered_keywords.append(kw)
        llm_keywords = set(filtered_keywords)
        
        # Filtrar free_terms contra keywords del LLM y contra el set de exclusión completo
        filtered_free_terms = []
        for t in free_terms:
            if t and t.lower() not in exclude_llm_keywords:
                if t not in llm_keywords and t.lower() not in {kw.lower() for kw in llm_keywords}:
                    filtered_free_terms.append(t)
        free_terms = filtered_free_terms
        
        if organism and free_terms:
            org_lower = organism.lower()
            filtered = []
            for term in free_terms:
                if term in org_lower:
                    continue
                alias_match = self.validator.organism_aliases.get(term)
                if alias_match and alias_match.lower() == org_lower:
                    continue
                filtered.append(term)
            free_terms = filtered
        logger.info(f"🔍 Free terms: {free_terms or 'None'}")

        # Validacion de compatibilidad (planta vs tejido animal)
        if organism and tissues:
            domain = self._classify_organism_domain(organism)
            for tissue in tissues:
                t_domain = self._tissue_domain(tissue)
                if domain == 'plant' and t_domain == 'animal':
                    clarification = (
                        "Detected a plant organism with an animal tissue. "
                        "Please review the organism or tissue selection."
                    )
                    return {
                        'user_input': user_input,
                        'extracted': {
                            'organism': organism,
                            'strategies': strategies,
                            'tissues': tissues,
                            'conditions': conditions,
                            'free_terms': free_terms
                        },
                        'ncbi_query': "",
                        'ready_to_use': False,
                        'clarification_needed': True,
                        'clarification_message': clarification
                    }
                if domain == 'animal' and t_domain == 'plant':
                    clarification = (
                        "Detected an animal organism with a plant tissue. "
                        "Please review the organism or tissue selection."
                    )
                    return {
                        'user_input': user_input,
                        'extracted': {
                            'organism': organism,
                            'organism_variants': organism_variants,
                            'strategies': strategies,
                            'tissues': tissues,
                            'conditions': conditions,
                            'free_terms': free_terms
                        },
                        'ncbi_query': "",
                        'ready_to_use': False,
                        'clarification_needed': True,
                        'clarification_message': clarification
                    }
        
        # If query is too general, prepare clarification but continue
        needs_clarification = (
            (organism is None and not strategies and not genes) or
            (organism is not None and not strategies and not free_terms and not tissues and not conditions and not genes)
        )
        clarification_message = ""
        if needs_clarification:
            clarification_message = (
                "Your query is too general. Please specify an organism "
                "(e.g., Arabidopsis thaliana), a condition (e.g., drought stress), "
                "a tissue (e.g., leaf), or a strategy (e.g., RNA-Seq, ChIP-Seq)."
            )
            logger.info("⚠️ Clarification needed: general query")

        # Paso 6: Generar query booleana
        ncbi_query = self.query_builder.build_query(
            organisms=organism_variants,
            organism_synonyms=organism_synonyms,
            strategies=strategies,
            strategy_synonyms=strategy_synonyms,
            free_terms=free_terms,
            tissues=tissues,
            conditions=conditions,
            tissue_synonyms=tissue_synonyms,
            condition_synonyms=condition_synonyms,
            genes=genes,
            use_llm=use_llm
        )

        logger.info(f"✅ Generated query: {ncbi_query}")

        return {
            'user_input': user_input,
            'extracted': {
                'organism': organism,
                'organism_variants': organism_variants,
                'strategies': strategies,
                'tissues': tissues,
                'conditions': conditions,
                'genes': list(genes.keys()),
                'free_terms': free_terms
            },
            'synonyms': {
                'organism': organism_synonyms,
                'strategies': strategy_synonyms,
                'tissues': tissue_synonyms,
                'conditions': condition_synonyms,
                'genes': gene_synonyms
            },
            'ncbi_query': ncbi_query,
            'ready_to_use': True,
            'clarification_needed': needs_clarification,
            'clarification_message': clarification_message
        }
