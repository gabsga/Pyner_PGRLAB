import type { BioprojectResult, MineroResponse, MineroResult, PubmedResult, SourceMode } from '../types';

function downloadBlob(data: BlobPart, filename: string, mimeType: string): void {
  const blob = new Blob([data], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function exportJson(response: MineroResponse): void {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const source = response.metadata.source;
  downloadBlob(JSON.stringify(response, null, 2), `minero_${source}_${stamp}.json`, 'application/json');
}

function csvEscape(value: unknown): string {
  const text = String(value ?? '');
  if (text.includes(',') || text.includes('"') || text.includes('\n')) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function buildPubmedRow(item: PubmedResult): Record<string, string | number> {
  const classification = item.classification;

  return {
    pmid: item.pmid,
    title: item.title,
    year: item.year ?? '',
    journal: item.journal ?? '',
    publication_type: item.publication_type ?? '',
    relevance_label: classification.relevance_label,
    relevance_score: classification.relevance_score,
    tags: Array.isArray(classification.tags) ? classification.tags.join(';') : '',
    evidence_level: classification.evidence_level,
    model_source: classification.model_source,
    reason_short: classification.reason_short,
  };
}

function buildBioprojectRow(item: BioprojectResult): Record<string, string | number> {
  const classification = item.classification;

  return {
    bioproject: item.bioproject,
    title: item.title,
    organism: item.organism ?? '',
    sra_experiments_count: item.sra_experiments_count ?? '',
    biosamples_count: item.biosamples_count ?? '',
    relevance_label: classification.relevance_label,
    relevance_score: classification.relevance_score,
    tags: Array.isArray(classification.tags) ? classification.tags.join(';') : '',
    evidence_level: classification.evidence_level,
    model_source: classification.model_source,
    reason_short: classification.reason_short,
  };
}

export function exportCsv(results: MineroResult[], source: SourceMode): void {
  if (!results.length) {
    return;
  }

  const rows =
    source === 'pubmed'
      ? results.filter((item): item is PubmedResult => 'pmid' in item).map(buildPubmedRow)
      : results.filter((item): item is BioprojectResult => 'bioproject' in item).map(buildBioprojectRow);
  if (!rows.length) {
    return;
  }
  const headers = Object.keys(rows[0]);
  const csv = [headers.join(','), ...rows.map((row) => headers.map((h) => csvEscape(row[h])).join(','))].join('\n');

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  downloadBlob(csv, `minero_${source}_${stamp}.csv`, 'text/csv;charset=utf-8');
}
