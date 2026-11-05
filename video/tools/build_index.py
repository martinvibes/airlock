"""Writes index.html: the twelve scene hosts, the music bed and every sound effect.

Each effect is listed at the moment its picture happens (scene start + local time);
the clip is shifted so its measured peak lands one frame after that picture.
Run from anywhere: python3 video/tools/build_index.py
"""
from pathlib import Path

VIDEO = Path(__file__).resolve().parent.parent

SCENES = [  # id, start (s) on the music's bar lines
    ("hook", 0.0), ("blame", 7.165), ("wall", 21.415), ("reveal", 30.925),
    ("rooms", 38.055), ("claim", 52.305), ("meet", 76.075), ("match", 90.325),
    ("replay", 108.895), ("payoff", 120.635), ("walls", 132.505), ("endcard", 139.635),
]
END = 149.145
START = dict(SCENES)

# peak offset of each bundled effect (npx hyperframes audio assets/sfx/<f> --json)
PEAK = {
    "click": 0.073, "click-soft": 0.073, "pop": 0.12, "error": 0.745, "impact-bass-1": 0.073,
    "notification": 0.229, "chime": 0.418, "sparkle": 0.027, "whoosh": 0.162,
    "whoosh-short": 0.162, "typing": 0.457, "key-press": 0.076, "riser": 3.472,
    "whoosh-cinematic": 2.503, "glitch-1": 0.82, "ping": 0.324,
}

# (scene, local time the picture hits, effect, volume)
HITS = [
    ("hook", 0.46, "impact-bass-1", 0.45), ("hook", 1.61, "impact-bass-1", 0.45),
    ("hook", 5.15, "pop", 0.7), ("hook", 5.45, "click-soft", 0.8), ("hook", 5.75, "pop", 0.7),
    ("hook", 6.96, "whoosh", 0.8),
    ("blame", 1.05, "pop", 0.8), ("blame", 1.75, "notification", 0.7), ("blame", 3.45, "notification", 0.7),
    ("blame", 5.5, "pop", 0.8), ("blame", 7.08, "whoosh-short", 0.8), ("blame", 13.95, "whoosh", 0.8),
    ("wall", 1.5, "typing", 0.6), ("wall", 3.05, "pop", 0.8), ("wall", 6.8, "whoosh", 0.8),
    ("wall", 7.52, "impact-bass-1", 1.0),
    ("reveal", 0.45, "whoosh-cinematic", 0.6), ("reveal", 1.45, "whoosh-short", 0.7),
    ("reveal", 2.1, "chime", 0.5), ("reveal", 6.75, "whoosh-short", 0.7),
    ("rooms", 0.3, "whoosh-short", 0.6), ("rooms", 1.62, "pop", 0.8), ("rooms", 2.72, "click-soft", 0.9),
    ("rooms", 3.82, "pop", 0.8), ("rooms", 4.92, "click-soft", 0.9), ("rooms", 5.92, "pop", 0.8),
    ("rooms", 7.55, "error", 0.7), ("rooms", 11.3, "error", 0.6), ("rooms", 13.95, "whoosh", 0.8),
    ("claim", 0.62, "notification", 0.6), ("claim", 3.02, "notification", 0.6),
    ("claim", 6.4, "typing", 0.6), ("claim", 8.62, "notification", 0.6),
    ("claim", 11.6, "key-press", 0.9), ("claim", 12.86, "error", 0.7),
    ("claim", 15.0, "key-press", 0.9), ("claim", 15.08, "click", 0.7), ("claim", 15.62, "ping", 0.6),
    ("claim", 18.2, "whoosh", 0.7), ("claim", 18.86, "impact-bass-1", 0.45),
    ("claim", 19.55, "whoosh-short", 0.8), ("claim", 23.4, "whoosh", 0.6),
    ("meet", 0.32, "notification", 0.6), ("meet", 1.7, "whoosh-short", 0.7), ("meet", 2.14, "error", 0.7),
    ("meet", 5.05, "whoosh-short", 0.7), ("meet", 5.65, "whoosh", 0.6), ("meet", 7.65, "whoosh", 0.7),
    ("meet", 8.2, "pop", 0.8), ("meet", 14.0, "whoosh-short", 0.6),
    ("match", 1.9, "pop", 0.7), ("match", 2.7, "pop", 0.7), ("match", 4.9, "glitch-1", 0.4),
    ("match", 7.0, "pop", 0.7), ("match", 7.12, "click-soft", 0.8), ("match", 9.3, "whoosh-short", 0.7),
    ("match", 12.0, "pop", 0.8), ("match", 13.9, "whoosh-cinematic", 0.6),
    ("match", 13.97, "impact-bass-1", 0.7),
    ("replay", 0.3, "pop", 0.7), ("replay", 0.78, "click", 0.9), ("replay", 1.38, "click", 0.9),
    ("replay", 2.45, "whoosh", 0.6), ("replay", 2.8, "error", 0.7), ("replay", 3.32, "pop", 0.7),
    ("replay", 7.42, "key-press", 0.9), ("replay", 7.62, "pop", 0.7), ("replay", 9.34, "pop", 0.7),
    ("payoff", 0.33, "click", 0.9), ("payoff", 0.98, "click", 0.9), ("payoff", 2.0, "whoosh", 0.6),
    ("payoff", 2.36, "impact-bass-1", 1.0), ("payoff", 2.5, "chime", 0.7), ("payoff", 2.9, "sparkle", 0.6),
    ("payoff", 4.85, "whoosh", 0.6), ("payoff", 5.95, "pop", 0.8), ("payoff", 7.46, "impact-bass-1", 0.5),
    ("payoff", 7.5, "sparkle", 0.6), ("payoff", 11.6, "whoosh-short", 0.6),
    ("walls", 1.95, "click-soft", 0.8), ("walls", 3.35, "click-soft", 0.8), ("walls", 4.55, "click-soft", 0.8),
    ("endcard", 0.35, "pop", 0.7), ("endcard", 1.25, "whoosh-short", 0.6), ("endcard", 2.25, "sparkle", 0.6),
    ("endcard", 3.05, "click-soft", 0.7),
]
# the riser peaks on the drop (payoff + 2.36 = 122.995)
RISER_AT = START["payoff"] + 2.36

