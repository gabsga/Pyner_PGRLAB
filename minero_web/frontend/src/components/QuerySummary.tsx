import type { QueryGeneration } from '../types';

interface QuerySummaryProps {
  query: QueryGeneration | null;
}

export function QuerySummary({ query }: QuerySummaryProps) {
  if (!query) {
    return (
      <section className="panel compact">
        <header className="panel-header">
          <h2>NCBI Query</h2>
          <p>The generated query will appear here after running a search.</p>
        </header>
      </section>
    );
  }

  return (
    <section className="panel compact">
      <header className="panel-header">
        <h2>Generated NCBI Query</h2>
        <p>Confirm this query correctly reflects your biological question.</p>
      </header>

      <pre className="query-block">{query.ncbi_query}</pre>

      <div className="chips-wrap">
        {(query.extracted.organism_variants ?? []).slice(0, 4).map((organism) => (
          <span key={organism} className="chip">
            organism:{organism}
          </span>
        ))}
        {(query.extracted.conditions ?? []).slice(0, 4).map((condition) => (
          <span key={condition} className="chip">
            condition:{condition}
          </span>
        ))}
        {(query.extracted.strategies ?? []).slice(0, 4).map((strategy) => (
          <span key={strategy} className="chip">
            strategy:{strategy}
          </span>
        ))}
      </div>
    </section>
  );
}
