# Review: Airlock demo film

2:29 (149.1 s), 1920×1080, 30 fps. 12 scenes cut on the bar lines of "Funkorama" (101.1 BPM).

## Check

`npx hyperframes check` passes with no errors. Two reading-time warnings are kept on purpose:

- `#cl-p2` (55 s): a 60-word investigator post in the rebuilt Mattermost. It is the real message;
  its key phrase ("checks only the X-Sig-Primary header") is highlighted, which is what the viewer reads.
- `#mt-inj` (76 s): the prompt-injection bubble. It shows for about 2 s before the REFUSED stamp
  covers it; the stamp carries the point.

## Frames looked at

The 34 stills in `boards/stills/` (one or more per scene), plus re-shoots of every fix.

Fixed in this pass:

- `AK.shake` was a `fromTo` that wrote `x: 0` at build time, which overrode off-screen starts.
  The clay and teal halves covered the payments sheet for the whole wall scene. It now uses
  `immediateRender: false`.
- Blame card: the half-hidden 97 and 42 now fade as the card lands.
- RELEASED stamp: it was clipped at the right edge after the slide and covered "from KudiMart".
  It now sits above the ticket (claim and meet).
- Payoff: the INCIDENT CLOSED stamp no longer hits "stuck"; the 37 to 0 counter is right-aligned.
- The injection bubble dims behind REFUSED.

## Sound

- Music bed at 0.5, fading over the last 2.4 s.
- 87 effects, each placed so its measured peak lands one frame after its picture.
- The riser peaks on the drop (123.0 s), where "37 delivered" lands.

## Data

Synthetic only: order KM-100139, the 5 payments.csv rows and the Mattermost texts come from the
`-demo` run. KudiMart and Paylane are fictional. Music credit is on the end card and in CREDITS.md.
