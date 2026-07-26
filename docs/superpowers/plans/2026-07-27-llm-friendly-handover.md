# Making Ctrl+Grid easy for an LLM to drive. Handover

**Date:** 2026-07-27. Written at the end of the 0.12.0 session, at the user's
request, because the idea is worth doing and the session that had it was running
out of context. **Nothing here is built.** It is a starting point for a design
conversation, not a plan — the forks in section 5 need the user before any code.

## 1. The idea, and the framing that keeps it inside § 2

A user says *"a booklet of 5 mm hex paper for my D&D group, A5"* and gets a
sheet. The language part happens in an assistant; **the tool does not talk to an
LLM, it is easy for an LLM to talk to.**

That framing is not a preference, it is what § 2 and § 10.1 already require. A
built-in natural-language mode would mean a model or an API key inside a tool
whose promises are *no network*, *same input → same bytes* and *never guess*. So
ctrlgrid ships the **contract** an assistant holds on to, and nothing more.

Why it is worth doing at all: 1.0.0 has always been waiting for the DSL to meet
someone other than the test suite. An assistant writing definitions is a user of
the DSL — a demanding one, and one that reports its confusion in writing.

## 2. What already works in the tool's favour (do not rebuild this)

**It refuses instead of guessing, and that is the whole reason the loop can
converge.** An unknown key is an error (§ 5.1), not an ignored field, so an
invented option produces a message rather than a plausible wrong PDF. And § 12
requires every message to name the field, the line and the numbers — so a wrong
definition tells the writer exactly what to change.

On top of that: `ctrlgrid check` validates and writes nothing; `ctrlgrid show
<preset>` prints a real definition to bend; the presets *are* the documentation
(§ 9.3); and the media check (§ 12.1) already says things like *"line weight
0.2pt = 0.64px at 229dpi"*, which is precisely the sort of thing an assistant
should relay to a user.

So *write → check → correct* already works today. What follows makes it converge
faster and lets the assistant ask better questions.

## 3. What to build, in order of value over effort

**(a) A schema command — the biggest win for the least work.**
`ctrlgrid schema [generator]` printing JSON Schema. Verified during this session:
`REGISTRY['tiling'].config_model.model_json_schema()` already returns a complete
2352-byte schema with all nine keys — pydantic gives it for nothing, and the CLI
would only have to print it. The handle sections (`page`, `header`, `pattern`, …)
are pydantic too.

*Honest limit:* a JSON Schema cannot express the generator-local unit `sp`
(§ 5.1), the relative measures `%w`/`%h`/`%s` (§ 8.11), or what a cycle *means*
(§ 5.3). Those stay prose, which is what (b) is for.

**(b) One page written for machines — and it should probably be a *skill*.**
(Raised by the user, 2026-07-27, and it is the better shape.) The handbook is
~1600 lines; an assistant needs perhaps 150 of them: the shape of a definition,
the generator table, the units, the cycle model in one paragraph, the refusals it
will actually hit, and the workflow — write, `check`, correct, build, then relay
the print instruction. A skill is exactly that document in the format an
assistant already loads on demand, with a description that decides when it is
loaded at all ("printable paper, a planner, a booklet, graph paper for a pad…").
It also carries what no schema can: which questions to ask (section 4), and the
§ 8.2 sentence about printing at 100 %, which is the one thing a user must be
told and no file can enforce.

**The one rule that decides whether it stays true: it must point, not copy.**
`ctrlgrid schema`, `ctrlgrid presets`, `ctrlgrid devices` and `ctrlgrid show` are
the truth; a skill that lists keys is a second description of the same thing and
will go stale. This is not a hypothetical — in *this* session the handbook was
found to hold two lists of the switch-style flags, one of which had never learnt
`--crop-marks`. Same failure, one level up. So the skill teaches the *shape* and
the *questions*, and asks the tool for the *facts*.

Where it lives is an open question (see section 5): in the repository so it
versions with the tool and a user can install both at once, or as a separate
plugin so it can be updated without a release. The repository has no `.claude/`
skills directory today — only `settings.local.json` — so either way it is new
ground here.

**(c) `--json` as an envelope, never a replacement.** Errors already carry a
field path and a source line; wrapping them alongside the prose closes the loop
without touching the messages themselves — § 12 calls them the face of the tool,
and the face does not change because a machine is also listening. Same for the
run report, which carries the notices (§ 8.3), the media findings (§ 12.1) and
the print instruction (§ 8.2).

**(d) `ctrlgrid generators --json`** — name, one line of purpose, required keys.
Discovery: today an assistant has to read prose to learn that `tiling` exists.

## 4. The sharpening the user added, and it is the interesting part

An assistant that asks about everything is worse than one that guesses well. The
useful thing is not *all* the options — it is **which decisions the tool
deliberately refuses to make on the user's behalf.**

