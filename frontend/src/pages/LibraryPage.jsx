import { useEffect, useState } from "react";

import { listOutputs, updateOutputStatus } from "../lib/api";

const statuses = ["draft", "approved", "needs_edit", "rejected"];

export default function LibraryPage() {
  const [rows, setRows] = useState([]);

  const load = async () => {
    const res = await listOutputs();
    setRows(res.data);
  };

  useEffect(() => {
    load();
  }, []);

  const changeStatus = async (id, status) => {
    await updateOutputStatus(id, status);
    await load();
  };

  return (
    <div>
      <h2>Content Library</h2>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Title</th>
              <th>Status</th>
              <th>Generated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.output_type}</td>
                <td>{r.title}</td>
                <td>
                  <select value={r.status} onChange={(e) => changeStatus(r.id, e.target.value)}>
                    {statuses.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{new Date(r.generated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
