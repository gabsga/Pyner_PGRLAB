#!/usr/bin/env python3
"""
Direct PubMed Boolean Search
=============================

Búsqueda directa en PubMed usando queries booleanos.

Usage:
    python pubmed_boolean_search.py "Arabidopsis AND phosphate" --max 50 --output results.tsv
"""

import sys
import csv
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from ncbi_linkout import LinkoutFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def save_pubmed_results_tsv(publications: List[Dict], output_file: Path):
    """
    Save PubMed search results to TSV.
    
    Args:
        publications: List of publication dictionaries
        output_file: Output TSV path
    """
    if not publications:
        logger.warning("No publications to save")
        return
    
    logger.info(f"\n{'='*70}")
    logger.info("💾 SAVING RESULTS TO TSV")
    logger.info(f"{'='*70}")
    
    fieldnames = [
        'pmid',
        'title',
        'year',
        'journal',
        'publication_type',
        'authors',
        'doi',
        'pmcid',
        'url',
        'abstract',
        'fetched_at'
    ]
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval='NA', delimiter='\t')
            writer.writeheader()
            
            for pub in publications:
                # Format authors list
                authors_str = "; ".join(pub.get('authors', [])) if pub.get('authors') else 'NA'
                
                row = {
                    'pmid': pub.get('pmid', 'NA'),
                    'title': pub.get('title', 'NA'),
                    'year': pub.get('year', 'NA'),
                    'journal': pub.get('journal', 'NA'),
                    'publication_type': pub.get('publication_type', 'NA'),
                    'authors': authors_str,
                    'doi': pub.get('doi', 'NA') if pub.get('doi') else 'NA',
                    'pmcid': pub.get('pmcid', 'NA') if pub.get('pmcid') else 'NA',
                    'url': pub.get('url', 'NA'),
                    'abstract': pub.get('abstract', 'NA'),
                    'fetched_at': pub.get('fetched_at', 'NA')
                }
                writer.writerow(row)
        
        logger.info(f"✓ Saved {len(publications)} publications to: {output_file}")
        
        # Print statistics
        with_doi = sum(1 for p in publications if p.get('doi') and p.get('doi') != 'NA')
        logger.info(f"  - Publications with DOI: {with_doi}")
        logger.info(f"  - Publications without DOI: {len(publications) - with_doi}")
        
    except Exception as e:
        logger.error(f"Error saving TSV: {e}")


def save_pubmed_results_json(publications: List[Dict], query: str, output_file: Path):
    """
    Save PubMed search results to JSON.
    
    Args:
        publications: List of publication dictionaries
        query: Original query string
        output_file: Output JSON path
    """
    if not publications:
        logger.warning("No publications to save")
        return
    
    try:
        data = {
            "metadata": {
                "query": query,
                "total_results": len(publications),
                "date": datetime.now().isoformat(),
                "with_doi": sum(1 for p in publications if p.get('doi') and p.get('doi') != 'NA')
            },
            "publications": publications
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"✓ Saved JSON to: {output_file}")
        
    except Exception as e:
        logger.error(f"Error saving JSON: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Direct PubMed boolean search"
    )
    parser.add_argument(
        "query",
        help="Boolean search query (e.g., 'Arabidopsis AND phosphate')"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=100,
        help="Maximum number of publications to retrieve (default: 100)"
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        help="Output TSV file (default: auto-generated)"
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Output JSON file (optional)"
    )
    parser.add_argument(
        "--db",
        choices=['pubmed', 'pmc'],
        default='pubmed',
        help="Database to search: 'pubmed' (titles/abstracts) or 'pmc' (full-text, more results). Default: pubmed"
    )
    
    args = parser.parse_args()
    
    # Generate default output filename if not provided
    if not args.output_tsv:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_tsv = Path(f"pubmed_results_{timestamp}.tsv")
    
    db_label = "PMC (full-text)" if args.db == 'pmc' else "PubMed"
    
    logger.info(f"\n{'*'*70}")
    logger.info(f"🔬 {db_label.upper()} DIRECT BOOLEAN SEARCH")
    logger.info(f"{'*'*70}")
    logger.info(f"Query: {args.query}")
    logger.info(f"Database: {db_label}")
    logger.info(f"Max results: {args.max}")
    
    # Execute search
    fetcher = LinkoutFetcher()
    publications = fetcher.search_publications_by_boolean_query(
        args.query,
        max_results=args.max,
        db=args.db
    )
    
    if not publications:
        logger.warning("\n⚠️  No publications found")
        logger.info("Suggestions:")
        logger.info("  - Try a broader query")
        logger.info("  - Check spelling")
        logger.info("  - Use fewer AND operators")
        return
    
    # Save results
    save_pubmed_results_tsv(publications, args.output_tsv)
    
    if args.output_json:
        save_pubmed_results_json(publications, args.query, args.output_json)
    
    logger.info(f"\n{'*'*70}")
    logger.info("✓ SEARCH COMPLETE")
    logger.info(f"{'*'*70}\n")


if __name__ == "__main__":
    main()
