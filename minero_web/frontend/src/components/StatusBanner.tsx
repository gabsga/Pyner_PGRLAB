import { AlertTriangle, CheckCircle2, LoaderCircle, Radar, ShieldAlert } from 'lucide-react';
import type { AppStatus, MineroMetadata } from '../types';

interface StatusBannerProps {
  status: AppStatus;
  message: string;
  metadata: MineroMetadata | null;
}

export function StatusBanner({ status, message, metadata }: StatusBannerProps) {
  const icon =
    status === 'loading' ? (
      <LoaderCircle className="spin" size={18} />
    ) : status === 'success' ? (
      <CheckCircle2 size={18} />
    ) : status === 'partial-success' ? (
      <AlertTriangle size={18} />
    ) : status === 'error' ? (
      <ShieldAlert size={18} />
    ) : (
      <Radar size={18} />
    );

  return (
    <div className={`status-banner ${status}`}>
      <div className="status-main">
        {icon}
        <span>{message}</span>
      </div>
      {metadata ? (
        <div className="status-meta">
          <small>Results: {metadata.total_results}</small>
          <small>Classification: {metadata.model_default}</small>
        </div>
      ) : null}
    </div>
  );
}
