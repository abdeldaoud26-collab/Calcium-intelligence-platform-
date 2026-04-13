from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import numpy as np
import cv2
import io
import uuid
import os
import tempfile

app = FastAPI(title="Calcium Intelligence Platform", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

experiments = {}

# ── Helpers ──
def load_video(data, filename):
    low = filename.lower()
    if low.endswith((".tif", ".tiff")):
        import tifffile
        return tifffile.imread(io.BytesIO(data)).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(low)[1], delete=False) as tmp:
        tmp.write(data); tmp.flush()
        cap = cv2.VideoCapture(tmp.name); frames = []
        while True:
            ok, f = cap.read()
            if not ok: break
            if f.ndim == 3: f = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            frames.append(f.astype(np.float32))
        cap.release()
    return np.array(frames)

def load_mask(data, filename):
    low = filename.lower()
    if low.endswith((".tif", ".tiff")):
        import tifffile
        return tifffile.imread(io.BytesIO(data)).astype(np.int32)
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img.ndim == 3: img = img[:, :, 0]
    return img.astype(np.int32)

# ── Analysis Engine ──
class AnalysisResult:
    def __init__(self, video, mask, fps=10.0):
        from scipy.signal import find_peaks
        from skimage.measure import regionprops
        self.video = video; self.mask = mask; self.fps = fps
        self.n_frames, self.height, self.width = video.shape
        # ROIs
        self.rois = {}
        for p in regionprops(mask):
            binary = (mask == p.label).astype(np.uint8)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours: continue
            c = contours[0].squeeze().tolist()
            if isinstance(c[0], (int, float)): c = [c]
            self.rois[p.label] = {"id": p.label, "centroid": [float(p.centroid[1]), float(p.centroid[0])],
                                   "area": int(p.area), "contour": c}
        # Traces
        self.raw_traces = {}
        for cid in sorted(self.rois):
            m = mask == cid
            self.raw_traces[cid] = np.array([video[t][m].mean() for t in range(self.n_frames)])
        # DFF
        self.dff_traces = {}
        for cid, tr in self.raw_traces.items():
            f0 = max(np.percentile(tr, 10), 1e-6)
            self.dff_traces[cid] = (tr - f0) / f0
        # Metrics
        self.metrics = {}
        for cid, tr in self.dff_traces.items():
            z = (tr - np.mean(tr)) / max(np.std(tr), 1e-6)
            peaks, props = find_peaks(z, height=2.0, distance=int(fps), prominence=1.0)
            deriv = np.gradient(tr) * fps
            evts = []
            for i, pk in enumerate(peaks):
                h = z[pk]; thr = 0.1 * h
                rs = pk
                while rs > 0 and z[rs] > thr: rs -= 1
                de = pk
                while de < len(z) - 1 and z[de] > thr: de += 1
                evts.append({"peak_frame": int(pk), "peak_time": float(pk / fps),
                    "amplitude": float(h), "rise_time": float((pk - rs) / fps),
                    "decay_time": float((de - pk) / fps),
                    "upstroke_velocity": float(np.max(deriv[rs:pk + 1])),
                    "downstroke_velocity": float(np.min(deriv[pk:de + 1])),
                    "auc": float(np.trapz(z[rs:de + 1]) / fps)})
            self.metrics[cid] = {"cell_id": cid, "n_events": len(peaks),
                "mean_amplitude": float(np.mean([e["amplitude"] for e in evts])) if evts else 0,
                "mean_frequency": float(len(peaks) / (len(tr) / fps)),
                "centroid": self.rois[cid]["centroid"], "area": self.rois[cid]["area"], "events": evts}

