# HoloVec

An Old Republic reference collection for search and retrieval.

The collection can include lore references, game material, guides, bibliographic records, related discussion and vector representations. Vector publication remains on hold while the source collection is still being completed.

[Usage](docs/usage.md) · [Full source catalog](docs/sources.md)

Mirrored to the Hugging Face dataset: [sync design and runbook](docs/sync-huggingface.md).

Codeberg sync (GitHub to Codeberg, fast-forward only, plus review-only inbound PRs): [docs/sync-codeberg.md](docs/sync-codeberg.md)

## 📚 Sources at a glance

| | Category | What is tracked | Publisher / host | Status |
|:---:|---|---|---|:---:|
| 🎮 | Games | KOTOR I and II resource metadata; SWTOR class stories, expansions and updates | Steam depot data for KOTOR I; SWTOR via swtor.com | 📇 🔎 |
| 📖 | Novels | 16 works: Old Republic novels, Darth Bane, Lost Tribe of the Sith, Dawn of the Jedi, reference books, bundles (2007–2024 editions) | Penguin Random House | 🔎 |
| 💥 | Comics | 24 series, 162 issues (1992–2013), 11 collected editions | Dark Horse series; Marvel and PRH Comics catalogs | 🔎 |
| 🕸️ | SWTOR webcomics | *Threat of Peace* (27) and *Blood of the Empire* (12) | swtor.com | 🔎 |
| 🎲 | Tabletop and miniatures | Campaign Guide supplements, creature articles, adventures, 8 miniatures scenarios, *Tales of the Jedi Companion* | Wizards of the Coast, West End Games, DK | 🔎 🟡 |
| 🛰️ | Official SWTOR web fiction | 23 short stories, 33 companion features, patch-note index (373 links) | swtor.com | 🔎 |
| 🌐 | Community and wikis | Wookieepedia, Wikipedia, StrategyWiki, PCGamingWiki, Arqade, SFF Stack Exchange, mission checklists | Fandom, Wikimedia, Stack Exchange and others | 🟡 |
| 📄 | Original documents | Combat guide (StatsJedi), two scholarly papers, a research dialogue corpus | CC-licensed or rights-held | ✅ 📄 🚧 |
| 🚫 | Excluded | Software source code and tooling documentation | n/a | 🚫 |

| Icon | Meaning | Entries |
|:---:|---|---:|
| ✅ | Ingested | 1 |
| 🟡 | Partially ingested or screened | 17 |
| 📇 | Metadata only | 4 |
| 📄 | Original document preserved, no text layer | 2 |
| 🚧 | Held pending rights review | 2 |
| 🔎 | Discovery lead only, nothing ingested | 79 |
| 🚫 | Outside the corpus boundary | n/a |

> ⚠️ Most entries are leads, not content. A listing is evidence that a work exists, not permission to redistribute it.

The full itemized list, with titles, editions, ISBNs and per-source status, is in **[docs/sources.md](docs/sources.md)**. It is derived from [`catalog/sources/source-inventory.json`](catalog/sources/source-inventory.json) and [`catalog/works/`](catalog/works/).
