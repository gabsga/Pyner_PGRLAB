import { useEffect, useMemo, useState } from 'react';
import { BookOpenText, ChartSpline, Database, Search } from 'lucide-react';
import { SearchView } from './components/SearchView';
import { ResultsView } from './components/ResultsView';
import { AnalysisView } from './components/AnalysisView';
import { HelpView } from './components/HelpView';
import { StatusBanner } from './components/StatusBanner';
import { QuerySummary } from './components/QuerySummary';
import { checkHealth, generateQuery, runSearchWithQuery } from './lib/api';
import type { AppStatus, AppView, MineroResponse, QueryGeneration, SearchPayload } from './types';

const API_BASE = import.meta.env.VITE_MINERO_API_URL ?? 'http://127.0.0.1:8010';

const NAV_ITEMS: Array<{ id: AppView; label: string; icon: typeof Search }> = [
  { id: 'buscar', label: 'Search', icon: Search },
  { id: 'resultados', label: 'Classified Results', icon: Database },
  { id: 'analisis', label: 'Analytics', icon: ChartSpline },
  { id: 'ayuda', label: 'Help', icon: BookOpenText },
];

function statusMessage(status: AppStatus): string {
  switch (status) {
    case 'loading':
      return 'Processing query and classifying records...';
    case 'success':
      return 'Search completed with classified results.';
    case 'partial-success':
      return 'Search completed with warnings. Review flagged records.';
    case 'empty':
      return 'No records found for the current filters.';
    case 'error':
      return 'The operation could not be completed.';
    default:
      return 'System ready. Enter a biological query to begin.';
  }
}

interface PendingRun {
  source: SearchPayload['source'];
  max_results: number;
  use_llm: boolean;
  query_generation: QueryGeneration;
}

export default function App() {
  const [view, setView] = useState<AppView>('buscar');
  const [status, setStatus] = useState<AppStatus>('idle');
  const [response, setResponse] = useState<MineroResponse | null>(null);
  const [error, setError] = useState<string>('');
  const [llmAvailable, setLlmAvailable] = useState(false);
  const [pendingRun, setPendingRun] = useState<PendingRun | null>(null);
  const [step, setStep] = useState<'idle' | 'generating' | 'running'>('idle');

  useEffect(() => {
    checkHealth()
      .then((health) => setLlmAvailable(Boolean(health.llm_runtime_available)))
      .catch(() => setLlmAvailable(false));
  }, []);

  async function handleGenerate(payload: SearchPayload): Promise<void> {
    setStep('generating');
    setStatus('loading');
    setError('');

    try {
      const query_generation = await generateQuery({
        natural_query: payload.natural_query,
        use_llm: payload.use_llm,
      });
      setPendingRun({
        source: payload.source,
        max_results: payload.max_results,
        use_llm: payload.use_llm,
        query_generation,
      });
      setStatus('idle');
      setView('buscar');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setError(message);
      setStatus('error');
    } finally {
      setStep('idle');
    }
  }

  async function handleConfirm(): Promise<void> {
    if (!pendingRun) return;

    setStep('running');
    setStatus('loading');
    setError('');

    try {
      const result = await runSearchWithQuery({
        source: pendingRun.source,
        max_results: pendingRun.max_results,
        use_llm: pendingRun.use_llm,
        ncbi_query: pendingRun.query_generation.ncbi_query,
        query_generation: pendingRun.query_generation,
      });
      setResponse(result);
      setPendingRun(null);
      setStatus(result.metadata.status);
      setView('resultados');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unexpected error';
      setError(message);
      setStatus('error');
    } finally {
      setStep('idle');
    }
  }

  const message = useMemo(() => {
    if (status === 'error' && error) {
      return error;
    }
    return statusMessage(status);
  }, [status, error]);

  return (
    <div className="app-shell">
      <div className="bg-layer bg-grid" />
      <div className="bg-layer bg-mesh" />
      <div className="scanline" />

      <aside className="sidebar">
        <header className="sidebar-header">
          <div className="brand-cluster">
            <div className="brand-mark" aria-hidden="true" />
            <div>
              <p className="brand-eyebrow">PGRLAB NODE</p>
              <h1>Minero</h1>
              <span>Guided scientific search</span>
            </div>
          </div>
        </header>

        <nav>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={view === id ? 'nav-item active' : 'nav-item'}
              onClick={() => setView(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <footer>
          <small>Build stable 1.0.0</small>
          <small>LLM: {llmAvailable ? 'Ollama available' : 'Heuristic fallback'}</small>
          <small>API: {API_BASE}</small>
        </footer>
      </aside>

      <main className="main-content">
        <div className="main-frame">
          <StatusBanner status={status} message={message} metadata={response?.metadata ?? null} />

          <section className="workspace">
            {view === 'buscar' ? (
              <div className="top-stack">
                <QuerySummary query={pendingRun?.query_generation ?? null} />
                <section className="panel compact flow-panel">
                  <header className="panel-header">
                    <h2>Workflow Status</h2>
                    <p>
                      {pendingRun
                        ? 'Query generated. Confirm to execute against PubMed or BioProject.'
                        : 'No run yet. Use the Search view to start.'}
                    </p>
                  </header>
                </section>
              </div>
            ) : null}

            {view === 'buscar' ? (
              <SearchView
                loading={status === 'loading'}
                isGenerating={step === 'generating'}
                isRunning={step === 'running'}
                llmAvailable={llmAvailable}
                pendingQuery={pendingRun?.query_generation ?? null}
                onGenerate={handleGenerate}
                onConfirm={handleConfirm}
                onDiscard={() => setPendingRun(null)}
              />
            ) : null}
            {view === 'resultados' ? <ResultsView response={response} /> : null}
            {view === 'analisis' ? <AnalysisView response={response} /> : null}
            {view === 'ayuda' ? <HelpView /> : null}
          </section>
        </div>
      </main>
    </div>
  );
}