# ── Network / Waves ──
class WaveAnalyzer:
    def __init__(self, traces, positions, fps=10.0):
        from scipy.signal import find_peaks
        from scipy.stats import pearsonr
        from scipy.spatial.distance import pdist, squareform
        self.traces = traces; self.positions = positions; self.fps = fps
        self.cell_ids = sorted(traces.keys()); self.n = len(self.cell_ids)
        pos_arr = np.array([positions[c] for c in self.cell_ids])
        self.dist_mat = squareform(pdist(pos_arr)) if self.n > 1 else np.zeros((1,1))
        self.events = {}
        for c in self.cell_ids:
            tr = traces[c]; z = (tr - np.median(tr)) / max(np.std(tr), 1e-8)
            pks, pr = find_peaks(z, height=2.0, distance=int(fps * 0.8), prominence=1.0)
            self.events[c] = {"times": pks / fps}

    def detect_waves(self, window=3.0, min_cells=3):
        from scipy.stats import linregress
        all_ev = []
        for c in self.cell_ids:
            for t in self.events[c]["times"]: all_ev.append({"cell": c, "time": t})
        all_ev.sort(key=lambda x: x["time"])
        if not all_ev: return []
        waves, used = [], set()
        for i, ev in enumerate(all_ev):
            if i in used: continue
            grp = [i]; cells = {ev["cell"]}
            for j in range(i + 1, len(all_ev)):
                if all_ev[j]["time"] - ev["time"] > window: break
                if j not in used and all_ev[j]["cell"] not in cells:
                    grp.append(j); cells.add(all_ev[j]["cell"])
            if len(cells) >= min_cells:
                wevts = sorted([all_ev[k] for k in grp], key=lambda x: x["time"])
                for k in grp: used.add(k)
                cs = [e["cell"] for e in wevts]; ts = np.array([e["time"] for e in wevts])
                pos = np.array([self.positions[c] for c in cs])
                origin = pos[0]; dists = np.linalg.norm(pos - origin, axis=1)
                rel = ts - ts[0]; spd = r2 = dirn = None
                if len(ts) > 2 and np.std(rel) > 0:
                    sl, _, r, _, _ = linregress(rel, dists); spd = abs(sl); r2 = r**2
                    disp = pos - origin; tw = 1.0 / (rel + 0.01); tw[0] = 0
                    if tw.sum() > 0:
                        tw /= tw.sum(); dv = np.average(disp, axis=0, weights=tw)
                        dirn = float(np.degrees(np.arctan2(dv[1], dv[0])))
                waves.append({"origin_cell": int(cs[0]), "n_cells": len(cs),
                    "duration": float(ts[-1] - ts[0]), "speed": float(spd) if spd else None,
                    "r2": float(r2) if r2 else None, "direction_deg": dirn, "start_time": float(ts[0])})
        return waves

    def synchrony_matrix(self):
        from scipy.stats import pearsonr
        mat = np.zeros((self.n, self.n))
        for i in range(self.n):
            for j in range(i, self.n):
                v, _ = pearsonr(self.traces[self.cell_ids[i]], self.traces[self.cell_ids[j]])
                mat[i, j] = mat[j, i] = v
        return {"matrix": mat.tolist(), "cell_ids": [int(c) for c in self.cell_ids]}

    def functional_network(self, threshold=0.5):
        sync = self.synchrony_matrix(); mat = np.array(sync["matrix"])
        nodes = [{"id": int(c), "x": float(self.positions[c][0]),
                  "y": float(self.positions[c][1]), "degree": 0} for c in self.cell_ids]
        edges = []
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if abs(mat[i, j]) >= threshold:
                    edges.append({"source": int(self.cell_ids[i]), "target": int(self.cell_ids[j]),
                                  "weight": float(mat[i, j])})
                    nodes[i]["degree"] += 1; nodes[j]["degree"] += 1
        degs = [n["degree"] for n in nodes]
        return {"nodes": nodes, "edges": edges,
                "global": {"n_edges": len(edges), "mean_degree": float(np.mean(degs)) if degs else 0,
                           "density": float(2 * len(edges) / (self.n * (self.n - 1))) if self.n > 1 else 0},
                "sync": sync}

# ── Insights ──
class SmartInsights:
    def __init__(self, result):
        self.r = result
    def generate(self):
        n = len(self.r.metrics)
        active = sum(1 for m in self.r.metrics.values() if m["n_events"] > 0)
        pct = active / max(n, 1) * 100
        ins = []
        if pct > 80: ins.append(f"🟢 High activity: {pct:.0f}% cells active ({active}/{n}).")
        elif pct > 40: ins.append(f"🟡 Moderate activity: {pct:.0f}% active.")
        else: ins.append(f"🔴 Low activity: {pct:.0f}% active. Check dye loading.")
        freqs = [m["mean_frequency"] for m in self.r.metrics.values() if m["mean_frequency"] > 0]
        if freqs: ins.append(f"📊 Mean frequency: {np.mean(freqs):.3f} Hz.")
        return {"insights": ins, "n_cells": n, "active": active, "pct_active": round(pct, 1)}

