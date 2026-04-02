import { useCallback } from "react";
import { useState } from "react";

import { deleteOutput, listOutputs, updateOutputStatus } from "../lib/api";
import { downloadAsWordDocument } from "../lib/documentExport";
import useApi from "../lib/useApi";

const statuses = ["draft", "approved", "needs_edit", "rejected"];
const PAGE_SIZE = 20;

export default function LibraryPage() {
  const [page, setPage] = useState(1);
  const [expandedOutputId, setExpandedOutputId] = useState(null);
  const [deletingOutputId, setDeletingOutputId] = useState(null);

  const fetchOutputs = useCallback(
    () => listOutputs({ skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE }),
    [page],
  );
  const { data: rows, loading, error, reload } = useApi(fetchOutputs);

  const changeStatus = async (id, status) => {
    await updateOutputStatus(id, status);
    await reload();
  };

  const onDeleteOutput = async (id) => {
    if (!id || deletingOutputId) return;
    if (!window.confirm("Delete this generated output?")) return;

    setDeletingOutputId(id);
    try {
      await deleteOutput(id);
      if (expandedOutputId === id) {
        setExpandedOutputId(null);
      }
      if ((rows || []).length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      } else {
        await reload();
      }
    } finally {
      setDeletingOutputId(null);
    }
  };

  const hasNextPage = (rows || []).length === PAGE_SIZE;
  const previewText = (value) => {
    const clean = (value || "").replace(/\s+/g, " ").trim();
    if (!clean) return "No generated content.";
    if (clean.length <= 160) return clean;
    return `${clean.slice(0, 160)}...`;
  };

  const handleDownloadOutput = (output) => {
    if (!output) return;
    downloadAsWordDocument({
      title: output.title,
      content: output.content,
      fileNamePrefix: output.output_type || "output",
    });
  };

  return (
    <div>
      <h2>Content Library</h2>

      {loading && <p className="page-loading">Loading content library...</p>}
      {error && <p className="msg-error">{error}</p>}

      <div className="action-row mt-sm">
        <button type="button" className="secondary" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1 || loading}>
          Previous Page
        </button>
        <button type="button" className="secondary" onClick={() => setPage((current) => current + 1)} disabled={!hasNextPage || loading}>
          Next Page
        </button>
        <span className="page-status">Page {page}</span>
      </div>

      {rows && (
        <div className="card">
          {rows.length === 0 ? (
            <p className="empty-state">No generated content yet. Generate content from the Scraped Topics page.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Title</th>
                  <th>Preview</th>
                  <th>Status</th>
                  <th>Generated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => [
                  <tr key={r.id}>
                      <td>{r.output_type}</td>
                      <td>{r.title}</td>
                      <td className="content-snippet">{previewText(r.content)}</td>
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
                      <td>
                        <div className="action-row">
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setExpandedOutputId((current) => (current === r.id ? null : r.id))}
                          >
                            {expandedOutputId === r.id ? "Hide" : "View"}
                          </button>
                          <button type="button" onClick={() => onDeleteOutput(r.id)} disabled={deletingOutputId === r.id}>
                            {deletingOutputId === r.id ? "Deleting..." : "Delete"}
                          </button>
                          <button type="button" className="secondary" onClick={() => handleDownloadOutput(r)}>
                            Download as Word
                          </button>
                        </div>
                      </td>
                    </tr>,
                    expandedOutputId === r.id ? (
                      <tr key={`${r.id}-content`}>
                        <td colSpan={6}>
                          <pre className="output-pre">{r.content}</pre>
                        </td>
                      </tr>
                    ) : null,
                ])}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
