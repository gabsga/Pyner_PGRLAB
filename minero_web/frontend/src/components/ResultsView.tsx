import { useEffect, useMemo, useState } from 'react';
import { Download, Search as SearchIcon } from 'lucide-react';
import type { BioprojectResult, MineroResponse, MineroResult, PubmedResult } from '../types';
import { exportCsv, exportJson } from '../lib/exporters';

interface ResultsViewProps {
  response: MineroResponse | null;
}

function isPubmed(source: string, item: MineroResult): item is PubmedResult {
  return source === 'pubmed' && 'pmid' in item;
}

function isBioproject(source: string, item: MineroResult): item is BioprojectResult {
  return source === 'bioproject' && 'bioproject' in item;
}

function shortText(value: string, max: number = 54): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

function extractTagByPrefix(tags: string[], prefix: string): string {
  const match = tags.find((tag) => tag.startsWith(prefix));
  if (!match) return '-';
  return match.replace(prefix, '').trim() || '-';
}

function formatTag(tag: string): string {
  return tag
    .replace(/^organismo:/, 'organism: ')
    .replace(/^condicion:/, 'condition: ')
    .replace(/^estrategia:/, 'strategy: ')
    .replace(/^tejido:/, 'tissue: ')
    .replace(/^evidencia:/, 'evidence: ')
    .replace(/^alineacion:/, 'alignment: ');
}

export function ResultsView({ response }: ResultsViewProps) {
  const [searchText, setSearchText] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    setSelectedIndex(0);
  }, [response]);

  const filteredResults = useMemo(() => {
    if (!response) return [];
    return response.results.filter((item) => {
      const haystack = JSON.stringify(item).toLowerCase();
      return searchText.trim() === '' || haystack.includes(searchText.toLowerCase());
    });
  }, [response, searchText]);

  const selected = filteredResults[selectedIndex] ?? null;

  const streamStats = useMemo(() => {
    if (!response) return { high: 0, medium: 0, low: 0, direct: 0, weak: 0 };
    let high = 0;
    let medium = 0;
    let low = 0;
    let direct = 0;
    let weak = 0;
    response.results.forEach((result) => {
      if (result.classification.relevance_label === 'alta') high += 1;
      if (result.classification.relevance_label === 'media') medium += 1;
      if (result.classification.relevance_label === 'baja') low += 1;
      if (result.classification.evidence_level === 'directa') direct += 1;
      if (result.classification.evidence_level === 'débil') weak += 1;
    });
    return { high, medium, low, direct, weak };
  }, [response]);

  if (!response) {
    return (
      <section className="panel">
        <header className="panel-header">
          <h2>Classified Results</h2>
          <p>Run a search to inspect relevance-ranked scientific records.</p>
        </header>
      </section>
    );
  }

  return (
    <section className="panel repo-panel">
      <header className="repo-header">
        <div className="repo-title-block">
          <h2>Mined Repository</h2>
          <p>SYNCHRONIZED SRA METADATA</p>
        </div>
        <div className="repo-tools">
          <label className="repo-filter">
            <SearchIcon size={15} />
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Quick Filter..."
            />
          </label>
          <button className="primary repo-export" type="button" onClick={() => exportCsv(filteredResults, response.metadata.source)}>
            <Download size={14} /> Export CSV
          </button>
          <button className="ghost repo-export-secondary" type="button" onClick={() => exportJson(response)}>
            <Download size={14} /> JSON
          </button>
        </div>
      </header>

      <section className="repo-metadata-stream">
        <div className="stream-column">
          <p>METADATA_STREAM_B</p>
          <div className="stream-bars">
            <article>
              <strong>{response.metadata.total_results}</strong>
              <span>records</span>
            </article>
            <article>
              <strong>{streamStats.high}</strong>
              <span>high</span>
            </article>
            <article>
              <strong>{streamStats.direct}</strong>
              <span>direct</span>
            </article>
          </div>
        </div>
        <div className="stream-column">
          <p>TEMPORAL DISTRIBUTION</p>
          <div className="dot-grid">
            {Array.from({ length: 40 }).map((_, idx) => (
              <span key={idx} className={idx % 3 === 0 ? 'on' : ''} />
            ))}
          </div>
        </div>
        <div className="stream-column">
          <p>MORPHOLOGY</p>
          <div className="donut-wrap">
            <div
              className="donut"
              style={{
                background: `conic-gradient(#19d3a2 0 ${Math.max(5, streamStats.high * 8)}%, #3b82f6 0 ${Math.max(
                  15,
                  streamStats.medium * 8 + streamStats.high * 8
                )}%, #9b5de5 0 100%)`,
              }}
            />
            <div
              className="donut"
              style={{
                background: `conic-gradient(#16a34a 0 ${Math.max(10, streamStats.direct * 10)}%, #f59e0b 0 ${Math.max(
                  25,
                  streamStats.weak * 10 + streamStats.direct * 10
                )}%, #334155 0 100%)`,
              }}
            />
          </div>
        </div>
      </section>

      <div className="repo-table-wrap">
        <table className="repo-table">
          <thead>
            <tr>
              <th>{response.metadata.source === 'bioproject' ? 'BIOPROJECT ID' : 'PUBMED ID'}</th>
              <th>TITLE / CONTEXT</th>
              <th>ORGANISM / JOURNAL</th>
              <th>DOI</th>
              <th>TISSUE</th>
              <th>STRATEGY</th>
            </tr>
          </thead>
          <tbody>
            {filteredResults.map((item, index) => {
              const active = index === selectedIndex;
              const tags = item.classification.tags ?? [];
              const tissueTag = extractTagByPrefix(tags, 'tejido:');
              const strategyTag = extractTagByPrefix(tags, 'estrategia:');
              return (
                <tr
                  key={`${index}-${'pmid' in item ? item.pmid : (item as BioprojectResult).bioproject}`}
                  className={active ? 'active' : ''}
                  onClick={() => setSelectedIndex(index)}
                >
                  <td className="repo-id">
                    {isPubmed(response.metadata.source, item)
                      ? item.pmid
                      : isBioproject(response.metadata.source, item)
                      ? item.bioproject
                      : '-'}
                  </td>
                  <td className="repo-title">{shortText(item.title || 'Untitled record')}</td>
                  <td className="repo-organism">
                    {isPubmed(response.metadata.source, item)
                      ? item.journal || 'Unknown journal'
                      : isBioproject(response.metadata.source, item)
                      ? item.organism || 'Unknown organism'
                      : '-'}
                  </td>
                  <td className="repo-doi">
                    {isPubmed(response.metadata.source, item) ? item.doi || '-' : '-'}
                  </td>
                  <td>
                    <span className="repo-chip">{tissueTag.toUpperCase()}</span>
                  </td>
                  <td>{strategyTag === '-' ? '-' : shortText(strategyTag, 20)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <aside className="details-panel">
        <h3>Why this record matters</h3>
        {selected ? (
          <>
            <p>{selected.classification.reason_short}</p>
            <ul>
              {selected.classification.tags.map((tag) => (
                <li key={tag}>{formatTag(tag)}</li>
              ))}
            </ul>
            <dl>
              <div>
                <dt>Model source</dt>
                <dd>{selected.classification.model_source}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p>No records match the current filters.</p>
        )}
      </aside>
    </section>
  );
}
