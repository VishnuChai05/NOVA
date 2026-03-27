import { useEffect, useState } from "react";

import { generateOutput, listScrapedPosts } from "../lib/api";

export default function GeneratorPage() {
  const [posts, setPosts] = useState([]);
  const [postId, setPostId] = useState("");
  const [type, setType] = useState("blog");
  const [result, setResult] = useState(null);

  useEffect(() => {
    listScrapedPosts().then((res) => {
      setPosts(res.data);
      if (res.data[0]) {
        setPostId(res.data[0].id);
      }
    });
  }, []);

  const onGenerate = async () => {
    if (!postId) return;
    const res = await generateOutput({ post_id: postId, output_type: type });
    setResult(res.data);
  };

  return (
    <div>
      <h2>Content Generator</h2>
      <div className="card" style={{ display: "grid", gap: 10 }}>
        <label>
          Source Topic
          <select value={postId} onChange={(e) => setPostId(e.target.value)}>
            {posts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Output Type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="blog">Blog</option>
            <option value="reel">Reel</option>
            <option value="product_idea">Product Idea</option>
          </select>
        </label>
        <button onClick={onGenerate}>Generate</button>
      </div>

      {result && (
        <div className="card" style={{ marginTop: 12 }}>
          <h3>{result.title}</h3>
          <p>
            <strong>Quality score:</strong> {result.evaluation_score ?? "n/a"}
          </p>
          <pre style={{ whiteSpace: "pre-wrap" }}>{result.content}</pre>
        </div>
      )}
    </div>
  );
}
