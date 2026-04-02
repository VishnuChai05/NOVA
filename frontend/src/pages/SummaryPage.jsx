import { useCallback } from "react";

import { blogCount, refreshBlogCount } from "../lib/api";
import useApi from "../lib/useApi";

export default function SummaryPage() {
  const fetchBlogCount = useCallback(() => blogCount(), []);
  const { data, loading, error, reload } = useApi(fetchBlogCount);

  const onRefresh = async () => {
    await refreshBlogCount();
    await reload();
  };

  return (
    <div>
      <h2>Summary</h2>
      <button onClick={onRefresh}>Refresh Blog Index</button>

      {loading && <p className="page-loading">Loading summary...</p>}
      {error && <p className="msg-error mt-sm">{error}</p>}

      {data && (
        <div className="grid mt-sm">
          <div className="card">
            <strong>Total Blogs</strong>
            <p>{data.total}</p>
          </div>
          {Object.entries(data.categories).map(([k, v]) => (
            <div className="card" key={k}>
              <strong>{k}</strong>
              <p>{v}</p>
            </div>
          ))}
          <div className="card">
            <strong>Last Updated</strong>
            <p>{data.last_updated}</p>
          </div>
          <div className="card">
            <strong>Topic Gaps</strong>
            <p>{data.topic_gap_flags.join(", ") || "None"}</p>
          </div>
        </div>
      )}
    </div>
  );
}
