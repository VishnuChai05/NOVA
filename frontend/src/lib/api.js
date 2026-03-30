import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  timeout: 20000,
});

export const health = () => api.get("/health");
export const blogCount = () => api.get("/blog-count");
export const refreshBlogCount = () => api.post("/blog-count/refresh");
export const runScrape = () => api.post("/scrape/run");
export const listScrapedPosts = () => api.get("/scraped-posts");
export const generateOutput = (payload) => api.post("/generate", payload);
export const listOutputs = () => api.get("/outputs");
export const updateOutputStatus = (id, status) => api.patch(`/outputs/${id}/status`, { status });
export const runBlogMaker = (payload) => api.post("/engine/blog-maker", payload);
export const runScriptGenerator = (payload) => api.post("/engine/script-generator", payload);
export const runProductRange = (payload) => api.post("/engine/product-range", payload);
