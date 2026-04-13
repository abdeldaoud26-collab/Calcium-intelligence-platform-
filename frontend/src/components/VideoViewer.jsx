import React, { useRef, useEffect, useCallback } from "react";
import useStore, { API } from "../store/useStore";
import { COLORS } from "../utils/colors";
import { findCellAt } from "../utils/geometry";

function draw(ctx, c, color, lw) {
  if (!c || c.length < 2) return;
  ctx.beginPath(); ctx.moveTo(c[0][0], c[0][1]);
  for (let i = 1; i < c.length; i++) ctx.lineTo(c[i][0], c[i][1]);
  ctx.closePath(); ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.stroke();
}
function fill(ctx, c, color) {
  if (!c || c.length < 2) return;
  ctx.beginPath(); ctx.moveTo(c[0][0], c[0][1]);
  for (let i = 1; i < c.length; i++) ctx.lineTo(c[i][0], c[i][1]);
  ctx.closePath(); ctx.fillStyle = color; ctx.fill();
}

export default function VideoViewer() {
  const canvasRef = useRef(null), overlayRef = useRef(null);
  const { jobId, currentFrame, rois, selectedCells, hoveredCell, dims, toggleCell, setHovered } = useStore();
  const [h, w] = dims;

  useEffect(() => {
    if (!jobId || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    const img = new Image();
    img.onload = () => { canvasRef.current.width = img.width; canvasRef.current.height = img.height; ctx.drawImage(img, 0, 0); };
    img.src = API + "/frame/" + jobId + "/" + currentFrame;
  }, [jobId, currentFrame]);

  useEffect(() => {
    if (!overlayRef.current || !w) return;
    const cv = overlayRef.current, ctx = cv.getContext("2d");
    cv.width = w; cv.height = h; ctx.clearRect(0, 0, w, h);
    Object.values(rois).forEach((r) => draw(ctx, r.contour, "rgba(255,255,255,0.15)", 1));
    if (hoveredCell && rois[hoveredCell]) {
      draw(ctx, rois[hoveredCell].contour, "rgba(255,255,0,0.6)", 2);
      const [cx, cy] = rois[hoveredCell].centroid;
      ctx.fillStyle = "yellow"; ctx.font = "12px monospace"; ctx.fillText("Cell " + hoveredCell, cx + 5, cy - 5);
    }
    selectedCells.forEach((cid, i) => {
      if (!rois[cid]) return;
      const col = COLORS[i % COLORS.length];
      draw(ctx, rois[cid].contour, col, 2); fill(ctx, rois[cid].contour, col + "33");
      const [cx, cy] = rois[cid].centroid;
      ctx.fillStyle = col; ctx.font = "bold 11px monospace"; ctx.fillText("#" + cid, cx + 5, cy - 5);
    });
  }, [rois, selectedCells, hoveredCell, w, h]);

  const coords = useCallback((e) => {
    const r = overlayRef.current.getBoundingClientRect();
    return [(e.clientX - r.left) * w / r.width, (e.clientY - r.top) * h / r.height];
  }, [w, h]);

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <canvas ref={canvasRef} style={{ display: "block", maxWidth: "100%", imageRendering: "pixelated" }} />
      <canvas ref={overlayRef}
        onClick={(e) => { const c = findCellAt(...coords(e), rois); if (c !== null) toggleCell(c); }}
        onMouseMove={(e) => setHovered(findCellAt(...coords(e), rois))}
        onMouseLeave={() => setHovered(null)}
        style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", cursor: "crosshair" }} />
    </div>
  );
}
