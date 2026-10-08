# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A static single-page web app: a hunting logbook for Monster Hunter 4 Ultimate, ported from the
[MH3U Hunting Log](../mh3u-hunting-log) (itself a port of the
[MHGU Hunting Log](../MHGU%20Hunting%20Log)). The user picks a quest and records what they were
after, what they wore, who came along and how it went; entries accumulate into a running log they
can copy out as plain text.

No build step for the app, no framework, no modules. `docs/app.js` is one IIFE, `docs/styles.css`
is hand-written, `docs/data.js` is generated.

GitHub Pages serves `docs/` through the "Deploy Pages" Actions workflow on push to `master`, like
the other MH apps.

## Relationship to the 3U Hunting Log

A port, not a fork that tracks it. The editor, logbook, farming/timestamp modes, drafts, save
files and copy format are the GU app's, and its CLAUDE.md explains the reasoning behind each
(resetEditor vs exitEditMode, the dirty gate, why Locale survives a quest switch, the clear-time
mask). What changed for 4U:

- **Boards**: Caravan 1-10★, Gathering Hall 1-7★ then G1-G3★ (stored as stars 8-10), Arena
  (Grudge Matches, same labels as the Hall), Training, and the three Expeditions (Low/High/G Rank).
- **Quest key** is `"q" + Id`, the game's quest number, as in 3U (names repeat across boards).
- **Icons**: `q.Icon` is the icon the game itself puts on the quest (slot 0 of the quest file's
  icon list), named by the build script.
- **Urgent / Key** are flag bits in the quest file, not an unlock rule. The quest head shows the
  subquest (`q.Sub`, `q.SubReward`) where 3U showed the unlock text.
- **Frenzy / Apex** pills come from the OUTBREAK markers in the quest's icon list.
- 14 weapon classes (Charge Blade, Insect Glaive added).
- **Guild Quests** are one pickable entry (`q.Relic`, number 45100) with per-entry `relicLevel`
  (1-140) and `guildTargets` (up to two monsters from `q.Pool`). The Guild Quest row is enabled
  only while it is selected and is cleared when you pick anything else. The display is
  "Guild Quest Lv 85 / Rajang + Kirin"; `entryTargets()` / `entryIcon()` feed the card, the copy
  text and the Monster grouping. The pickers follow the level: `q.RankMax` brackets it into Low /
  High / G (Lv 1-30, 31-85, 86-140), `q.Pool` holds each monster's ranks, and `q.Swaps` replaces
  monsters inside level ranges (Furious Rajang 76-85, Apex 136-140, Chaotic Gore Magala 126-140).
  A pick carries across a level change as the same monster (`carryPick`) and clears only when it
  can't appear. With no level, the whole pool shows. The second picker follows the game's rules
  (`q.Solo` come alone, the `q.NoPair` Najarala never pair). Objective stays the hunter's note on why they hunted.
- Storage keys are `mh4u-log-*`; save files are `{ app: "mh4u-hunting-log", version: 1, entries }`.
- The theme palette is the MH4U Collection Tracker's (same hexes and LEGACY_HEX as every family).

## Data

`python scripts/build_data.py "C:\MH4U-Extract"` rewrites `docs/data.js`
(`window.MH4U_LOG_DATA = { quests, weapons, weaponIcons, icons }`) and the icon folders. The quest
files must be extracted first (`python tools\arc4.py extract "loc\quest\m"` in the extract). The
script header documents the quest file layout. Findings worth knowing:

- `loc\quest\mNNNNN` in `quest00.arc` / `quest01.arc` are the cart's quests, with their text in all
  five languages inside the file. 1 is a dev stub, 100 the prologue, 451xx/452xx Guild Quest
  templates; all three are skipped. 6xxxx (DLC) are not on the cart.
- **Key** (flag 0x20) matches Kiranico's Gathering Hall Key badges on 1-3★ and 6-10★; 4★ and 5★
  differ by a few quests and the game's flag is used. Don't "fix" it toward Kiranico.
- The **Caravan** opens up by story events, so its Key flags cover only some of the quests
  Kiranico calls Key, and the story quests (Research: …, Gore Magala Drama, the 3★ "???") carry
  no Urgent flag. The story unlock tables in the executable are not decoded.
- Variant monsters (Apex, Furious Rajang, Chaotic Gore Magala…) share their base name in the
  game's monster list; `VARIANTS` in the build script names them.
- The monster → icon cell table isn't traced; the build votes it from the quest files.

**Guild Quests** are generated at run time; the cart's 451xx/452xx files are blank templates.
The build emits a single "Guild Quest" entry (`guild_quest()`) carrying the monster pool read from
the generator's tables (GUILD QUEST MONSTERS in the script header: 54 monsters, per rank, with the
quests that unlock them). Its locale is the hunter's to type.

## Critical: cache busting

Bump the `?v=N` on `styles.css`, `app.js` or `data.js` in `docs/index.html` whenever that file
changes.

## Conventions

All user text goes into the DOM via `textContent`/`.value` through `el()` — never `innerHTML`.
An entry's `quest` snapshot is read back from save files as untrusted shape (`questTargets`
guards it).
