import sys, os

os.chdir(__import__("pathlib").Path(__file__).resolve().parent.parent / "compositions")
css = open("" + str(__import__("pathlib").Path(__file__).with_name("boxes.css")) + "").read()


def boxes(pfx, ver_from, ver_to, rid):
    return f'''    <div id="{pfx}-k" class="bx bxk"><h3>KudiMart<br />canary pod</h3><div class="m">verifier <span class="vreel" data-layout-allow-overflow><span id="{pfx}-ver" style="display:block" data-layout-ignore><span style="display:block">{ver_from}</span><span style="display:block">{ver_to}</span></span></span></div></div>
    <div id="{pfx}-p" class="bx bxp"><h3>Paylane</h3><div class="big">37 webhooks<br />to replay</div></div>
    <div id="{pfx}-sk" class="sg sgk"><div class="av">K</div><div class="bub">sign {rid}</div></div>
    <div id="{pfx}-sp" class="sg sgp"><div class="av">P</div><div class="bub">sign {rid}</div></div>
    <div id="{pfx}-tks"></div>
'''


def tickets_js(p):
    return f'''      const host = document.querySelector("#{p}-tks");
      if (!host.children.length) {{
        for (let i = 0; i < 37; i++) {{
          const t = document.createElement("div");
          t.className = "tk";
          t.style.left = 1300 + (i % 6) * 76 + "px";
          t.style.top = 520 + Math.floor(i / 6) * 22 + "px";
          host.appendChild(t);
        }}
      }}
      const tks = [...host.children];
'''


replay = f'''<template>
  <style>
    #root {{
      position: absolute;
      inset: 0;
      background: var(--plaster);
      overflow: hidden;
    }}
{css}
    #rp-401 {{
      left: 220px;
      top: 430px;
      font-size: 150px;
      color: var(--crimson);
      z-index: 5;
    }}
    #rp-inv {{
      position: absolute;
      left: 640px;
      top: 270px;
      width: 130px;
      height: 130px;
      z-index: 6;
    }}
    #rp-rej {{
      position: absolute;
      left: 230px;
      top: 720px;
      font-size: 52px;
      font-weight: 700;
      color: var(--crimson);
    }}
  </style>
  <div id="root" data-composition-id="replay" data-width="1920" data-height="1080">
{boxes("rp", "v2.14.0", "v2.14.1", "replay-1")}
    <div id="rp-401" class="stampx" data-layout-allow-occlusion data-layout-allow-overlap>401</div>
    <div id="rp-rej">37 rejected</div>
    <div id="rp-say1" class="say">Replays need both engineers to sign.</div>
    <div id="rp-say2" class="say">The canary still checks only X-Sig-Primary.</div>
    <div id="rp-say3" class="say">KudiMart ships v2.14.1: it accepts either header.</div>
    <div id="rp-say4" class="say">Its investigator checks the fix in KudiMart's own files.</div>
    <svg id="rp-inv" viewBox="0 0 100 100"><rect x="18" y="18" width="64" height="64" rx="16" transform="rotate(45 50 50)" fill="#9bd78d"/><circle cx="39" cy="50" r="6" fill="#0f172a"/><circle cx="61" cy="50" r="6" fill="#0f172a"/></svg>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
{tickets_js("rp")}
      const rnd = AK.rng(401);
      AK.pop(tl, "#rp-k", 0.15);
      AK.pop(tl, "#rp-p", 0.25);
      AK.pop(tl, "#rp-sk", 0.7);
      AK.pop(tl, "#rp-sp", 1.3);
      AK.words(tl, "#rp-say1", 1.9, 0.08);
      // 37 webhooks fly at the canary and bounce
      tl.fromTo(tks, {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1, stagger: 0.025 }}, 2.1);
      tks.forEach((t, i) => {{
        const s = 2.2 + i * 0.025;
        tl.to(t, {{ x: -560 - (i % 6) * 76, duration: 0.42, ease: "power2.in" }}, s);
        tl.to(t, {{ borderColor: "#c8102e", backgroundColor: "#f7d9dd", duration: 0.05 }}, s + 0.42);
        tl.to(t, {{ x: -360 - (i % 6) * 76 + rnd() * 120, y: 260 + rnd() * 160, rotation: -60 + rnd() * 120, opacity: 0, duration: 0.6, ease: "power2.out" }}, s + 0.44);
      }});
      AK.stamp(tl, "#rp-401", 2.64, -8);
      AK.pop(tl, "#rp-rej", 3.2);
      AK.out(tl, "#rp-say1", 4.1, 0.15);
      AK.words(tl, "#rp-say2", 4.3, 0.08);
      // the fix ships
      AK.out(tl, ["#rp-say2", "#rp-401", "#rp-rej"], 6.6, 0.18);
      AK.words(tl, "#rp-say3", 6.7, 0.08);
      tl.to("#rp-ver", {{ yPercent: -50, duration: 0.35, ease: "back.out(1.6)" }}, 7.4);
      tl.to("#rp-k", {{ borderLeftColor: "#2e7d32", duration: 0.3 }}, 7.4);
      AK.out(tl, "#rp-say3", 9.12, 0.15);
      AK.pop(tl, "#rp-inv", 9.22);
      AK.words(tl, "#rp-say4", 9.27, 0.06);
      window.__timelines["replay"] = tl;
    }})();
  </script>
</template>
'''
open("replay.html", "w").write(replay)

