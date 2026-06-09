# ivg-kg

**Interactive Visual Grounding of LLM Responses in Multimodal Knowledge Graphs.**

`ivg-kg` is an interactive visual-analytics instrument that makes the grounding of
LLM answers against a knowledge graph *inspectable*. Each claim in an answer is
attributed to its supporting KG evidence and classified as **retrieved** (a direct
triple supports it), **reasoned-supportable** (a multi-hop path supports it), or
**fabricated** (no supporting evidence). On top of that, an analyst can withhold
evidence (text content, structural triples, or image content), watch how grounding
changes, and measure which repairs resolve the most downstream fabrication. The
interface is three coordinated Dash panels: the answer (colour-coded by status), the
supporting subgraph, and analytics.

> **Status:** P0 foundation — data layer, typed schema, perturbation interface, and the
> Dash UI skeleton run on **mock fixtures**; real grounding (claim extraction, entity
> linking, the entailment-gated classifier) lands in P1. The app is fully runnable now
> on the mock data.

## Prerequisites

This repo is driven by [**go-task**](https://taskfile.dev) over [**uv**](https://docs.astral.sh/uv),
so every common action is a one-liner. Install both (macOS / Homebrew):

```sh
brew install go-task/tap/go-task   # the `task` runner
brew install uv                    # Python env + dependency manager
```

## Setup

Create the virtualenv and install dependencies (core + dev + data extras):

```sh
task setup
```

## Run / stop the app

```sh
task run      # start the Dash app in the background -> http://127.0.0.1:8050
task stop     # stop it
```

Other lifecycle helpers:

```sh
task status   # is it running?
task restart  # stop + run
task logs     # tail the app log
task dev      # run in the foreground with hot-reload (Ctrl-C to quit)
```

Override the bind address/port with variables, e.g. `task run PORT=9000 HOST=0.0.0.0`.

## Other common tasks

```sh
task          # list every available task
task test     # run the test suite (e.g. `task test -- -k schema`)
task lint     # ruff
task check    # lint + test (mirrors CI)
task freeze   # rebuild the frozen books KG slice from live Wikidata (build-time)
```
