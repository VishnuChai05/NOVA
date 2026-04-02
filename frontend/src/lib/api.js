import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  timeout: 300000,
});

const apiKey = import.meta.env.VITE_API_KEY;
if (apiKey) {
  api.defaults.headers.common["X-API-Key"] = apiKey;
}

export const health = () => api.get("/health");
export const blogCount = () => api.get("/blog-count");
export const refreshBlogCount = () => api.post("/blog-count/refresh");
export const runScrape = () => api.post("/scrape/run", undefined, { timeout: 600000 });
export const listScrapedPosts = (params = {}) => api.get("/scraped-posts", { params });
export const deleteScrapedPost = (id) => api.delete(`/scraped-posts/${id}`);
export const listScrapedInsights = (params = {}) => api.get("/scraped-insights", { params });
export const listScrapedKeywordCandidates = (limit = 25) =>
  api.get("/scraped-keyword-candidates", { params: { limit } });
export const listScrapeRuns = (params = {}) => api.get("/scrape/runs", { params });
export const getScrapeScheduler = () => api.get("/scrape/scheduler");
export const startScrapeScheduler = () => api.post("/scrape/scheduler/start");
export const stopScrapeScheduler = () => api.post("/scrape/scheduler/stop");
export const setScrapeSchedulerInterval = (interval_minutes) =>
  api.post("/scrape/scheduler/interval", { interval_minutes });
export const getScrapeConfig = () => api.get("/scrape/config");
export const updateScrapeConfig = (payload) => api.put("/scrape/config", payload);
export const generateOutput = (payload) => api.post("/generate", payload);
export const listOutputs = (params = {}) => api.get("/outputs", { params });
export const updateOutputStatus = (id, status) => api.patch(`/outputs/${id}/status`, { status });
export const deleteOutput = (id) => api.delete(`/outputs/${id}`);
export const runBlogMaker = (payload) => api.post("/engine/blog-maker", payload);
export const runScriptGenerator = (payload) => api.post("/engine/script-generator", payload);
export const runProductRange = (payload) => api.post("/engine/product-range", payload);
