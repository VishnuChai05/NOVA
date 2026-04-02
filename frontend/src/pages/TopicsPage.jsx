import { useCallback, useEffect, useState } from 'react';

import {
  deleteScrapedPost,
  generateOutput,
  listScrapeRuns,
  listScrapedInsights,
  listScrapedKeywordCandidates,
  listScrapedPosts,
  runScrape,
} from '../lib/api';
import { downloadAsWordDocument } from '../lib/documentExport';
import useApi from '../lib/useApi';

const POSTS_PAGE_SIZE = 100;
const INSIGHTS_PAGE_SIZE = 12;

export default function TopicsPage() {
  const [postsPage, setPostsPage] = useState(1);
  const [insightsPage, setInsightsPage] = useState(1);

  const fetchTopicsData = useCallback(async () => {
    const [postsRes, insightsRes, candidatesRes] = await Promise.all([
      listScrapedPosts({ skip: (postsPage - 1) * POSTS_PAGE_SIZE, limit: POSTS_PAGE_SIZE }),
      listScrapedInsights({ skip: (insightsPage - 1) * INSIGHTS_PAGE_SIZE, limit: INSIGHTS_PAGE_SIZE }),
      listScrapedKeywordCandidates(20),
    ]);
    return {
      posts: postsRes.data || [],
      insights: insightsRes.data || [],
      candidates: candidatesRes.data || [],
    };
  }, [insightsPage, postsPage]);
  const { data, loading, error: loadError, reload } = useApi(fetchTopicsData);

  const [isScraping, setIsScraping] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [actionStatus, setActionStatus] = useState('');
  const [filterSource, setFilterSource] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');
  const [sortBy, setSortBy] = useState('date');
  const [selectedPostId, setSelectedPostId] = useState(null);
  const [isDeletingPost, setIsDeletingPost] = useState(false);
  const [isGeneratingBlog, setIsGeneratingBlog] = useState(false);
  const [isGeneratingSuggestions, setIsGeneratingSuggestions] = useState(false);
  const [generatedBlog, setGeneratedBlog] = useState(null);
  const [generatedSuggestions, setGeneratedSuggestions] = useState(null);

  const latestRunId = async () => {
    const res = await listScrapeRuns();
    return res.data?.[0]?.id || null;
  };

  const waitForNextCompletedRun = async (previousRunId) => {
    const timeoutMs = 180000;
    const pollMs = 3000;
    const startedAt = Date.now();

    while (Date.now() - startedAt < timeoutMs) {
      const currentRunId = await latestRunId();
      if (currentRunId && currentRunId !== previousRunId) {
        return true;
      }
      await new Promise((resolve) => globalThis.setTimeout(resolve, pollMs));
    }
    return false;
  };

  const onRun = async () => {
    setIsScraping(true);
    setError('');
    setStatus('Scraper is running. This can take up to a minute...');

    try {
      const response = await runScrape();
      await reload();

      if (response.data?.created === 0 && response.data?.message) {
        setStatus(response.data.message);
      } else {
        setStatus('Scrape completed and topics updated.');
      }
    } catch (e) {
      if (e?.response?.status === 409) {
        setError('');
        setStatus('A scrape is already running. Waiting for it to finish...');
        const prevRunId = await latestRunId();
        const completed = await waitForNextCompletedRun(prevRunId);
        await reload();
        setStatus(completed
          ? 'Background scrape finished and topics updated.'
          : 'Still running in background. Topics were refreshed.');
      } else if (e?.code === 'ECONNABORTED') {
        setStatus('Scraper is taking longer than expected. Refresh in a moment.');
        setError('');
      } else {
        const detail = e?.response?.data?.detail;
        setStatus('');
        setError(typeof detail === 'string' && detail.trim() ? detail : 'Failed to run scraper.');
      }
    } finally {
      setIsScraping(false);
    }
  };

  const allRows = data?.posts || [];
  const insights = data?.insights || [];
  const candidates = data?.candidates || [];
  const sources = ['all', ...new Set(allRows.map(r => r.source))].sort();
  const categories = ['all', ...new Set(allRows.map(r => r.category_tag))].sort();
  const hasNextPostsPage = allRows.length === POSTS_PAGE_SIZE;
  const hasNextInsightsPage = insights.length === INSIGHTS_PAGE_SIZE;

  const formatDate = (isoString) => {
    try {
      return new Date(isoString).toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch {
      return 'Invalid date';
    }
  };

  const parseInsightSuggestions = (insight) => {
    try {
      const parsed = JSON.parse(insight.suggestions_json || '[]');
      if (Array.isArray(parsed)) {
        return parsed
          .filter((item) => typeof item === 'string' && item.trim())
          .map((item) => item.trim())
          .slice(0, 3);
      }
    } catch {
      // Ignore malformed suggestion payloads in UI and fall back to rationale.
    }
    if (insight.rationale && insight.rationale.trim()) {
      return [insight.rationale.trim()];
    }
    return ['No suggestion text available.'];
  };

  const onDeleteRow = async (postId) => {
    if (!postId || isDeletingPost) return;
    if (!window.confirm('Delete this scraped row and related generated outputs?')) return;

    setIsDeletingPost(true);
    setError('');
    setActionStatus('Deleting scraped row...');
    try {
      await deleteScrapedPost(postId);
      await reload();
      if (selectedPostId === postId) {
        setSelectedPostId(null);
        setGeneratedBlog(null);
        setGeneratedSuggestions(null);
      }
      setActionStatus('Row deleted successfully.');
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' && detail.trim() ? detail : 'Failed to delete row.');
      setActionStatus('');
    } finally {
      setIsDeletingPost(false);
    }
  };

  const onGenerateForSelected = async (outputType, forcedPostId = null) => {
    const targetPostId = forcedPostId || selectedPostId;
    if (!targetPostId) {
      setError('Select a row first to generate content.');
      return;
    }

    const isBlog = outputType === 'blog';
    if (isBlog) setIsGeneratingBlog(true);
    else setIsGeneratingSuggestions(true);

    setError('');
    setActionStatus(isBlog ? 'Generating full blog draft...' : 'Generating detailed product suggestions...');

    try {
      const response = await generateOutput({ post_id: targetPostId, output_type: outputType });
      if (isBlog) {
        setGeneratedBlog(response.data || null);
      } else {
        setGeneratedSuggestions(response.data || null);
      }
      setActionStatus(isBlog ? 'Blog draft generated.' : 'Product suggestions generated.');
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' && detail.trim() ? detail : 'Failed to generate output.');
      setActionStatus('');
    } finally {
      if (isBlog) setIsGeneratingBlog(false);
      else setIsGeneratingSuggestions(false);
    }
  };

  const handleDownloadOutput = (output) => {
    if (!output) return;
    downloadAsWordDocument({
      title: output.title,
      content: output.content,
      fileNamePrefix: output.output_type === 'blog' ? 'blog' : 'suggestions',
    });
  };

  let filtered = allRows.filter(r => {
    if (filterSource !== 'all' && r.source !== filterSource) return false;
    if (filterCategory !== 'all' && r.category_tag !== filterCategory) return false;
    return true;
  });

  filtered = [...filtered].sort((a, b) => {
    if (sortBy === 'score') return b.score - a.score;
    if (sortBy === 'title') return a.title.localeCompare(b.title);
    return new Date(b.scraped_at) - new Date(a.scraped_at);
  });

  const selectedPost = filtered.find((item) => item.id === selectedPostId) || null;

  useEffect(() => {
    setSelectedPostId((currentSelectedId) => {
      if (!filtered.length) {
        return null;
      }
      if (currentSelectedId && filtered.some((item) => item.id === currentSelectedId)) {
        return currentSelectedId;
      }
      return filtered[0].id;
    });
  }, [filtered]);

  return (
    <div>
      <h2>Scraped Topics</h2>
      <button onClick={onRun} disabled={isScraping}>
        {isScraping ? 'Running Scraper...' : 'Run Scraper'}
      </button>

      {isScraping && (
        <div className="inline-loader" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <span>Scraper is running and updating topics...</span>
        </div>
      )}

      {loading && <p className="page-loading">Loading topics...</p>}
      {(loadError || error) && <p className="msg-error mt-sm">{loadError || error}</p>}
      {status && <p className="mt-sm">{status}</p>}
      {actionStatus && <p className="msg-success mt-sm">{actionStatus}</p>}

      <div className="action-row mt-sm">
        <button type="button" className="secondary" onClick={() => setPostsPage((current) => Math.max(1, current - 1))} disabled={postsPage === 1 || loading}>
          Previous Posts
        </button>
        <button type="button" className="secondary" onClick={() => setPostsPage((current) => current + 1)} disabled={!hasNextPostsPage || loading}>
          Next Posts
        </button>
        <span className="page-status">Posts page {postsPage}</span>
      </div>

      <div className="card filter-bar mt-sm">
        <label>
          Source:
          <select value={filterSource} onChange={(e) => setFilterSource(e.target.value)}>
            {sources.map(s => <option key={s} value={s}>{s === 'all' ? 'All Sources' : s}</option>)}
          </select>
        </label>

        <label>
          Category:
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
            {categories.map(c => <option key={c} value={c}>{c === 'all' ? 'All Categories' : c}</option>)}
          </select>
        </label>

        <label>
          Sort By:
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="date">Newest First</option>
            <option value="score">Highest Score</option>
            <option value="title">Title (A-Z)</option>
          </select>
        </label>

        <span className="filter-bar-count">Showing {filtered.length} posts on page {postsPage}</span>
      </div>

      <div className="card mt-sm">
        {filtered.length === 0 ? (
          <p className="empty-state">
            {allRows.length === 0
              ? 'No scraped posts yet. Run the scraper to get started!'
              : 'No posts match the selected filters.'}
          </p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Category</th>
                <th>Score</th>
                <th>Title</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id} className={selectedPostId === r.id ? 'table-row-selected' : ''} onClick={() => setSelectedPostId(r.id)}>
                  <td>{r.source}</td>
                  <td>{r.category_tag}</td>
                  <td><strong>{r.score}</strong></td>
                  <td>{r.title}</td>
                  <td>{formatDate(r.scraped_at)}</td>
                  <td>
                    <div className="action-row">
                      <button type="button" className="secondary" onClick={(e) => { e.stopPropagation(); setSelectedPostId(r.id); onGenerateForSelected('blog', r.id); }} disabled={isGeneratingBlog || !r.id}>
                        {isGeneratingBlog && selectedPostId === r.id ? 'Generating...' : 'Generate Blog'}
                      </button>
                      <button type="button" className="secondary" onClick={(e) => { e.stopPropagation(); setSelectedPostId(r.id); onGenerateForSelected('product_idea', r.id); }} disabled={isGeneratingSuggestions || !r.id}>
                        {isGeneratingSuggestions && selectedPostId === r.id ? 'Generating...' : 'Product Suggestions'}
                      </button>
                      <button type="button" onClick={(e) => { e.stopPropagation(); onDeleteRow(r.id); }} disabled={isDeletingPost}>
                        {isDeletingPost && selectedPostId === r.id ? 'Deleting...' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card mt-sm">
        <h3>Content Studio</h3>
        {!selectedPost ? (
          <p className="empty-state">Select a scraped row to generate a full blog and detailed product suggestions.</p>
        ) : (
          <div className="card-body">
            <p><strong>Selected:</strong> {selectedPost.title}</p>
            <p className="topic-item-subtext"><strong>Source:</strong> {selectedPost.source} | <strong>Category:</strong> {selectedPost.category_tag}</p>
            <div className="action-row">
              <button type="button" className="secondary" onClick={() => onGenerateForSelected('blog')} disabled={isGeneratingBlog}>
                {isGeneratingBlog ? 'Generating Blog...' : 'Generate Full Blog'}
              </button>
              <button type="button" className="secondary" onClick={() => onGenerateForSelected('product_idea')} disabled={isGeneratingSuggestions}>
                {isGeneratingSuggestions ? 'Generating Suggestions...' : 'Generate Detailed Product Suggestions'}
              </button>
            </div>

            {generatedBlog && (
              <div className="topic-item">
                <div className="topic-item-top">
                  <strong>{generatedBlog.title || 'Generated Blog'}</strong>
                  <span>Score {Math.round((generatedBlog.evaluation_score || 0) * 100)}%</span>
                </div>
                <pre className="output-pre">{generatedBlog.content}</pre>
                <div className="action-row mt-sm">
                  <button type="button" className="secondary" onClick={() => handleDownloadOutput({ ...generatedBlog, output_type: 'blog' })}>
                    Download as Word
                  </button>
                </div>
              </div>
            )}

            {generatedSuggestions && (
              <div className="topic-item">
                <div className="topic-item-top">
                  <strong>{generatedSuggestions.title || 'Detailed Product Suggestions'}</strong>
                  <span>Score {Math.round((generatedSuggestions.evaluation_score || 0) * 100)}%</span>
                </div>
                <pre className="output-pre">{generatedSuggestions.content}</pre>
                <div className="action-row mt-sm">
                  <button type="button" className="secondary" onClick={() => handleDownloadOutput({ ...generatedSuggestions, output_type: 'product_idea' })}>
                    Download as Word
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid mt-sm topics-grid-2col">
        <div className="card">
          <h3>AI Insights</h3>
          <div className="action-row mt-sm">
            <button type="button" className="secondary" onClick={() => setInsightsPage((current) => Math.max(1, current - 1))} disabled={insightsPage === 1 || loading}>
              Previous Insights
            </button>
            <button type="button" className="secondary" onClick={() => setInsightsPage((current) => current + 1)} disabled={!hasNextInsightsPage || loading}>
              Next Insights
            </button>
            <span className="page-status">Insights page {insightsPage}</span>
          </div>
          {insights.length === 0 ? (
            <p className="empty-state">No insights yet. Run scraper to generate analysis.</p>
          ) : (
            <div className="topics-list">
              {insights.slice(0, 12).map((insight) => (
                <article key={insight.id} className="topic-item">
                  <div className="topic-item-top">
                    <strong>{insight.primary_topic || 'other'}</strong>
                    <span>{Math.round((insight.confidence || 0) * 100)}%</span>
                  </div>
                  <div className="topic-item-subtext">
                    {parseInsightSuggestions(insight).map((line, idx) => (
                      <p key={`${insight.id}-suggestion-${idx}`}>{line}</p>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3>Keyword Candidates (Review)</h3>
          {candidates.length === 0 ? (
            <p className="empty-state">No keyword candidates available yet.</p>
          ) : (
            <div className="topics-list">
              {candidates.map((candidate) => (
                <article key={candidate.keyword} className="topic-item">
                  <div className="topic-item-top">
                    <strong>{candidate.keyword}</strong>
                    <span>{candidate.appearances} hits</span>
                  </div>
                  <p className="topic-item-subtext">
                    Avg confidence {Math.round((candidate.avg_confidence || 0) * 100)}%
                    {candidate.source_topics?.length ? ` | Topics: ${candidate.source_topics.join(', ')}` : ''}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}