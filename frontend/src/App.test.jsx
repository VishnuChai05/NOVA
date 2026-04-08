import { describe, expect, test } from "vitest";

describe("frontend", () => {
  test("App module exports a default function component", async () => {
    const mod = await import("./App");
    expect(typeof mod.default).toBe("function");
  });

  test("Sidebar module exports a default function component", async () => {
    const mod = await import("./components/Sidebar");
    expect(typeof mod.default).toBe("function");
  });

  test("ErrorBoundary module exports a default class component", async () => {
    const mod = await import("./components/ErrorBoundary");
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe("function");
  });

  test("useApi hook module exports a default function", async () => {
    const mod = await import("./lib/useApi");
    expect(typeof mod.default).toBe("function");
  });

  test("useScrapeJobProgress hook module exports a default function", async () => {
    const mod = await import("./lib/useScrapeJobProgress");
    expect(typeof mod.default).toBe("function");
  });

  test("api module exports all expected endpoint functions", async () => {
    const api = await import("./lib/api");
    const expectedExports = [
      "health", "blogCount", "refreshBlogCount", "runScrape",
      "getScrapeJobStatus", "getActiveScrapeJobStatus", "clearScrapeJobStatusCache",
      "peekScrapeJobStatus",
      "listScrapedPosts", "listScrapedInsights", "listScrapedKeywordCandidates",
      "deleteScrapedPost",
      "listScrapeRuns", "getScrapeScheduler",
      "startScrapeScheduler", "stopScrapeScheduler", "setScrapeSchedulerInterval",
      "getScrapeConfig", "updateScrapeConfig", "generateOutput",
      "listOutputs", "updateOutputStatus", "deleteOutput", "runBlogMaker",
      "runScriptGenerator", "runProductRange",
    ];
    for (const name of expectedExports) {
      expect(typeof api[name]).toBe("function");
    }
  });

  test("all page modules export default function components", async () => {
    const pages = [
      "./pages/SummaryPage",
      "./pages/TopicsPage",
      "./pages/EngineStudioPage",
      "./pages/LibraryPage",
      "./pages/SettingsPage",
    ];
    for (const path of pages) {
      const mod = await import(path);
      expect(typeof mod.default).toBe("function");
    }
  });
});
