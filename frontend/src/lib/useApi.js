import { useCallback, useEffect, useState } from "react";

/**
 * Custom hook for API data fetching with loading/error state management.
 *
 * @param {Function} fetchFn - Async function that returns { data } (e.g. from axios)
 * @param {object} options
 * @param {boolean} [options.immediate=true] - Whether to fetch on mount
 * @returns {{ data, loading, error, reload }}
 */
export default function useApi(fetchFn, { immediate = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchFn();
      // Support both axios-style responses ({ data }) and plain returned objects.
      setData(res && Object.prototype.hasOwnProperty.call(res, "data") ? res.data : res);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" && detail.trim() ? detail : "Request failed.");
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    if (immediate) {
      reload();
    }
  }, [immediate, reload]);

  return { data, loading, error, reload, setData };
}