FRAME = 1 / 30
# measured file lengths, so each effect clip ends where its sound does
LEN = {
    "chime": 2.5, "click-soft": 0.37, "click": 0.37, "error": 1.62, "glitch-1": 2.64,
    "impact-bass-1": 2.12, "key-press": 0.4, "notification": 2.46, "ping": 1.32, "pop": 0.72,
    "riser": 10.03, "sparkle": 1.8, "typing": 1.5, "whoosh-cinematic": 5.54, "whoosh-short": 0.57,
    "whoosh": 0.57,
}


def host(sid, start, dur):
    return (f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html"\n'
            f'        data-start="{start:.3f}" data-duration="{dur:.3f}" data-track-index="1" data-track-kind="graphics"\n'
            f'        data-width="1920" data-height="1080"></div>')


def main():
    hosts = []
    for i, (sid, start) in enumerate(SCENES):
        end = SCENES[i + 1][1] if i + 1 < len(SCENES) else END
        hosts.append(host(sid, start, end - start))

    events = [(START[s] + t, f, v) for s, t, f, v in HITS] + [(RISER_AT, "riser", 0.7)]
    events.sort()
    audio = []
    lanes = []  # end time of the last clip on each effects lane
    for n, (t, f, v) in enumerate(events, 1):
        at = max(0.0, t + FRAME - PEAK[f])
        dur = min(LEN[f], END - at)
        lane = next((i for i, e in enumerate(lanes) if e <= at), None)
        if lane is None:
            lanes.append(0.0)
            lane = len(lanes) - 1
        lanes[lane] = at + dur
        audio.append(f'      <audio id="sfx-{n:02d}" class="clip" src="assets/sfx/{f}.mp3" data-start="{at:.3f}" '
                     f'data-duration="{dur:.3f}" data-track-index="{4 + lane}" data-volume="{v}"></audio>')

    html = f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <script src="compositions/_kit.js"></script>
    <style>
      :root {{
        --plaster: #f4ece1;
        --paper: #fff8ee;
        --ink: #3e2415;
        --wood: #5c3a21;
        --resin: #c08a4a;
        --clay: #b5532f;
        --teal: #1f5c5b;
        --crimson: #c8102e;
        --green: #2e7d32;
        --mm-navy: #1e325c;
        --shadow: 0 10px 0 rgba(62, 36, 21, 0.28);
        --font-display: "Archivo Black", sans-serif;
        --font-body: "Outfit", sans-serif;
        --font-mono: "IBM Plex Mono", monospace;
      }}
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      html,
      body {{
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: var(--plaster);
      }}
      #root {{
        width: 100%;
        height: 100%;
        position: relative;
        background: var(--plaster);
        font-family: var(--font-body);
        color: var(--ink);
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{END}"
      data-width="1920"
      data-height="1080"
    >
{chr(10).join(hosts)}
      <audio id="bgm" class="clip" src="assets/bgm/funkorama.mp3" data-start="0" data-duration="{END}"
        data-track-index="3" data-volume="0.5" data-fade-out="2.4"></audio>
{chr(10).join(audio)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
'''
    (VIDEO / "index.html").write_text(html)
    print(f"{len(hosts)} scenes, {len(audio)} effects")


if __name__ == "__main__":
    main()
