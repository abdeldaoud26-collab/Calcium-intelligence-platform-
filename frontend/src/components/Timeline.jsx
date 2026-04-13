import React, { useEffect } from "react";
import useStore from "../store/useStore";

export default function Timeline({ fps = 10 }) {
  const { currentFrame, nFrames, setFrame, isPlaying, setPlaying } = useStore();
  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => {
      const s = useStore.getState(); setFrame((s.currentFrame + 1) % s.nFrames);
    }, 1000 / fps);
    return () => clearInterval(id);
  }, [isPlaying, fps]);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#0f3460", padding: "8px 14px", borderRadius: 8 }}>
      <button onClick={() => setPlaying(!isPlaying)} style={{ background: "none", border: "1px solid #4ECDC4", borderRadius: "50%", width: 32, height: 32, cursor: "pointer", fontSize: 14 }}>
        {isPlaying ? "⏸" : "▶"}
      </button>
      <span style={{ color: "#4ECDC4", fontFamily: "monospace", fontSize: 13 }}>{(currentFrame / fps).toFixed(2)}s</span>
      <input type="range" min={0} max={Math.max(nFrames - 1, 0)} value={currentFrame}
        onChange={e => setFrame(+e.target.value)} style={{ flex: 1 }} />
      <span style={{ color: "#4ECDC4", fontFamily: "monospace", fontSize: 13 }}>{(nFrames / fps).toFixed(2)}s</span>
    </div>
  );
}
