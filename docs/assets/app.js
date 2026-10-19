// 공통: 상단 메뉴, 푸터, 테마, 데이터 로딩, 숫자 포맷, 스파크라인
const NAV = [
  ["index.html", "대시보드"],
  ["macro.html", "매크로"],
  ["market.html", "시황·뉴스"],
  ["ai.html", "AI 섹터"],
  ["power.html", "전력 인프라"],
  ["indicators.html", "보조지표"],
  ["learn.html", "더 공부하기"],
  ["archive.html", "지난 주차"],
  ["slides.html", "발표 슬라이드"],
];

const App = (() => {
  const cache = {};
  const bust = new Date().toISOString().slice(0, 13); // 1시간 단위 캐시 무효화

  function load(path) {
    if (!cache[path]) {
      cache[path] = fetch(`${path}?v=${bust}`).then((r) => {
        if (!r.ok) throw new Error(`${path} ${r.status}`);
        return r.json();
      });
    }
    return cache[path];
  }
  const loadOpt = (path) => load(path).catch(() => null);

  // ---------- 테마 ----------
  function getTheme() {
    try { return localStorage.getItem("theme"); } catch { return null; }
  }
  function applyTheme(t) {
    if (t) document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
  }
  applyTheme(getTheme());
  function isDark() {
    const t = document.documentElement.dataset.theme;
    return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function toggleTheme() {
    const next = isDark() ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("theme", next); } catch {}
    location.reload(); // 차트 색을 다시 그리기 위해
  }
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ---------- 셸 ----------
  function shell() {
    const here = location.pathname.split("/").pop() || "index.html";
    const top = document.createElement("header");
    top.className = "topbar";
    top.innerHTML = `<div class="topbar-inner">
      <a class="brand" href="index.html">📈 <span>투자 스터디</span></a>
      <nav class="nav">${NAV.map(([h, t]) => `<a href="${h}" class="${h === here ? "active" : ""}">${t}</a>`).join("")}</nav>
      <button class="theme-btn" title="테마 전환">${isDark() ? "☀️" : "🌙"}</button></div>`;
    document.body.prepend(top);
    top.querySelector(".theme-btn").onclick = toggleTheme;
    const f = document.createElement("footer");
    f.innerHTML = `이 사이트는 스터디 <b>학습용 자료</b>이며 특정 종목의 매수·매도를 권유하지 않습니다. 데이터는 지연되거나 틀릴 수 있으니 투자 판단 전에 원자료로 확인하세요.<br>
      데이터: Yahoo Finance(yfinance), FRED(세인트루이스 연준), 한국은행 ECOS · 글: 매주 Claude가 웹 검색으로 작성`;
    document.body.append(f);
    if (window.Chart) {
      Chart.defaults.font.family = css("--font");
      Chart.defaults.color = css("--muted");
      Chart.defaults.borderColor = css("--border");
      Chart.defaults.maintainAspectRatio = false;
      Chart.defaults.plugins.legend.labels.boxWidth = 12;
    }
  }

  async function stamp(el) {
    if (!el) return;
    const [u, w] = await Promise.all([loadOpt("data/updated.json"), loadOpt("content/weekly/latest.json")]);
    el.innerHTML = `데이터 <b>${u?.updated_at ?? "-"}</b> · 주간 글 <b>${w?.date ?? "-"}</b>`;
  }

  // ---------- 포맷 ----------
  function num(v, d = 2) {
    if (v == null || Number.isNaN(v)) return "-";
    return Number(v).toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function smart(v) {
    if (v == null) return "-";
    const a = Math.abs(v);
    return num(v, a >= 1000 ? 0 : a >= 100 ? 1 : 2);
  }
  function chg(v, suffix = "%") {
    if (v == null) return `<span class="flat-c">-</span>`;
    const cls = v > 0 ? "up" : v < 0 ? "down" : "flat-c";
    const arrow = v > 0 ? "▲" : v < 0 ? "▼" : "";
    return `<span class="${cls}">${arrow}${num(Math.abs(v), 2)}${suffix}</span>`;
  }
  function bigNum(v) {
    if (v == null) return "-";
    if (v >= 1e12) return `${num(v / 1e12, 2)}조`;
    if (v >= 1e8) return `${num(v / 1e8, 0)}억`;
    return num(v, 0);
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- 스파크라인 ----------
  function spark(canvas, arr) {
    if (!canvas || !arr?.length) return;
    const dpr = devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const min = Math.min(...arr), max = Math.max(...arr), rng = max - min || 1;
    const color = arr[arr.length - 1] >= arr[0] ? css("--up") : css("--down");
    ctx.beginPath();
    arr.forEach((v, i) => {
      const x = (i / (arr.length - 1)) * w, y = h - 2 - ((v - min) / rng) * (h - 4);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
  }

  function tile(it, opts = {}) {
    const unit = opts.unit ?? "";
    return `<div class="card tile">
      <div class="t-name">${esc(it.name)}</div>
      <div class="t-val">${smart(it.last)}${unit}</div>
      <div class="t-chg">${chg(it.chg1d)} <span class="t-sub">1D</span> &nbsp;${chg(it.chg1m)} <span class="t-sub">1M</span></div>
      <canvas class="spark" data-spark='${JSON.stringify(it.spark || [])}'></canvas>
      <div class="t-sub">${it.date} 기준 · YTD ${it.ytd == null ? "-" : num(it.ytd, 1) + "%"}</div>
    </div>`;
  }
  function drawSparks(root = document) {
    root.querySelectorAll("canvas[data-spark]").forEach((c) => spark(c, JSON.parse(c.dataset.spark)));
  }

  // 매크로 시계열용 Chart.js 라인 차트
  function lineChart(canvas, datasets, opts = {}) {
    const palette = [css("--accent"), css("--up"), css("--neutral"), css("--down"), css("--muted")];
    const xs = datasets.flatMap((d) => d.points.map(([x]) => Date.parse(x)));
    return new Chart(canvas, {
      type: "line",
      data: {
        datasets: datasets.map((d, i) => ({
          label: d.label, data: d.points.map(([x, y]) => ({ x: Date.parse(x), y })),
          borderColor: d.color || palette[i % palette.length], backgroundColor: "transparent",
          borderWidth: 1.8, pointRadius: 0, tension: 0.15, ...(d.extra || {}),
        })),
      },
      options: {
        parsing: false, animation: false, interaction: { mode: "index", intersect: false },
        scales: {
          x: { type: "linear", min: Math.min(...xs), max: Math.max(...xs), ticks: { maxTicksLimit: 7, callback: (v) => new Date(v).toISOString().slice(0, 7) } },
          y: { ticks: { callback: (v) => v + (opts.unit ?? "") } },
        },
        plugins: {
          legend: { display: datasets.length > 1 },
          tooltip: { callbacks: { title: (items) => new Date(items[0].parsed.x).toISOString().slice(0, 10), label: (c) => `${c.dataset.label}: ${num(c.parsed.y, 2)}${opts.unit ?? ""}` } },
          ...(opts.plugins || {}),
        },
        ...(opts.options || {}),
      },
    });
  }

  return { load, loadOpt, shell, stamp, num, smart, chg, bigNum, esc, spark, tile, drawSparks, lineChart, css, isDark };
})();

document.addEventListener("DOMContentLoaded", () => {
  if (document.body.dataset.noShell != null) return; // 슬라이드는 메뉴·푸터 없이
  App.shell();
  App.stamp(document.querySelector(".stamp"));
});