payoff = f'''<template>
  <style>
    #root {{
      position: absolute;
      inset: 0;
      background: var(--plaster);
      overflow: hidden;
    }}
{css}
    #po-200 {{
      left: 230px;
      top: 440px;
      font-size: 150px;
      color: var(--green);
      z-index: 5;
    }}
    #po-green {{
      position: absolute;
      inset: 0;
      background: var(--green);
      color: var(--plaster);
      z-index: 6;
    }}
    #po-37 {{
      position: absolute;
      left: 130px;
      top: 200px;
      font-family: var(--font-display);
      font-size: 440px;
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    #po-del {{
      position: absolute;
      left: 140px;
      top: 660px;
      font-family: var(--font-display);
      font-size: 170px;
      line-height: 1;
    }}
    #po-stuck {{
      position: absolute;
      left: 130px;
      top: 170px;
      display: flex;
      align-items: flex-end;
      gap: 40px;
      z-index: 4;
    }}
    #po-reel {{
      font-family: var(--font-display);
      font-size: 440px;
      line-height: 440px;
      height: 440px;
      overflow: hidden;
      color: var(--ink);
      text-align: right;
      letter-spacing: -0.04em;
    }}
    #po-stuck span {{
      font-family: var(--font-display);
      font-size: 150px;
      line-height: 1;
      margin-bottom: 60px;
    }}
    #po-closed {{
      left: 1020px;
      top: 600px;
      font-size: 100px;
      line-height: 1.05;
      text-align: center;
      color: var(--green);
      z-index: 5;
    }}
    #po-say,
    #po-say2 {{
      z-index: 4;
    }}
    #po-wood {{
      position: absolute;
      inset: 0;
      background: repeating-linear-gradient(90deg, #5c3a21 0 46px, #553519 46px 48px);
      z-index: 9;
    }}
  </style>
  <div id="root" data-composition-id="payoff" data-width="1920" data-height="1080">
{boxes("po", "v2.14.1", "v2.14.1", "replay-2")}
    <div id="po-200" class="stampx" data-layout-allow-occlusion data-layout-allow-overlap>200</div>
    <div id="po-stuck"><div id="po-reel"></div><span>stuck</span></div>
    <div id="po-say" class="say">Customs re-runs the match on its own.</div>
    <div id="po-say2" class="say">Fixed together. Not one log line crossed.</div>
    <div id="po-closed" class="stampx" data-layout-allow-occlusion>INCIDENT<br />CLOSED</div>
    <div id="po-green"><div id="po-37">37</div><div id="po-del">delivered</div></div>
    <div id="po-wood"></div>
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
{tickets_js("po")}
      const reel = AK.reel("#po-reel", 37, 0);
      tl.set("#po-k", {{ borderLeftColor: "#2e7d32" }}, 0);
      ["#po-stuck", "#po-say"].forEach((s) => tl.set(s, {{ opacity: 0 }}, 0));
      tl.set("#po-wood", {{ xPercent: -100 }}, 0);
      AK.pop(tl, "#po-sk", 0.25);
      AK.pop(tl, "#po-sp", 0.9);
      // the replay goes through, landing on the drop at 2.36
      tl.fromTo(tks, {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1, stagger: 0.011 }}, 1.45);
      tks.forEach((t, i) => {{
        const s = 1.55 + i * 0.011;
        tl.to(t, {{ x: -640 - (i % 6) * 76, scale: 0.2, duration: 0.4, ease: "power2.in" }}, s);
        tl.to(t, {{ opacity: 0, duration: 0.05 }}, s + 0.4);
      }});
      AK.stamp(tl, "#po-200", 2.2, -8);
      tl.fromTo("#po-green", {{ clipPath: "circle(0% at 420px 510px)" }}, {{ clipPath: "circle(150% at 420px 510px)", duration: 0.38, ease: "power2.inOut" }}, 2.36);
      tl.fromTo("#po-37", {{ scale: 1.3, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.5, ease: "expo.out" }}, 2.42);
      AK.blurIn(tl, "#po-del", 2.75);
      // back on plaster: the stuck counter rolls to zero
      tl.to("#po-green", {{ xPercent: 100, duration: 0.4, ease: "power3.in" }}, 4.6);
      tl.set(["#po-k", "#po-p", "#po-sk", "#po-sp", "#po-200"], {{ opacity: 0 }}, 2.8);
      tl.to("#po-stuck", {{ opacity: 1, duration: 0.01 }}, 4.6);
      AK.roll(tl, reel, 4.95, 1.0, "power2.inOut");
      tl.to("#po-say", {{ opacity: 1, duration: 0.01 }}, 6.1);
      AK.words(tl, "#po-say", 6.1, 0.08);
      AK.stamp(tl, "#po-closed", 7.3, -6);
      AK.shake(tl, "#po-stuck", 7.46, 10);
      AK.out(tl, "#po-say", 9.1, 0.15);
      AK.words(tl, "#po-say2", 9.3, 0.08);
      tl.to("#po-wood", {{ xPercent: 0, duration: 0.45, ease: "power2.inOut" }}, 11.4);
      window.__timelines["payoff"] = tl;
    }})();
  </script>
</template>
'''
open("payoff.html", "w").write(payoff)
print("ok")
