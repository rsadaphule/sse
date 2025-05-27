/**
 * React + TypeScript client that starts a build and streams its logs via SSE.
 * Assumes backend is running on http://localhost:8000
 */
import { useState } from "react";

export default function App() {
  const [buildId, setBuildId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");

  /* --------------------------------------------------------------------- */
  /* Kick off a new build, then open an EventSource to /build/{id}/stream. */
  /* --------------------------------------------------------------------- */
  async function handleStart() {
    setStatus("running");
    setLogs([]);

    const res = await fetch("http://localhost:8000/build/start", {
      method: "POST",
    });

    console.log("[DEBUG] status", res.status);
   
    const { build_id } = await res.json();
    

    console.log("[DEBUG] build_id", build_id);

    setBuildId(build_id);

    const es = new EventSource(
      `http://localhost:8000/build/${build_id}/stream`
    );

    es.onopen = () => console.log("SSE open");

    es.onmessage = (evt) => {
      const line = JSON.parse(evt.data);
      setLogs((prev) => [...prev, line]);
    };

    es.addEventListener("done", () => {
      es.close();
      setStatus("done");
    });

    es.onerror = () => {
      console.error("SSE connection lost");
      es.close();
      setStatus("idle");
    };
  }

  /* UI ----------------------------------------------------------- */
  return (
    <main className="min-h-screen bg-slate-50 p-6 font-mono">
      <h1 className="mb-4 text-2xl font-bold text-slate-800">
        🛠️ Live Build Logs (SSE)
      </h1>

      <button
        onClick={handleStart}
        disabled={status === "running"}
        className="rounded bg-indigo-600 px-4 py-2 font-semibold text-white shadow disabled:opacity-40"
      >
        {status === "running" ? "Building…" : "Start Build"}
      </button>

      {buildId && (
        <p className="mt-2 text-sm text-slate-600">
          Build&nbsp;ID:&nbsp;<code>{buildId}</code>
        </p>
      )}

      <pre className="mt-4 h-[65vh] overflow-y-auto rounded bg-black p-4 text-green-400 shadow-inner">
        {logs.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </pre>

      {status === "done" && (
        <p className="mt-2 text-green-700">Build finished ✔</p>
      )}
    </main>
  );
}