Ctrl+Grid already knows that set. It is written in the specification and nowhere
in the code, and it is **small** — roughly a dozen fields. Grounded sites, each
checked against the text during this session:

| Where | What the specification says |
|---|---|
| § 8.3.1 (line 1625) | `snap: pixel` is "**niemals der Default**: Das Werkzeug darf diese Abwägung nicht für den Nutzer treffen, aber es muss sie ihm zeigen" — exact measure against even cells |
| § 7.2 (line 615) | a `dots` colour cycle without `axis` is a validation error, because "jede Mischregel wäre geraten" |
| § 8.9 | `cut: false` is the default because a silently truncated name is data loss — thirty sheets should fail, not print wrong |
| § 8.7 (line 1725) | freeing the hole marks by widening `margin.inner` is "eine Gestaltungsentscheidung und bleibt beim Nutzer" |
| § 7.8 (line 988) | `choice` offers boxes and never enforces exclusivity — "auf Papier entscheidet der Stift" |
| decision 26 | `min_path_factor` defaults to 0 because "the demand is the user's to make" |
| § 8.3 | with two families on one axis, `governing` must be marked — a real disagreement is an error naming both |

Everything else has a default that is deliberately good, and an assistant should
take it silently.

So a field would carry one of four states, and only the third and fourth ever
produce a question:

| State | What an assistant does |
|---|---|
| required | derive from the request, or ask |
| defaulted, uncontested | take it, do not mention it |
| **a trade-off the spec says the user must see** | ask, with both sides — § 8.3.1 already writes the sentence |
| **refused rather than guessed** | ask as soon as the context raises it |

The fourth state is already *implemented* — the refusal exists. What would be new
is making it visible before the run rather than after it.

**The discipline is the whole design.** A marker may only sit where the
specification says outright that the user decides. The moment someone assigns
them by feel, the assistant starts asking about `weight` and `color` and the
feature turns into its own opposite.

## 5. The forks that need the user before any code

1. **Where the markers live.** In the pydantic fields via
   `Field(json_schema_extra=…)`, so the schema carries them and they sit next to
   the thing they describe? Or in one curated table, so the small set stays
   visible and cannot sprawl? The first keeps them from drifting from the field;
   the second keeps them from multiplying.
2. **What a question looks like.** Free text per field, or a structured
   `{question, options, consequence}`? § 8.3.1 has already written one in prose
   ("exakt 5,000 mm / ungleichmäßige Zellen" against "4,991 mm / völlig
   gleichmäßig") — a structure that cannot hold that table is the wrong
   structure.
3. **Does the medium get a special place?** Paper versus device is the most
   consequential branch in the whole tool (§ 9.2: the aspect ratio is not A4, and
   a 0.2 pt line is 0.64 px), and it is *one* question that changes everything
   downstream. It may deserve to be asked first and separately rather than as one
   marked field among twelve.
4. **Where the skill lives, and what it is allowed to state.** In the repository
   (versions with the tool, installs with it, but a wrong sentence needs a
   release to fix) or as a separate plugin (fixable any time, but it can drift
   from the version it describes). And: is it allowed to contain *any* key names
   at all, or must every fact come from `ctrlgrid schema` at use time? The strict
   answer is easier to keep true and slower to read; the loose one is the
   handbook's mistake waiting to happen again.
5. **How far does `--json` go?** Errors only, or the run report too? The report
   carries the media findings an assistant should relay, so probably both — but
   that is a second command surface to keep true.

## 6. What not to build

- **No natural-language mode in the tool.** § 2, and the reproducibility promise.
  The language belongs in the assistant.
- **An MCP server: not yet.** Legitimate as a wrapper *around* the tool rather
  than a plugin *into* it (§ 2 forbids the latter), but it is a second surface
  that has to be maintained and versioned. Do (a) and (b) first and see whether
  anything is still missing; a schema plus one machine-readable page may be the
  whole of it.
- **Do not soften the refusals to make life easier for a generator.** They are
  why the loop converges. A tool that accepted a guess would produce a sheet that
  is *almost* right, which § 5.1 calls the worst failure class there is.

## 7. How to start

The recipe has not changed: settle the forks in section 5 with the user, write
the design to `docs/superpowers/specs/`, then a plan, then test-first with the
*why* and its § number in the comment, one coherent commit each, and the
specification, `implementation-decisions.md` and `docs/CLAUDE.md` updated in the
same breath.

A skill changes the order slightly, and for the better: **(a) and (b) are then a
matched pair.** The schema command is the truth that would go stale in prose; the
skill is the prose that cannot go in a schema. Building the schema first makes the
skill shorter *and* more durable, because it can point instead of list.

Note that (a) and (b) together are small — one command and one document — and
they need almost none of section 5, because the markers are what the forks are
about. Building those two first, and treating section 4 as a second step, is
probably the right order: it puts something usable in an assistant's hands
quickly and lets real use decide how much of the marker system is wanted.
