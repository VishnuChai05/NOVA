import { useEffect, useState } from "react";

import { listScrapedPosts, runScrape } from "../lib/api";

export default function TopicsPage() {
  const [rows, setRows] = useState([]);

  const load = async () => {
    const res = await listScrapedPosts();
    setRows(res.data);
  };

  useEffect(() => {
    load();
  }, []);

  const onRun = async () => {
    await runScrape();
    await load();
  };

  return (
    <div>
      <h2>Scraped Topics</h2>
      <button onClick={onRun}>Run Scraper</button>
      <div className="card" style={{ marginTop: 12 }}>
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Category</th>
              <th>Score</th>
              <th>Title</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.source}</td>
                <td>{r.category_tag}</td>
                <td>{r.score}</td>
                <td>{r.title}</td>
                <td>{new Date(r.scraped_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
