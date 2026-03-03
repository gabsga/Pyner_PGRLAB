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

// ─── Nombre del proyecto ────────────────────────────────────────────────────
// Cambiar este valor cuando se defina el nombre final (Pyner / MAIner / Minero)
const APP_NAME = 'Minero';

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

function PickaxeLogo() {
  return (
    <svg
      className="pickaxe-logo"
      viewBox="0 0 72 72"
      role="img"
      aria-label="Minero project logo"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Background gradient — deep forest green to near-black */}
        <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#0e2318" />
          <stop offset="55%" stopColor="#0a1c13" />
          <stop offset="100%" stopColor="#060f0a" />
        </linearGradient>

        {/* Shiny gold for pickaxe head */}
        <linearGradient id="goldHead" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffe98a" />
          <stop offset="40%" stopColor="#d4a017" />
          <stop offset="100%" stopColor="#8c6500" />
        </linearGradient>

        {/* Warm wood for handle */}
        <linearGradient id="woodHandle" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#9c6c30" />
          <stop offset="100%" stopColor="#4e2d08" />
        </linearGradient>

        {/* Teal accent for data-node dots */}
        <linearGradient id="tealDot" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#5efcde" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>

        {/* Outer rim glow */}
        <linearGradient id="rimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#d4a017" stopOpacity="0.8" />
          <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.5" />
        </linearGradient>

        {/* Gold glow filter */}
        <filter id="glowGold" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="1.6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        {/* Teal glow filter */}
        <filter id="glowTeal" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="1.4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        {/* Inner shadow for bg depth */}
        <filter id="innerShadow">
          <feFlood floodColor="#000" floodOpacity="0.45" result="flood" />
          <feComposite in="flood" in2="SourceGraphic" operator="in" result="shadow" />
          <feBlend in="SourceGraphic" in2="shadow" />
        </filter>
      </defs>

      {/* ── Background rounded rectangle ── */}
      <rect x="2" y="2" width="68" height="68" rx="20" fill="url(#bgGrad)" />

      {/* Subtle inner highlight top */}
      <rect x="2" y="2" width="68" height="34" rx="20"
        fill="url(#bgGrad)" opacity="0.15" />

      {/* Gradient rim border */}
      <rect x="2" y="2" width="68" height="68" rx="20"
        fill="none" stroke="url(#rimGrad)" strokeWidth="1.6" />

      {/* ── Inner glow ring (subtle) ── */}
      <rect x="5" y="5" width="62" height="62" rx="18"
        fill="none" stroke="#d4a017" strokeWidth="0.5" strokeOpacity="0.18" />

      {/* ── Pickaxe handle ── */}
      <line
        x1="20" y1="52" x2="40" y2="30"
        stroke="url(#woodHandle)" strokeWidth="5.5"
        strokeLinecap="round"
      />
      {/* Handle highlight stripe */}
      <line
        x1="21.5" y1="50" x2="39" y2="31.5"
        stroke="#c88c3a" strokeWidth="1.5"
        strokeLinecap="round" strokeOpacity="0.5"
      />

      {/* ── Pickaxe head — forward spike (main) ── */}
      <path
        d="M32 26 C34 18 44 12 56 15 C51 21 42 26 34 27 Z"
        fill="url(#goldHead)"
        filter="url(#glowGold)"
      />
      {/* Head highlight ridge */}
      <path
        d="M33 25 C36 21 43 17 52 16"
        fill="none" stroke="#ffe98a" strokeWidth="1.2"
        strokeLinecap="round" strokeOpacity="0.7"
      />

      {/* ── Pickaxe head — back horn ── */}
      <path
        d="M32 26 C29 22 24 16 16 15 C18 20 24 25 31 27 Z"
        fill="url(#goldHead)"
      />

      {/* Tip flash */}
      <line x1="54" y1="14" x2="59.5" y2="9.5"
        stroke="#ffe98a" strokeWidth="2.2" strokeLinecap="round"
        filter="url(#glowGold)"
      />

      {/* ── Handle grip cap ── */}
      <circle cx="20" cy="52" r="3.5" fill="url(#goldHead)" opacity="0.9" />
      <circle cx="20" cy="52" r="1.8" fill="#ffe98a" opacity="0.6" />

      {/* ── Data-node constellation (bottom-right) ── */}
      {/* Nodes */}
      <circle cx="49" cy="52" r="2.8" fill="url(#tealDot)" filter="url(#glowTeal)" opacity="0.95" />
      <circle cx="56" cy="45" r="1.8" fill="url(#tealDot)" filter="url(#glowTeal)" opacity="0.8" />
      <circle cx="57" cy="55" r="1.4" fill="url(#tealDot)" opacity="0.7" />
      {/* Connecting lines */}
      <line x1="49" y1="52" x2="56" y2="45"
        stroke="#06b6d4" strokeWidth="0.9" strokeOpacity="0.55" />
      <line x1="56" y1="45" x2="57" y2="55"
        stroke="#06b6d4" strokeWidth="0.9" strokeOpacity="0.4" />
      <line x1="49" y1="52" x2="57" y2="55"
        stroke="#06b6d4" strokeWidth="0.6" strokeOpacity="0.3" />
    </svg>
  );
}

/** Logos institucionales: PGRLab y Phytolearning en el footer del sidebar. */
function InstitutionalLogos() {
  return (
    <div className="inst-logos">
      <div className="inst-logo-wrap">
        <img
          src="/logos/pgrlab.png"
          alt="PGRLab"
          title="Plant Genome Regulation Lab (PGRLab)"
          className="inst-logo"
          onError={(e) => { (e.target as HTMLImageElement).parentElement!.style.display = 'none'; }}
        />
      </div>
      <div className="inst-logo-wrap inst-logo-wrap--phyto">
        <img
          src="/logos/phytolearning.png"
          alt="Phytolearning"
          title="Phytolearning — Núcleo Milenio en Ciencia de Datos y Resiliencia Vegetal"
          className="inst-logo"
          onError={(e) => { (e.target as HTMLImageElement).parentElement!.style.display = 'none'; }}
        />
      </div>
    </div>
  );
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
            <PickaxeLogo />
            <div>
              <p className="brand-eyebrow">PGRLAB · PHYTOLEARNING</p>
              <h1>{APP_NAME}</h1>
              <span>Guided scientific literature mining</span>
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
          <InstitutionalLogos />
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
