import { useMemo, useState } from "react";

import { runBlogMaker, runProductRange, runScriptGenerator } from "../lib/api";

const ENGINE_TYPES = [
  { id: "blog", label: "Blog Maker" },
  { id: "script", label: "Production Script Generator" },
  { id: "product", label: "Product Range Builder" },
];

export default function EngineStudioPage() {
  const [engine, setEngine] = useState("blog");
  const [provider, setProvider] = useState("groq");
  const [brief, setBrief] = useState(
    "Women in India are asking for better comfort, real reviews, and practical product suggestions for daily use."
  );
  const [audience, setAudience] = useState("Women in India");
  const [keyword, setKeyword] = useState("women product reviews India");
  const [goal, setGoal] = useState("awareness");
  const [catalog, setCatalog] = useState("bras, panties, shapewear");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const helper = useMemo(() => {
    if (engine === "blog") {
      return "Creates a complete SEO-first blog blueprint from women-focused market intent.";
    }
    if (engine === "script") {
      return "Builds story + dialogue + screenplay shotlist + production explanation in one pack.";
    }
    return "Converts feedback trends into new product line ideas and a launch roadmap.";
  }, [engine]);

  const onRun = async () => {
    setLoading(true);
    setResult(null);
    setError("");
    try {
      let res;
      if (engine === "blog") {
        res = await runBlogMaker({
          brief, target_audience: audience, brand_name: "NOVA",
          seo_focus_keyword: keyword, llm_provider: provider,
        });
      } else if (engine === "script") {
        res = await runScriptGenerator({
          brief, target_audience: audience, brand_name: "NOVA",
          campaign_goal: goal, llm_provider: provider,
        });
      } else {
        res = await runProductRange({
          brief, target_audience: audience, brand_name: "NOVA",
          current_catalog_summary: catalog, llm_provider: provider,
        });
      }
      setResult(res.data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" && detail.trim() ? detail : "Engine run failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <section className="hero-panel">
        <p className="eyebrow">Engine Studio</p>
        <h2>Build Content, Campaign Scripts, and Product Range Strategy</h2>
        <p>
          A three-part backend engine for NOVA: blog maker, full production script generator, and product line
          expansion intelligence.
        </p>
      </section>

      <div className="card mt-sm">
        <div className="pill-row">
          {ENGINE_TYPES.map((item) => (
            <button
              key={item.id}
              className={engine === item.id ? "pill active" : "pill"}
              onClick={() => setEngine(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <p className="mt-sm">{helper}</p>

        <div className="engine-form">
          <label>
            Strategic Brief
            <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={4} />
          </label>

          <label>
            Target Audience
            <input value={audience} onChange={(e) => setAudience(e.target.value)} />
          </label>

          <label>
            Model Provider
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="template">Template (Fast, no API key)</option>
              <option value="anthropic">Anthropic</option>
              <option value="groq">Groq</option>
            </select>
          </label>

          {engine === "blog" && (
            <label>
              SEO Focus Keyword
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            </label>
          )}

          {engine === "script" && (
            <label>
              Campaign Goal
              <input value={goal} onChange={(e) => setGoal(e.target.value)} />
            </label>
          )}

          {engine === "product" && (
            <label>
              Current Catalog Summary
              <input value={catalog} onChange={(e) => setCatalog(e.target.value)} />
            </label>
          )}

          <button onClick={onRun} disabled={loading}>
            {loading ? "Generating..." : "Run Engine"}
          </button>
          {error && <p className="msg-error">{error}</p>}
        </div>
      </div>

      {result && (
        <div className="card mt-sm">
          <p className="eyebrow">{result.engine.replace("_", " ")}</p>
          <p>
            Provider: <strong>{result.provider_used}</strong>
            {result.used_fallback ? " (fallback used)" : ""}
          </p>
          <h3>{result.title}</h3>
          <pre className="output-pre">{result.content}</pre>
        </div>
      )}
    </div>
  );
}
