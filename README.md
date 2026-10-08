# MH4U Hunting Log

A logbook for **Monster Hunter 4 Ultimate**. Pick a quest, record what you were after, what you
wore, who came along and how it went, and build up a running record of your hunts. A port of the
[MH3U Hunting Log](https://github.com/ArmoredRaven17/mh3u-hunting-log) and the
[MHGU Hunting Log](https://github.com/ArmoredRaven17/MHGU-Hunting-Log), with its quest data read
from the game itself.

```
Quest: Gathering Hall G3★ / Advanced: Beyond Brawn / Apex Rajang
Locale: Ancestral Steppe
Weapon: Ziggurat
Hunting Party: Raven
Carts: 0
Outcome: Success
```

That's what **Copy Selected** produces, ready to paste into Discord.

## Features

- **Quest browser**: all 472 quests on the cartridge (180 Caravan, 259 Gathering Hall, 16 Arena
  Grudge Matches, 14 Training, 3 Expeditions) plus a Guild Quest entry, grouped by board and star in the game's own order,
  searchable by name, monster or locale. Picking one fills in its locale and shows its objective,
  subquest, time limit, fee, reward and client, with Urgent, Key, Frenzy and Apex pills.
- **Per-entry fields**: date, locale, your own objective, a Relic Level for Guild Quests (open only
  while one is selected), armor, weapon (with a class picker
  that supplies the game's class icon and every weapon name as autocomplete), a party of up to
  four, carts, outcome, clear time and notes.
- **Farming** and **Timestamp** switches, autosave, `.json` save files, and the MH4U monster-icon
  themes shared with the other MH4U apps, all as in the GU log.

Downloadable Event Quests aren't on the cartridge, so they aren't listed. Guild Quests are
generated rather than stored, so they share one entry: you give the relic level and pick its
monsters from the ones the game's Guild Quest tables allow at that level (Low Rank up to Lv 30,
High Rank to 85, G Rank to 140, with Furious, Apex and Chaotic monsters at their levels).

## Where the data comes from

[scripts/build_data.py](scripts/build_data.py) reads a local extract of a personally owned copy of
the game: the quest files (`loc\quest\mNNNNN` in `quest00.arc` / `quest01.arc`, which carry their
own text along with star, map, objectives, money, monsters and icons), the English message tables
(monster, item, weapon and map names), the icon atlases, and one table in the executable (the
quest order). The script's header documents every field. Star, locale, Urgent and Key were
cross-checked against Kiranico's MH4U quest lists; no data is taken from it.

## Running it

No build step for the app. Open `docs/index.html`, or serve `docs/`:

```
python -m http.server 5592 --directory docs
```

## Regenerating data

Needs the extract laid out like `C:\MH4U-Extract` (romfs unpacked, arcs extracted, `code.bin`
decompressed), Python 3.10+, Pillow and numpy:

```
python scripts/build_data.py "C:\MH4U-Extract"
```

This rewrites `docs/data.js`, `docs/assets/MonsterIcons/` and `docs/assets/WeaponIcons/`.

## Cache busting

GitHub Pages caches assets by full URL. When you change `styles.css`, `app.js` or `data.js`, bump
the `?v=N` query string on its tag in `docs/index.html`.

## AI assistance

Most of this project (the port, the quest decode and this README) was written with
[Claude Code](https://claude.com/claude-code), Anthropic's AI coding tool, working from the author's
direction and reviewed before landing.

## Licensing

Code is MIT (see [LICENSE](LICENSE)). Game data and icons are Capcom's; see [NOTICE.md](NOTICE.md).
Monster Hunter 4 Ultimate is © Capcom Co., Ltd.; this is an unofficial fan project.
