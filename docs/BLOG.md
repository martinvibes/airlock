# Two companies, one outage, zero shared logs: building Airlock on Switch

_#HowISwitch · Flip the Switch hackathon · draft_

Here's an incident every Nigerian developer who has touched payments will recognise. A customer pays. The money leaves their account. The order stays "pending". The shop blames the payment provider, and the provider says its webhooks went out fine. Both are telling the truth as far as they can see. Neither can prove it, because the evidence is logs full of phone numbers, card digits and payment references, and you don't paste those into a shared Slack channel with another company.

For the Flip the Switch hackathon I built **Airlock**: two companies investigate a shared failure in team chat, each with its own AI investigator, and **only typed claims that a human releases** cross between them. It runs on [Switch](https://github.com/sandbox-quantum/switch), with Mattermost as the chat and Claude Code as the investigators. Both companies, KudiMart (a shop) and Paylane (a provider), are fictional, and all the data is synthetic.

Repo: https://github.com/martinvibes/airlock

## The bug, and why nobody can see it alone

I wanted an incident where both sides are right about their own half:

- At 09:12, KudiMart ships a new webhook verifier to a 10% canary pod. It reads only the `X-Sig-Primary` header.
- At 09:40, Paylane rotates its signing secret the textbook way: the primary header gets the new secret, and the secondary header keeps the old one for 72 hours.
- KudiMart only has the old secret. The canary checks only the header signed with the new one. Every webhook that lands on the canary gets a 401.

Then I made it worse, on purpose, because that's what real incidents do. KudiMart's verifier rejects before parsing the body, which is good practice, so its 401 log lines don't say *which* payment failed. Its support team has already credited 5 orders by hand after customers complained.

So Paylane's log says **42** webhooks gave up. KudiMart sees **97** pending orders but can't tell paid from abandoned. The truth is **37**, and you need both companies' records to get it.

## Three rooms and two kinds of agent

Each company gets a private Switch room: its engineer, its investigator and its "Customs" agent. There is one shared room, `airlock`, which holds only the two engineers and the two Customs agents.

**The investigators are not in airlock.** That is the first thing Switch gives you for free. Room membership for agents is enforced on the server. When I post, stream or read history for airlock with an investigator's key, I get `403 Agent is not a member of this room`. That's not a prompt instruction the model might ignore. The server won't send it the messages.

The investigators are Claude Code, each running inside one company's folder with no shell, no edit tools and no web, in `dontAsk` permission mode. One gotcha I hit: passing `--allowedTools Read` lets Read open files *anywhere*. I tested it: it happily read a file in a sibling folder. Leaving Read off the allow list is what keeps it inside the working directory.

**Customs** is the part I'm proudest of. It's plain Python on Switch's agent protocol, with no language model. You can't prompt-inject something that has no prompt. An investigator that wants to tell the other company something has to write a typed claim:

```
@kudimart-customs propose {"kind":"finding","code":"merchant_verifier_reads_primary_header_only"}
```

Customs checks it against a fixed vocabulary. There is no free-text field anywhere: every field is an enum, a bounded integer or a strict regex. It queues the claim and says "Only KudiMart Engineer can send it: `release 1`". If the investigator types `release 1` itself, Customs refuses, because it checks the **sender id Switch attached to the message**, not the text. That id is the second thing Switch gives you. In Mattermost, the engineer's account is linked to their Switch user through an identity claim that the account has to confirm.

## Agreeing on "37" without swapping lists

To count the stuck payments, the two Customs run a small private set intersection: Diffie-Hellman PSI, standard library only, over the RFC 3526 group. Paylane blinds its 480 payments with a secret exponent. KudiMart re-blinds them and blinds its 443 credited orders with its own. Paylane compares the two and finds 37 with no match. That list never leaves Paylane, and only the number is posted.

The blinded payloads are about 250 KB and 470 KB, far too big for a chat message. So they go in **Switch room documents**, attached to airlock, and the claim carries only the document id and a SHA-256. That's the third Switch primitive I didn't have to build.

I'm careful about how I pitch this. It's semi-honest PSI: it assumes both sides follow the protocol, and it reveals the count and the set sizes. In real life KudiMart could also check its pending orders one at a time against Paylane's verify API. What the match gives you is one consented step for the whole window, and a replay list that stays with the company sending the replay.

## The ending

Paylane's Customs proposes replaying the 37 webhooks. **Both** engineers have to `sign`. Before the fix, the replay really fails: the local webhook endpoint checks real HMAC signatures, and all 37 come back 401. KudiMart ships v2.14.1. Its investigator confirms the fix from its own files. Both sign again, and 37 are delivered. Customs re-runs the match on its own and gets **0 stuck**, then posts `incident_closed`.

My favourite moment came during testing, not in the script. After Paylane released its findings ("primary signed with the new secret, secondary still with the old"), KudiMart's investigator picked them up, re-read its own `verifier.json`, and worked out that KudiMart had never rotated its secret. Neither side had that sentence on its own. In another run the investigator was confidently wrong: it proposed "accepts either header" before the fix had shipped. The engineer typed `reject 5`. That's the design working.

## Things I learned about Switch

If you're building on Switch, these will save you an afternoon each:

- **Participant ids are opaque.** The sender id on a message isn't the agent id or the user id you created. I pair them at setup: every participant posts a one-time nonce, and I record the sender id Switch attaches to it.
- **One connection per room.** A single-scope connection holds one room, so Customs keeps two connections (its private room and airlock) and feeds both into one worker thread.
- **Documents belong to the connection's room.** `create_room_document` attaches to whatever room the calling connection holds. Loading it from another room is refused. That's exactly what you want for a trust boundary.
- **Document names are unique per room.** My run ids restarted at `run-1` whenever Customs restarted, and the second `psi-run-1-round1` was rejected. I added a random suffix.
- **New agents are owner-only.** Customs needs an addressing policy that lets it hear the other company's Customs in airlock.
- **Identity links must be confirmed.** Claiming a Mattermost account for a Switch user counts for nothing until the account confirms it. Setup does that with the account's own session.
- **The bundled Mattermost user joins every channel the bridge creates.** That's fine for a solo dev setup, but not for "private" rooms, so setup removes it from the two war rooms.

## Honest limits

The README has the full list. Briefly: server admins can read every room. In the demo both companies' agents run on one laptop. PSI is semi-honest. Nothing here has been audited. The data is synthetic.

## Why Switch, really

Take Switch away and you're left with a shared chat channel and some bots that promise to behave. Airlock's boundary *is* Switch: server-side room membership for agents, verified sender identity, separate owners per company, and room documents. Airlock itself is a few hundred lines of policy on top.

I built it with Claude Code as a pair programmer over the hackathon. The commit history in the repo tells the story step by step.
