import React, { useState, useMemo } from 'react';
import { ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react';

const PAGE_SIZE = 8;

export default function TradeHistory({ trades }) {
  const [sortKey, setSortKey] = useState('time');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    const arr = [...trades];
    arr.sort((a, b) => {
      let aVal = a[sortKey];
      let bVal = b[sortKey];
      if (sortKey === 'time') {
        aVal = new Date(aVal).getTime();
        bVal = new Date(bVal).getTime();
      }
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (sortDir === 'asc') return aVal > bVal ? 1 : -1;
      return aVal < bVal ? 1 : -1;
    });
    return arr;
  }, [trades, sortKey, sortDir]);

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const handleSort = (key) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const formatTime = (iso) => {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
      ' ' +
      d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  };

  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'time', label: 'Time' },
    { key: 'symbol', label: 'Symbol' },
    { key: 'side', label: 'Side' },
    { key: 'entry', label: 'Entry' },
    { key: 'exit', label: 'Exit' },
    { key: 'pnl', label: 'PnL' },
    { key: 'rr', label: 'R:R' },
    { key: 'status', label: 'Status' },
  ];

  return (
    <div className="glass-card glow-cyan">
      <div className="card-header">
        <div className="card-title">
          <ArrowUpDown />
          Trade History
        </div>
        <span className="card-badge">{trades.length} trades</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{
                    color: sortKey === col.key ? 'var(--cyan)' : undefined,
                  }}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span style={{ marginLeft: '4px', fontSize: '9px' }}>
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((trade) => (
              <tr key={trade.id}>
                <td style={{ color: 'var(--text-muted)' }}>{trade.id}</td>
                <td>{formatTime(trade.time)}</td>
                <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{trade.symbol}</td>
                <td>
                  <span className={`badge ${trade.side === 'LONG' ? 'badge-long' : 'badge-short'}`}>
                    {trade.side}
                  </span>
                </td>
                <td>{trade.entry_price != null ? `$${trade.entry_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}</td>
                <td>
                  {trade.exit_price != null
                    ? `$${trade.exit_price?.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                    : '—'}
                </td>
                <td>
                  {trade.pnl != null ? (
                    <span style={{
                      color: trade.pnl >= 0 ? 'var(--emerald)' : 'var(--rose)',
                      fontWeight: 600,
                    }}>
                      {trade.pnl >= 0 ? '+' : ''}${trade.pnl?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      <span style={{ opacity: 0.6, fontSize: '10px', marginLeft: '4px' }}>
                        ({trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct}%)
                      </span>
                    </span>
                  ) : '—'}
                </td>
                <td>
                  {trade.rr != null ? (
                    <span style={{
                      color: trade.rr >= 1 ? 'var(--emerald)' : 'var(--amber)',
                    }}>
                      {trade.rr?.toFixed(2)}
                    </span>
                  ) : '—'}
                </td>
                <td>
                  <span className={`badge badge-${(trade.status || 'OPEN').toLowerCase()}`}>
                    {trade.status || 'OPEN'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={styles.pagination}>
          <button
            className="btn"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            style={{ opacity: page === 0 ? 0.4 : 1 }}
          >
            <ChevronLeft size={14} /> Prev
          </button>
          <span className="mono" style={styles.pageInfo}>
            {page + 1} / {totalPages}
          </span>
          <button
            className="btn"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            style={{ opacity: page >= totalPages - 1 ? 0.4 : 1 }}
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

const styles = {
  pagination: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    marginTop: '16px',
    paddingTop: '12px',
    borderTop: '1px solid var(--border-subtle)',
  },
  pageInfo: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
  },
};
