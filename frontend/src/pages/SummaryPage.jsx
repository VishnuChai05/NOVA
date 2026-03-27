import { useEffect, useState } from "react";

import { blogCount, refreshBlogCount } from "../lib/api";

export default function SummaryPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      const res = await blogCount();
      setData(res.data);
      setError("");
    } catch {
      setError("Could not load blog count. Try refresh.");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onRefresh = async () => {
    await refreshBlogCount();
    await load();
  };

  return (
    <div>
      <h2>Summary</h2>
      <button onClick={onRefresh}>Refresh Blog Index</button>
      {error && <p>{error}</p>}
      {data && (
        <div className="grid" style={{ marginTop: 12 }}>
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
