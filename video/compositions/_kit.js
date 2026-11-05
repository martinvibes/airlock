// Shared helpers for every scene. Deterministic: no clocks, no random, no measuring.
window.AK = window.AK || {
  split(el) {
    if (typeof el === "string") el = document.querySelector(el);
    if (!el) return [];
    if (!el.dataset.split) {
      el.dataset.split = "1";
      const walk = (n) => {
        [...n.childNodes].forEach((c) => {
          if (c.nodeType === 3) {
            const frag = document.createDocumentFragment();
            c.textContent.split(/(\s+)/).forEach((p) => {
              if (!p) return;
              if (/^\s+$/.test(p)) frag.appendChild(document.createTextNode(p));
              else {
                const s = document.createElement("span");
                s.className = "w";
                s.style.display = "inline-block";
                s.textContent = p;
                frag.appendChild(s);
              }
            });
            c.replaceWith(frag);
          } else if (c.nodeType === 1 && !c.classList.contains("w")) walk(c);
        });
      };
      walk(el);
    }
    return el.querySelectorAll(".w");
  },
  // per word: blur 6 -> 0 and opacity 0 -> 1 in 0.13 s, 0.07 s apart, no translate
  words(tl, sel, t, gap = 0.07) {
    const ws = AK.split(sel);
    tl.fromTo(ws, { opacity: 0, filter: "blur(6px)" },
      { opacity: 1, filter: "blur(0px)", duration: 0.13, ease: "power2.out", stagger: gap }, t);
    return ws;
  },
  blurIn(tl, sel, t, d = 0.18) {
    tl.fromTo(sel, { opacity: 0, filter: "blur(8px)" },
      { opacity: 1, filter: "blur(0px)", duration: d, ease: "power2.out" }, t);
  },
  out(tl, sel, t, d = 0.2) {
    tl.to(sel, { opacity: 0, filter: "blur(8px)", duration: d, ease: "power2.in" }, t);
  },
  // rubber stamp: scale 1.8 -> 1, rotate (rot-10) -> rot, 0.16 s power4.in
  stamp(tl, sel, t, rot = -8) {
    tl.fromTo(sel, { opacity: 0, scale: 1.8, rotation: rot - 10 },
      { opacity: 0.92, scale: 1, rotation: rot, duration: 0.16, ease: "power4.in" }, t);
  },
  shake(tl, sel, t, px = 8) {
    tl.fromTo(sel, { x: 0 }, { x: px, duration: 0.033, repeat: 3, yoyo: true, ease: "none", immediateRender: false }, t);
  },
  pop(tl, sel, t, stagger = 0) {
    tl.fromTo(sel, { opacity: 0, scale: 0.4 },
      { opacity: 1, scale: 1, duration: 0.45, ease: "back.out(1.6)", stagger }, t);
  },
  // number reel: a column of every value from a to b inside an overflow-hidden box one line tall.
  // Tweening the column's yPercent rolls the number with no callbacks.
  reel(sel, a, b) {
    const el = typeof sel === "string" ? document.querySelector(sel) : sel;
    const step = a <= b ? 1 : -1;
    let html = "";
    for (let v = a; v !== b + step; v += step) html += "<div>" + v + "</div>";
    el.innerHTML = '<div class="reel-col" data-layout-ignore>' + html + "</div>";
    el.setAttribute("data-layout-allow-overflow", "");
    const col = el.querySelector(".reel-col");
    col.dataset.n = String(Math.abs(b - a) + 1);
    return col;
  },
  roll(tl, col, t, d, ease = "power2.inOut") {
    const n = +col.dataset.n;
    tl.fromTo(col, { yPercent: 0 }, { yPercent: (-(n - 1) / n) * 100, duration: d, ease }, t);
  },
  // seeded PRNG (mulberry32)
  rng(seed) {
    return () => {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  },
};
