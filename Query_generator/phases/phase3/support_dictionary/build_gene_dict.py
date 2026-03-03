#!/usr/bin/env python3
"""
Build Gene Alias Dictionary from Annotation Files
===================================================

Parses tab-separated gene annotation files and generates JSON gene alias
dictionaries for use by the query generator.

Input format (TSV, no header):
    Column 1: Gene ID (e.g., Solyc01g008950)
    Column 2: Symbol (e.g., SlCaM1)
    Column 3: Full name (e.g., Calmodulin 1)

Output format (JSON):
    {
        "slcam1": ["SlCaM1", "Solyc01g008950", "Calmodulin 1"],
        ...
    }

Usage:
    python build_gene_dict.py <input_tsv> <output_json>
    python build_gene_dict.py /path/to/solyc_onto_annot.tab gene_aliases_tomato.json
"""

import sys
import json
import csv
from pathlib import Path
from collections import defaultdict


def build_gene_aliases(input_file: Path) -> dict:
    """
    Parse a gene annotation TSV and build an alias dictionary.
    
    Groups entries by gene ID so that multiple symbols for the same
    Solyc ID are merged into one alias set.
    
    Returns:
        dict: {lowercase_symbol: [symbol, gene_id, full_name, ...]}
    """
    # First pass: group all symbols and names by gene ID
    gene_groups = defaultdict(set)  # gene_id -> set of all terms
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) < 3:
                continue
            
            gene_id = row[0].strip()
            symbol = row[1].strip()
            name = row[2].strip()
            
            if not gene_id or not symbol:
                continue
            
            # Add all terms for this gene ID
            gene_groups[gene_id].add(gene_id)
            gene_groups[gene_id].add(symbol)
            if name and name != symbol:  # Avoid duplicates
                gene_groups[gene_id].add(name)
    
    # Second pass: create alias entries indexed by each symbol (lowercase)
    aliases = {}
    
    for gene_id, terms in gene_groups.items():
        term_list = sorted(terms)  # Deterministic order
        
        # Index by each symbol-like term (not the full name)
        for term in terms:
            key = term.lower()
            if key not in aliases:
                aliases[key] = term_list
            else:
                # Merge if there's overlap
                existing = set(aliases[key])
                existing.update(term_list)
                aliases[key] = sorted(existing)
    
    return aliases


def main():
    if len(sys.argv) < 3:
        print("Usage: python build_gene_dict.py <input_tsv> <output_json>")
        print("Example: python build_gene_dict.py solyc_onto_annot.tab gene_aliases_tomato.json")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)
    
    print(f"📖 Reading: {input_file}")
    aliases = build_gene_aliases(input_file)
    
    print(f"✓ Found {len(aliases)} gene alias entries")
    
    # Count unique genes (by Solyc ID)
    unique_genes = set()
    for terms in aliases.values():
        for t in terms:
            if t.startswith("Solyc"):
                unique_genes.add(t)
    print(f"✓ Covering {len(unique_genes)} unique genes")
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(aliases, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved to: {output_file}")
    
    # Show a few examples
    print("\n📋 Examples:")
    count = 0
    for key, vals in aliases.items():
        if key.startswith("sl") and count < 5:
            print(f"   {key} → {vals}")
            count += 1


if __name__ == "__main__":
    main()
