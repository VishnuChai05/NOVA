import { useCallback, useEffect, useState } from "react";

import {
  getScrapeConfig,
  getScrapeScheduler,
  setScrapeSchedulerInterval,
  startScrapeScheduler,
  stopScrapeScheduler,
  updateScrapeConfig,
} from "../lib/api";

function toLines(value) {
  return Array.isArray(value) ? value.join("\n") : "";
}

function fromLines(value) {
  return value
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [schedulerRunning, setSchedulerRunning] = useState(false);
  const [interval, setIntervalValue] = useState(60);

  const [subreddits, setSubreddits] = useState("");
  const [quoraQueries, setQuoraQueries] = useState("");
  const [discussionQueries, setDiscussionQueries] = useState("");
  const [blogQueries, setBlogQueries] = useState("");
  const [forumDomains, setForumDomains] = useState("");
  const [blogDomains, setBlogDomains] = useState("");
  const [maxPosts, setMaxPosts] = useState(50);
  const [minScore, setMinScore] = useState(10);
  const [runSchedule, setRunSchedule] = useState("0 9 * * 1");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const [configRes, schedulerRes] = await Promise.all([getScrapeConfig(), getScrapeScheduler()]);
      const config = configRes.data;
      const scheduler = schedulerRes.data;

      setSubreddits(toLines(config.subreddits));
      setQuoraQueries(toLines(config.quora_queries));
      setDiscussionQueries(toLines(config.discussion_queries));
      setBlogQueries(toLines(config.blog_queries));
      setForumDomains(toLines(config.forum_domains));
      setBlogDomains(toLines(config.blog_domains));
      setMaxPosts(config.max_posts_per_source);
      setMinScore(config.min_score);
      setRunSchedule(config.run_schedule);

      setSchedulerRunning(Boolean(scheduler.running));
      setIntervalValue(Number(scheduler.interval_minutes || 60));
    } catch {
      setError("Failed to load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onSaveConfig = async () => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await updateScrapeConfig({
        subreddits: fromLines(subreddits),
        quora_queries: fromLines(quoraQueries),
        discussion_queries: fromLines(discussionQueries),
        blog_queries: fromLines(blogQueries),
        forum_domains: fromLines(forumDomains),
        blog_domains: fromLines(blogDomains),
        max_posts_per_source: Number(maxPosts),
        min_score: Number(minScore),
        run_schedule: runSchedule,
      });
      setMessage("Scraper settings saved.");
    } catch {
      setError("Failed to save scraper settings.");
    } finally {
      setSaving(false);
    }
  };

  const onToggleScheduler = async () => {
    setError("");
    setMessage("");
    try {
      if (schedulerRunning) {
        const res = await stopScrapeScheduler();
        setSchedulerRunning(Boolean(res.data.running));
      } else {
        const res = await startScrapeScheduler();
        setSchedulerRunning(Boolean(res.data.running));
      }
    } catch {
      setError("Failed to update scheduler state.");
    }
  };

  const onSaveInterval = async () => {
    setError("");
    setMessage("");
    try {
      const res = await setScrapeSchedulerInterval(Number(interval));
      setIntervalValue(Number(res.data.interval_minutes));
      setMessage("Scheduler interval updated.");
    } catch {
      setError("Failed to update scheduler interval.");
    }
  };

  return (
    <div>
      <h2>Settings</h2>
      <div className="card card-body">
        {loading && <p className="page-loading">Loading settings...</p>}
        {message && <p className="msg-success">{message}</p>}
        {error && <p className="msg-error">{error}</p>}

        <h3>Scheduler</h3>
        <p>Status: {schedulerRunning ? "Running" : "Stopped"}</p>
        <div className="action-row">
          <button type="button" onClick={onToggleScheduler}>
            {schedulerRunning ? "Stop Scheduler" : "Start Scheduler"}
          </button>
        </div>

        <label>
          Interval Minutes
          <input
            type="number"
            min={5}
            max={1440}
            value={interval}
            onChange={(e) => setIntervalValue(e.target.value)}
          />
        </label>
        <button type="button" className="secondary" onClick={onSaveInterval}>
          Save Interval
        </button>

        <h3>Scraper Sources And Queries</h3>
        <p>One value per line.</p>

        <label>
          Subreddits
          <textarea rows={5} value={subreddits} onChange={(e) => setSubreddits(e.target.value)} />
        </label>

        <label>
          Quora Queries
          <textarea rows={5} value={quoraQueries} onChange={(e) => setQuoraQueries(e.target.value)} />
        </label>

        <label>
          Discussion Queries (Google forum-style)
          <textarea rows={5} value={discussionQueries} onChange={(e) => setDiscussionQueries(e.target.value)} />
        </label>

        <label>
          Blog Queries (Google blog-style)
          <textarea rows={5} value={blogQueries} onChange={(e) => setBlogQueries(e.target.value)} />
        </label>

        <label>
          Forum Domains
          <textarea rows={4} value={forumDomains} onChange={(e) => setForumDomains(e.target.value)} />
        </label>

        <label>
          Blog Domains
          <textarea rows={4} value={blogDomains} onChange={(e) => setBlogDomains(e.target.value)} />
        </label>

        <label>
          Max Posts Per Source
          <input type="number" min={5} max={500} value={maxPosts} onChange={(e) => setMaxPosts(e.target.value)} />
        </label>

        <label>
          Minimum Score
          <input type="number" min={0} max={5000} value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        </label>

        <label>
          Run Schedule (cron)
          <input value={runSchedule} onChange={(e) => setRunSchedule(e.target.value)} />
        </label>

        <button type="button" onClick={onSaveConfig} disabled={saving || loading}>
          {saving ? "Saving..." : "Save Scraper Settings"}
        </button>
      </div>
    </div>
  );
}
