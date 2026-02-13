import { useMemo, useState } from 'react';
import { FlaskConical, Search, Sparkles } from 'lucide-react';
import type { QueryGeneration, SearchPayload, SourceMode } from '../types';

interface SearchViewProps {
  loading: boolean;
  isGenerating: boolean;
  isRunning: boolean;
  llmAvailable: boolean;
  pendingQuery: QueryGeneration | null;
  onGenerate: (payload: SearchPayload) => Promise<void>;
  onConfirm: () => Promise<void>;
  onDiscard: () => void;
}

const DEFAULT_QUERY =
  'Arabidopsis thaliana RNA-Seq under drought and water stress in root';

export function SearchView({
  loading,
  isGenerating,
  isRunning,
  llmAvailable,
  pendingQuery,
  onGenerate,
  onConfirm,
  onDiscard,
}: SearchViewProps) {
  const [naturalQuery, setNaturalQuery] = useState(DEFAULT_QUERY);
  const [source, setSource] = useState<SourceMode>('pubmed');
  const [maxResults, setMaxResults] = useState(20);
  const [useLlm, setUseLlm] = useState(true);

  const sourceDescription = useMemo(() => {
    if (source === 'pubmed') {
      return 'PubMed: fast, focused on papers and abstracts.';
    }
    return 'BioProject: slower, focused on projects and SRA hierarchy.';
  }, [source]);

  async function handleGenerate(): Promise<void> {
    await onGenerate({
      natural_query: naturalQuery.trim(),
      source,
      max_results: maxResults,
      use_llm: useLlm,
    });
  }

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    await handleGenerate();
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h2>Search</h2>
        <p>Write your biological question in natural language and run Minero.</p>
      </header>

      <form className="search-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Biological query</span>
          <textarea
            value={naturalQuery}
            onChange={(event) => setNaturalQuery(event.target.value)}
            placeholder="Ex: tomato RNA-Seq under phosphate deficiency"
            rows={6}
            required
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Data source</span>
            <select value={source} onChange={(event) => setSource(event.target.value as SourceMode)}>
              <option value="pubmed">PubMed</option>
              <option value="bioproject">BioProject</option>
            </select>
            <small>{sourceDescription}</small>
          </label>

          <label className="field">
            <span>Maximum results</span>
            <input
              type="number"
              min={1}
              max={200}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
            />
            <small>Allowed range: 1 to 200.</small>
          </label>
        </div>

        <label className="switch-field">
          <input
            type="checkbox"
            checked={useLlm}
            onChange={(event) => setUseLlm(event.target.checked)}
          />
          <span>
            LLM Classification (Ollama)
            <em>
              {llmAvailable
                ? 'Available. If it fails, Minero uses heuristic fallback.'
                : 'Unavailable right now. Heuristic fallback will be used.'}
            </em>
          </span>
        </label>

        <div className="actions">
          <button type="button" className="ghost" onClick={() => setNaturalQuery(DEFAULT_QUERY)}>
            <FlaskConical size={16} /> Load sample
          </button>

          <button type="submit" className="primary" disabled={loading || naturalQuery.trim().length < 3}>
            {isGenerating ? <Sparkles size={16} className="spin" /> : <Search size={16} />}
            {isGenerating ? 'Generating query...' : 'Generate query'}
          </button>
        </div>
      </form>

      {pendingQuery ? (
        <section className="panel compact" style={{ marginTop: 12 }}>
          <header className="panel-header">
            <h2>Confirmation</h2>
            <p>Review the generated NCBI query and confirm to run the real search.</p>
          </header>
          <pre className="query-block">{pendingQuery.ncbi_query}</pre>
          <div className="actions">
            <button type="button" className="ghost" onClick={handleGenerate} disabled={loading}>
              <FlaskConical size={16} /> Regenerate
            </button>
            <button type="button" className="ghost" onClick={onDiscard} disabled={loading}>
              Discard
            </button>
            <button type="button" className="primary" onClick={onConfirm} disabled={loading}>
              {isRunning ? <Sparkles size={16} className="spin" /> : <Search size={16} />}
              {isRunning ? 'Searching...' : 'Confirm and search'}
            </button>
          </div>
        </section>
      ) : null}
    </section>
  );
}