# ── Report ──
class ReportGenerator:
    def __init__(self, result):
        self.r = result
    def html(self):
        from datetime import datetime
        m = self.r.metrics; n = len(m)
        active = sum(1 for v in m.values() if v["n_events"] > 0)
        rows = ""
        for cid in sorted(m):
            v = m[cid]
            rows += f"<tr><td>{cid}</td><td>{v['n_events']}</td><td>{v['mean_amplitude']:.3f}</td><td>{v['mean_frequency']:.4f}</td><td>{v['area']}</td></tr>\n"
        return f"""<!DOCTYPE html><html><head><title>Calcium Report</title>
<style>body{{font-family:sans-serif;max-width:1000px;margin:auto;padding:20px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:6px}}
th{{background:#3498db;color:#fff}}.b{{display:inline-block;background:#ecf0f1;padding:12px 20px;margin:6px;border-radius:6px;text-align:center}}
.v{{font-size:24px;font-weight:bold}}.l{{font-size:11px;color:#888;text-transform:uppercase}}</style></head><body>
<h1>🔬 Calcium Report</h1><p style="color:#999">{datetime.now():%Y-%m-%d %H:%M}</p>
<div class="b"><div class="v">{n}</div><div class="l">Cells</div></div>
<div class="b"><div class="v">{active}</div><div class="l">Active</div></div>
<h2>Per-Cell Metrics</h2>
<table><thead><tr><th>Cell</th><th>Events</th><th>Amplitude</th><th>Freq</th><th>Area</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Methods</h2><div style="background:#f8f9fa;padding:16px;border-radius:6px;border-left:4px solid #3498db">
<p><b>Traces:</b> Mean ROI intensity. ΔF/F₀ 10th-percentile baseline.</p>
<p><b>Events:</b> Peaks &gt;2σ, prominence &gt;1σ. Upstroke=max(dF/dt), downstroke=min(dF/dt).</p>
<p><em>Calcium Intelligence Platform v3</em></p></div></body></html>"""

# ══════════════ ROUTES ══════════════

@app.get("/")
async def root():
    return {"status": "ok", "app": "Calcium Intelligence Platform v3"}

@app.post("/upload")
async def upload(video: UploadFile = File(...), mask: UploadFile = File(...)):
    jid = str(uuid.uuid4())
    vdata = await video.read(); mdata = await mask.read()
    vs = load_video(vdata, video.filename); ms = load_mask(mdata, mask.filename)
    res = AnalysisResult(vs, ms)
    experiments[jid] = res
    return {"job_id": jid, "n_cells": len(res.rois), "n_frames": res.n_frames, "dims": [res.height, res.width]}

@app.get("/rois/{jid}")
async def get_rois(jid: str):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    return {"rois": e.rois}

@app.get("/cell/{jid}/{cid}")
async def get_cell(jid: str, cid: int):
    e = experiments.get(jid)
    if not e or cid not in e.raw_traces: return JSONResponse(404, {"error": "not found"})
    return {"cell_id": cid, "raw": e.raw_traces[cid].tolist(), "dff": e.dff_traces[cid].tolist(),
            "metrics": e.metrics[cid], "roi": e.rois[cid]}

@app.get("/cells/{jid}")
async def get_cells(jid: str):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    return {"cells": list(e.metrics.values())}

@app.get("/frame/{jid}/{idx}")
async def get_frame(jid: str, idx: int):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    f = e.video[min(idx, e.n_frames - 1)]
    fn = ((f - f.min()) / max(f.max() - f.min(), 1) * 255).astype(np.uint8)
    _, buf = cv2.imencode(".jpg", fn, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/jpeg")

@app.get("/network/{jid}")
async def get_network(jid: str, threshold: float = 0.5):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    pos = {cid: r["centroid"] for cid, r in e.rois.items()}
    return WaveAnalyzer(e.dff_traces, pos, e.fps).functional_network(threshold)

@app.get("/waves/{jid}")
async def get_waves(jid: str, window: float = 3.0, min_cells: int = 3):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    pos = {cid: r["centroid"] for cid, r in e.rois.items()}
    wa = WaveAnalyzer(e.dff_traces, pos, e.fps)
    waves = wa.detect_waves(window, min_cells)
    speeds = [w["speed"] for w in waves if w["speed"] is not None]
    return {"n_waves": len(waves), "waves": waves,
            "mean_speed": float(np.mean(speeds)) if speeds else None}

@app.get("/insights/{jid}")
async def get_insights(jid: str):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    return SmartInsights(e).generate()

@app.get("/report/{jid}")
async def get_report(jid: str):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    html = ReportGenerator(e).html()
    return StreamingResponse(io.BytesIO(html.encode()), media_type="text/html",
                             headers={"Content-Disposition": "attachment; filename=report.html"})

@app.get("/export/{jid}/traces")
async def export_traces(jid: str):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    import pandas as pd
    buf = io.StringIO(); pd.DataFrame(e.dff_traces).to_csv(buf)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=traces.csv"})

@app.get("/export/{jid}/metrics")
async def export_metrics(jid: str):
    e = experiments.get(jid)
    if not e: return JSONResponse(404, {"error": "not found"})
    import pandas as pd
    rows = [{"cell_id": cid, **{k: v for k, v in m.items() if k != "events"}} for cid, m in e.metrics.items()]
    buf = io.StringIO(); pd.DataFrame(rows).to_csv(buf, index=False)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=metrics.csv"})
