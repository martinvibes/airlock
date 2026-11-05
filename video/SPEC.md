# SPEC: Airlock, "The door"

GOAL:    a judge who has never heard of Airlock can say, in their own words: "two companies fixed one
         outage together in chat, and only typed claims an engineer released crossed between them,
         with Switch enforcing the walls". They smile at least twice (the 403 bounce, the REFUSED stamp).
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps.
TIME:    149.1 s x 30 = 4473 frames. Music "Funkorama" (Kevin MacLeod, CC BY 3.0), 101 BPM:
         a beat is 17.8 frames and a bar 71.2 frames. Cuts sit on the measured bar starts
         (beats/funkorama.json): 7.165, 14.285, 21.415, 30.925, 38.055, 52.305, 76.075, 90.325,
         104.295 (breakdown starts), 108.895, 120.635, 122.995 (the drop), 132.505, 139.635, 149.145.

LOOK:    medium: a customs house of plaster, oud wood and paper.
         plaster ground #F4ECE1, flat with 2% noise. Ink #3E2415 for every word that must be read.
         Wood #5C3A21 for walls and doors, with vertical grain lines 2 px wide at 10% darker, 22 px apart.
         Resin #C08A4A is the one accent: door handles, the number 37, and the end card, never on body text.
         Room floors: KudiMart clay #B5532F, Paylane teal #1F5C5B. Airlock's floor is wood #5C3A21.
         Stamp inks: REFUSED / 401 crimson #C8102E, PAID / 200 / delivered green #2E7D32.
         Paper tickets: #FFF8EE, 3 px ink border, radius 10 px, one punched hole of 18 px,
         hard shadow 0 10 px 0 rgba(62,36,21,0.28) (no blur anywhere: cut paper, not glass).
         Display: Archivo Black, titles 96 to 150 px, hero words 220 to 420 px, tracking -2%.
         Body: Outfit 600 at 40 to 56 px. Claims and terminal: IBM Plex Mono 500 at 30 to 40 px.
         Real Mattermost rebuilt at 1.6x: Open Sans 30 px body, its own white panel and #1E325C sidebar.
OBJECTS: receipt card (order id, amount, merchant), rubber stamp (double 6 px border, letter-spaced
         Archivo Black, rotated -8 deg, 92% ink), wood wall (planks with grain, a 12 px darker cap),
         the door (the logo: an arched double door, a gap line, two resin handles, a threshold bar),
         claim ticket (paper + mono text + punched hole), room plan (top-down rooms with 24 px wood walls),
         avatars from the real run (magenta K #C5087E with white letter, red P, the green investigator
         diamond #9BD78D with #0F172A eyes, the door).

MOTION:  enter: expo.out 0.5 to 0.7 s. Camera and colour floods: power2.inOut 0.4 to 0.6 s.
         Exit and zoom-through: power3.in, 40% shorter than the entrance.
         Stamps: scale 1.8 -> 1 and rotate -18 -> -8 deg in 0.16 s power4.in, then the stamped
         object shakes 8 px for 4 frames. Tickets: slide with 12 px horizontal blur peaking mid-move.
         Avatars and tickets may spring (back.out(1.6), about damping 0.5). Opacity and colour never bounce.
         Titles land per word (blur 6 -> 0 px, 0.13 s, 0.07 s apart) and then hold dead still.
         Numbers roll like a counter, about 0.05 s a step.
         Transitions (4 kinds): colour flood, the wall/door becoming the next world, zoom through the door,
         whip (0.2 s horizontal smear). At most a third of the seams are hard cuts.

SHOTS:
  1  hook     0.000-7.165    Receipt gets PAID then PENDING stamps; "37 customers paid." then
                             "Their orders never arrived." The receipt multiplies into 37.
                             Sound: stamp thuds, pops. Hands off: the 37 receipts whip right.
  2  blame    7.165-21.415   Clay | teal split. KudiMart: "97 orders stuck. Your webhooks never came."
                             Paylane: "42 webhooks gave up. We sent every one." Then "Who's right?"
                             "Both. Half each." "The real number is 37, and it takes both companies' records."
                             Sound: band enters, a notification per bubble. Hands off: logs slide up.
  3  wall     21.415-30.925  "So share the logs?" A log scrolls with phones, card digits and refs boxed
                             in crimson. "That's customer data. It can't leave the building."
                             A wood wall slams down the middle. Sound: impact-bass on the wall.
  4  reveal   30.925-38.055  The wall grows an arch, handles and a gap: the logo door. "Airlock" lands.
                             "Fix one incident together. Share only typed claims."
                             Hands off: the door shrinks into the room plan.
  5  rooms    38.055-52.305  Top-down plan: KudiMart room, airlock, Paylane room. Avatars pop in with
                             labels: Engineer (a person), Investigator (Claude Code, its own company's
                             files only), Customs (plain code, no AI). The investigator walks at airlock
                             and bounces: "403 Agent is not a member of this room". "Switch enforces the
                             walls on the server." Sound: pops, error buzz on the bounce.
  6  claim    52.305-76.075  Zoom through KudiMart's door into the real Mattermost war room at 1.6x.
                             The question, the investigator's answer, the typed propose line,
                             "Claim 1 queued, not sent." The investigator tries "release 1": REFUSED.
                             The engineer types "release 1"; the claim becomes a ticket and slides
                             through the door into airlock. Sound: typing, notifications, error, click, whoosh.
  7  meet     76.075-90.325  Teal tickets from Paylane arrive: "signing secret rotated 09:40",
                             "secondary still signed with the old secret". KudiMart's investigator:
                             "Two compounding causes on our side: wrong header accepted, and an
                             un-rotated secret." "Neither side had that sentence alone."
  8  match    90.325-108.895 Wood-dark world. 480 Paylane dots, 443 KudiMart dots, blinded (circles turn
                             to diamonds) and attached as Switch room documents. 443 cancel; 37 stay in
                             resin and fly together into a 420 px "37" on 104.295 as the music drops out.
                             "Only the count crosses. The list stays with Paylane."
  9  replay   108.895-120.635 Both engineers sign. 37 tickets fly at KudiMart and bounce stamped 401.
                             "The canary still reads the wrong header." "KudiMart ships v2.14.1."
                             Riser from 112.97 into the drop.
 10  payoff   120.635-132.505 Both sign again. On 122.995 the 37 go through, green, "37 delivered".
                             The stuck counter rolls 37 -> 0. INCIDENT CLOSED stamp. Sound: impact,
                             chimes, sparkle.
 11  claim    132.505-139.635 "The walls are Switch." Then one line at a time: "Rooms agents can't enter",
                             "Senders Switch verifies", "Documents that stay in their room".
 12  end      139.635-149.145 The door draws, then opens; "Airlock" wipes in beside it;
                             github.com/martinvibes/airlock; "Built on Switch". Music credit line.
                             Music fades over the last bar.

BANNED:  dark navy void; glow, bloom, particles; purple/blue gradients; glass cards; serif or italic
         accent words; "01 / 02" labels; mono caps labels as decoration; pill chips; everything
         centred; fade-and-slide-up entrances; titles that drift after landing; three cards in a row;
         KPI grids; a title over a dimmed screenshot; the logo docked in a corner; blurred drop shadows;
         invented UI claimed as Mattermost; real company or person names; the word "secure".
QA:      frame 0 reads as a thumbnail; every line holds 0.5 s + 0.3 s a word; text >= 28 px;
         each REFUSED / 403 / 401 has its sound one frame after the stamp; the drop at 122.995 lands
         on "37 delivered"; the end card holds at least 2.5 s; the mix is -16 to -14 LUFS.
