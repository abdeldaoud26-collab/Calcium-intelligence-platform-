import React, { useState } from "react";
import useStore, { API } from "./store/useStore";
import VideoViewer from "./components/VideoViewer";
import TracePlot from "./components/TracePlot";
import CellTable from "./components/CellTable";
import Timeline from "./components/Timeline";

export default function App() {
  const { jobId, setExperiment, setRois, setTraceMode } = useStore();
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault(); setUploading(true);
    const fd = new FormData();
    fd.append("video", e.target.video.files[0]);
    fd.append("mask", e.target.mask.files[0]);
    try {
      const r = await fetch(API + "/upload", { method: "POST", body: fd }).then(x => x.json());
      setExperiment(r.job_id, r.n_frames, r.dims);
      const rois = await fetch(API + "/rois/" + r.job_id).then(x => x.json());
      setRois(rois.rois);
    } catch (err) { alert("Upload failed: " + err.message); }
    setUploading(false);
  };

  const mbtn = { background: "#1a1a3e", color: "#4ECDC4", border: "1px solid #4ECDC4", padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12 };

  return (
    <div style={{ background: "#0a0a23", minHeight: "100vh", color: "#eee", fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ padding: "12px 20px", borderBottom: "1px solid #1a1a3e", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>🔬 Calcium Intelligence Platform</h1>
        {jobId && <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setTraceMode("raw")} style={mbtn}>Raw</button>
          <button onClick={() => setTraceMode("dff")} style={mbtn}>ΔF/F₀</button>
          <button onClick={() => window.open(API + "/export/" + useStore.getState().jobId + "/traces")} style={mbtn}>📥 CSV</button>
          <button onClick={() => window.open(API + "/report/" + useStore.getState().jobId)} style={{...mbtn, background: "#e74c3c", color: "#fff"}}>📄 Report</button>
        </div>}
      </header>
      {!jobId ? (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "80vh" }}>
          <form onSubmit={handleUpload} style={{ background: "#16213e", padding: 32, borderRadius: 12, display: "flex", flexDirection: "column", gap: 16 }}>
            <h2 style={{ margin: 0 }}>Upload Experiment</h2>
            <div><label>Calcium Video: </label><input type="file" name="video" accept=".tif,.tiff,.avi,.mp4" required /></div>
            <div><label>Cell Mask: </label><input type="file" name="mask" accept=".tif,.tiff,.png" required /></div>
            <button type="submit" disabled={uploading} style={{ background: "#4ECDC4", color: "#0a0a23", border: "none", padding: "12px 24px", borderRadius: 8, fontSize: 16, fontWeight: "bold", cursor: "pointer" }}>
              {uploading ? "⏳ Analyzing..." : "🚀 Upload & Analyze"}
            </button>
          </form>
        </div>
      ) : (
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 12 }}>
            <div style={{ background: "#111", borderRadius: 8, overflow: "hidden" }}><VideoViewer /></div>
            <CellTable />
          </div>
          <Timeline fps={10} />
          <TracePlot fps={10} />
        </div>
      )}
    </div>
  );
}
