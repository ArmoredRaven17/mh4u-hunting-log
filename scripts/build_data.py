r"""Build the hunting log's quest data and icons from a local MH4U extract.

    python scripts/build_data.py [C:\MH4U-Extract]

Reads only the game itself and writes:

    docs/data.js                          window.MH4U_LOG_DATA = { quests, weapons, weaponIcons, icons }
    docs/assets/MonsterIcons/MH4U-*.png   the game's monster and quest-type icons
    docs/assets/WeaponIcons/icon_*.png    the game's weapon-class icons

The extract layout is the MH4U Collection Tracker's: romfs unpacked from the cart image, ARC
entries under arcx\ (the extract's tools\arc4.py; the quests need
`python arc4.py extract "loc\quest\m"`), code.bin decompressed. 4U's text is LMD (lmd_messages).

QUEST FILES -- romfs loc/data/quest00.arc and quest01.arc, entries loc\quest\mNNNNN (type hash
1bbfd18e), one per quest; a few sit in both arcs, byte for byte. DLC quests are not on the cart.
  Header: u32 quest info offset (0xa0), 'v005', then section offsets. +0x28 -> a 0-terminated list
  of large-monster waves; each wave is a run of 0x28-byte records, u32 monster number first,
  0xffffffff ends it. The waves are every large monster the quest spawns, intruders included.
  Quest info (at +0xa0):
    +0x00 u8   quest type: 1 slay, 2 capture, 3 hunt, 4 deliver, 8 several monsters ("Hunt all
               large monsters", or a pair whose objective names only one), 16 special (repel,
               "Return on the Wagon")
    +0x01 u8   flags: 0x04 repel allowed ("Slay a Fatalis or repel it"), 0x10 Urgent, 0x20 Key
    +0x04 u32 x4  contract fee, reward, reward lost per cart, subquest reward
    +0x14 u32  time limit (minutes)
    +0x1c u32  -> five language tables (English first) of seven string offsets: name, main
               objective, failure condition, description, small monsters, client, subquest.
               Strings are UTF-16LE, 0-terminated, in the quest file itself.
    +0x20 u16  quest number (= the file name), +0x22 u8 star, +0x24 u8 map (mapName id)
    +0x2b u8   how the two main objectives join: 1 one, 2 both, 3 either
    +0x2c 8 bytes x3   objectives: two main, then the subquest. u8 kind (1 slay/hunt, 0x81
               capture, 2 deliver -- target = item number, 4 break/wound/mount), u8, u16,
               u16 target (monster or item number), u16 count
    +0x48 u16 x5  the quest's icons on the board (cells of cmn_micon; 98 = none). Slot 0 is the
               quest's own; later slots add the other monsters and the markers 84 (DANGER) /
               88 (OUTBREAK: frenzied monsters) / 123 (the red OUTBREAK: Apex monsters).
  Star, map, Urgent and Key were checked against Kiranico's MH4U quest lists. Urgent agrees on every
  board except the Caravan's story quests (Research: Basarios / Yian Garuga / Kirin, Gore Magala
  Drama, the 3* "???"), which Kiranico calls Urgent but which carry no flag: the story adds them,
  and the log doesn't mark them. The Key flag agrees with Kiranico's Gathering Hall Key badges on
  1-3* and 6-10* exactly; at 4* (Tetsucabra Bounty, Operation Catch-a-Kecha, Material Effect vs
  Kiranico's Purple People Eater, Buffoonish Baboon, Dastardly Duo) and 5* (Royal Rumble vs
  Writer's Block, Temper Tantrum) they differ, and the game's flag is used. In the Caravan the
  flag is on only some of Kiranico's Key quests (Boulder-bash, Shipshape Skin...): the Caravan
  opens up by story events, which aren't decoded. An Urgent can carry the Key bit as well (the
  G3 Operation chain); it is shown as Urgent only.

QUEST ORDER -- exefs code.decompressed.bin 0xefce2a: u16 quest numbers in three 0-separated runs,
  the offline quests, the Gathering Hall (with the Arena), then the DLC numbers 6xxxx. The cart's
  quest order; the log sorts by it.

LOCALES -- mapName (abbreviated: "A. Steppe"), spelled out where the game spells them: the six
  Guild Card map stickers (GuildCard 291-296) and its quest-count awards (1795, 1799) for Tower
  Summit, Speartip Crag and Castle Schrade.

ICONS -- cmn_micon (RGBA4444): 34 px icons on a 36 px pitch, seven columns; cells 0-97 run down the
  left half (x = 1 + 36 col), 99 on down the right (x = 257 + 36 col). The quest files name cells,
  not monsters, and the game's monster -> cell table isn't traced, so the build pairs them from the
  quests themselves (a single-target quest's slot 0; a quest whose icons line up one-to-one with
  its waves) and takes each monster's most common cell. Apex monsters share their base monster's
  cell. Cell 0 is the "?" the game shows for Dalamadur, Fatalis and Gogmazios.

Needs: Python 3.10+, Pillow, numpy. pica_la4.py (beside this script) decodes the textures.
"""
import collections, glob, json, os, re, struct, sys

EXTRACT = sys.argv[1] if len(sys.argv) > 1 else r'C:\MH4U-Extract'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CODE = open(os.path.join(EXTRACT, 'exefs', 'code.decompressed.bin'), 'rb').read()
BASE = 0x100000
QUESTS = glob.glob(os.path.join(EXTRACT, 'arcx', 'loc', 'data', 'quest0*', 'loc', 'quest', 'm*.1bbfd18e'))
ENG = os.path.join(EXTRACT, 'arcx', 'eng', 'data')
MSG = os.path.join(ENG, 'core_common', 'eng', 'msg')
TEXTURES = os.path.join(ENG, 'core_common', 'eng', 'lyt', 'common', 'texture')
MONSTER_TEX = os.path.join(TEXTURES, 'cmn_micon_BM_MQ_NOMIP.241f5deb')
ICON_TEX = os.path.join(TEXTURES, 'cmn_icon_GSM_NOMIP.241f5deb')

QUEST_ORDER = 0xefce2a


def lmd_messages(path):
    """LMD (type 62440501) -> messages by the id the game asks for. Message i -> entry i of the
    first table (u32 hash, u16 first op, u16 flags; 0xffff = empty) -> a run of 16-byte ops:
    1 = string pool index, 2 = inline tag, 22 = end. Strings are (u32 offset, u32 length, u32
    length) -> UTF-16LE. Same reader as the Collection Tracker's."""
    b = open(path, 'rb').read()
    assert b[:4] == b'lmd\0', path
    nmsg, nops, nstr = struct.unpack_from('<3I', b, 8)
    oops, ostr = struct.unpack_from('<2I', b, 0x18)
    pool = []
    for i in range(nstr):
        p, n, _ = struct.unpack_from('<3I', b, ostr + 12 * i)
        pool.append(b[p:p + 2 * n].decode('utf-16-le'))
    out = []
    for i in range(nmsg):
        k = struct.unpack_from('<IHH', b, 0x24 + 8 * i)[1]
        s = ''
        while k != 0xffff and k < nops:
            op, arg = struct.unpack_from('<2I', b, oops + 16 * k)
            if op == 22:
                break
            s += pool[arg] if op == 1 else ''
            k += 1
        out.append(s)
    return out


def msg(name): return lmd_messages(os.path.join(MSG, name + '_eng.62440501'))


EM = msg('emName')
ITEMS = msg('itemName')
COMMON = msg(os.path.join('common', 'Common'))
MENU = msg(os.path.join('common', 'Menu'))
MAPS = msg(os.path.join('common', 'mapName'))
CARD = lmd_messages(os.path.join(ENG, 'core_lobby', 'eng', 'msg', 'lobby', 'GuildCard_eng.62440501'))

# mapName id -> locale. The game abbreviates the six main maps and three others in mapName; the
# Guild Card spells them out (see LOCALES in the header).
LOCALES = {i: s for i, s in enumerate(MAPS) if s}
for i, card in zip((1, 2, 3, 4, 15, 5), range(291, 297)):     # A. Steppe ... V. Hollow, H. Mount
    LOCALES[i] = CARD[card]
for i, pat in ((7, r'(Tower Summit)'), (8, r'(Speartip Crag)'), (10, r'(Castle Schrade)')):
    LOCALES[i] = re.search(pat, CARD[1795] + ' ' + CARD[1799]).group(1)

# Monster numbers whose emName entry repeats the base monster's name. The game tells them apart by
# icon (or not at all, for Apex) and in quest text ("Apex Deviljho", "Rusted Kushala Daora"); the
# names are the ones the English game and Kiranico use. 78 is the Fatalis of "Red Dragon's Dawn",
# 117 the "cataclysmic Fatalis" of "A Final Battle Cry".
VARIANTS = {
    43: 'Savage Deviljho', 45: 'Furious Rajang', 78: 'Crimson Fatalis', 82: 'Rusted Kushala Daora',
    97: 'Chaotic Gore Magala', 112: 'Apex Rajang', 113: 'Apex Deviljho', 114: 'Apex Zinogre',
    115: 'Apex Gravios', 117: 'White Fatalis', 119: 'Apex Diablos', 120: 'Apex Tidal Najarala',
    121: 'Apex Tigrex', 122: 'Apex Seregios',
}
def monster(em): return VARIANTS.get(em) or EM[em]

# Non-monster cells of cmn_micon, named for what they show (by eye).
ITEM_CELLS = {84: 'Danger', 86: 'Chest', 88: 'Outbreak', 89: 'Egg', 90: 'Ore', 91: 'Fish', 92: 'Bone',
              93: 'Herb', 94: 'Mushroom', 95: 'Honey', 96: 'Scroll', 123: 'Apex Outbreak'}
NO_ICON, QUESTION_CELL, DANGER, FRENZY, APEX = 98, 0, 84, 88, 123

# Weapon classes in the GU log's order: (item type, slug, name table). Label = Common 36 + type,
# the game's item-type names. Same table as the Collection Tracker's.
TYPES = [
    (7, 'great_sword', 'LswordName'), (13, 'long_sword', 'Lsword2Name'),
    (8, 'sword_and_shield', 'SwordName'), (17, 'dual_blades', 'WswordName'),
    (9, 'hammer', 'HammerName'), (18, 'hunting_horn', 'Hammer2Name'),
    (10, 'lance', 'LanceName'), (15, 'gunlance', 'Lance2Name'),
    (14, 'switch_axe', 'AxeName'), (20, 'charge_blade', 'GaxeName'), (19, 'insect_glaive', 'RodName'),
    (11, 'light_bowgun', 'LightName'), (12, 'heavy_bowgun', 'HeavyName'), (16, 'bow', 'BowName'),
]
# Weapon icon cell, READ 0xc0e328: byte [0xfb8125 + class id], class id = byte [0xf5f2fc + type]
# (the Collection Tracker's notes). Player icons: 14x16 cells, ten per row from y 160 of cmn_icon.
ICON_CELL_TABLE, CLASS_OF = 0xfb8125, 0xf5f2fc


def text(b, o):
    e = o
    while b[e:e + 2] != b'\0\0':
        e += 2
    return b[o:e].decode('utf-16-le')


def one_line(s): return re.sub(r'\s+', ' ', s).strip()


def u32(b, o): return struct.unpack_from('<I', b, o)[0]


def read_quest(path):
    b = open(path, 'rb').read()
    qi = u32(b, 0)
    assert b[4:8] == b'v005', path
    t = [text(b, o) for o in struct.unpack_from('<7I', b, u32(b, u32(b, qi + 0x1c)))]
    fee, reward, _, sub_reward, minutes = struct.unpack_from('<5I', b, qi + 4)
    qid, star = struct.unpack_from('<HB', b, qi + 0x20)
    objs = [struct.unpack_from('<BBHHH', b, qi + 0x2c + 8 * k) for k in range(3)]
    waves, p = [], u32(b, 0x28)
    while p and u32(b, p):
        o = u32(b, p)
        while u32(b, o) != 0xffffffff:
            waves.append(u32(b, o))
            o += 0x28
        p += 4
    return dict(id=qid, star=star, map=b[qi + 0x24], type=b[qi], flags=b[qi + 1], fee=fee,
                reward=reward, sub_reward=sub_reward, minutes=minutes, main=[o for o in objs[:2] if o[0]],
                icons=[i for i in struct.unpack_from('<5H', b, qi + 0x48) if i != NO_ICON],
                waves=list(dict.fromkeys(waves)), name=one_line(t[0]), main_text=one_line(t[1]),
                client=one_line(t[5]), sub_text=one_line(t[6]))


def board(qid):
    """Quest number ranges: 11-24 the Training quests, below 10000 the Caravan (1xx-10xx, plus the
    story quests 12xx-16xx and 26xx), 1xxxx the Gathering Hall, 2xxxx the Arena's Grudge Matches,
    45000-45002 the three Expeditions to the Everwood."""
    if qid < 100: return 'Training'
    if qid < 10000: return 'Caravan'
    if qid < 20000: return 'Gathering Hall'
    if qid < 30000: return 'Arena'
    return 'Expedition'


def level(q):
    """The star, except the three Expeditions, which all say 1*: they are Low, High and G Rank."""
    return q['id'] - 44999 if board(q['id']) == 'Expedition' else q['star']


def quest_order():
    """The first two 0-terminated runs: the offline quests, then the Gathering Hall and Arena."""
    out, va, runs = [], QUEST_ORDER, 0
    while runs < 2:
        v = struct.unpack_from('<H', CODE, va - BASE)[0]
        if v:
            out.append(v)
        elif out:
            runs += 1
        va += 2
    return out


def main():
    order = {q: i for i, q in enumerate(quest_order())}
    raw = {}
    for path in sorted(QUESTS):
        q = read_quest(path)
        raw.setdefault(q['id'], q)
    # Kept: everything on the cart's quest boards. Dropped: 1 (a dev stub with no text), 100 (the
    # prologue on the sandship, played once from the intro and listed on no board -- the board
    # lists at 0xeda372 start 101, 102) and 451xx/452xx (Guild Quest templates with no text: the
    # game builds Guild Quests from relic data).
    keep = [q for q in raw.values() if q['name'] and q['id'] != 100]
    missing = [q['id'] for q in keep if q['id'] not in order]
    keep.sort(key=lambda q: (order.get(q['id'], 1 << 20), q['id']))

    large = {em for q in raw.values() for em in q['waves']}
    cells = monster_cells(raw.values())
    cell_name = {QUESTION_CELL: 'Question Mark'}
    for em, c in sorted(cells.items()):          # lowest number first: Rajang before Apex Rajang
        cell_name.setdefault(c, monster(em))
    cell_name.update(ITEM_CELLS)

    quests, used = [], set()
    for q in keep:
        kills = [(k, t) for k, _, _, t, _ in q['main'] if k in (1, 0x81) and t]
        ems = [t for _, t in kills]
        # Several monsters, or an objective that names none (Research quests, "Hunt 2 Gypceros
        # before time expires or deliver a Paw P.Tkt", "Repel Gore Magala"): the waves are the
        # targets. Delivery and Harvest Tours keep none -- their waves are only intruders.
        if q['type'] == 8 or not ems and q['type'] != 4:
            ems = list(dict.fromkeys(q['waves'] + ems))
        delivered = [ITEMS[t] for k, _, _, t, _ in q['main'] if k == 2]
        # The quest's own board icon; the Expeditions and Research quests have none, so take
        # their first monster's, else the scroll.
        icon = q['icons'][0] if q['icons'] else cells.get(q['waves'][0], QUESTION_CELL) if q['waves'] else 96
        used.add(icon)
        urgent = bool(q['flags'] & 0x10)
        quests.append({
            'Id': q['id'], 'Type': board(q['id']), 'Level': level(q),
            'Name': q['name'], 'Main': q['main_text'], 'Locale': LOCALES.get(q['map'], ''),
            'Monsters': [monster(em) for em in ems],
            'Icon': cell_name.get(icon, 'Question Mark').replace(' ', '_'),
            'Urgent': urgent, 'Key': bool(q['flags'] & 0x20) and not urgent,
            'Capture': q['type'] == 2 or any(k == 0x81 for k, _ in kills),
            'Repel': bool(q['flags'] & 0x04),
            'LgMonster': any(em in large for em in ems),
            'SmMonsters': any(em not in large for em in ems),
            'Delivery': any(d != 'Paw Pass Ticket' for d in delivered),
            # A Paw Pass Ticket ends both the Harvest Tours and the Hunt-a-thons; only the Tours
            # have no monster.
            'Harvest': 'Paw Pass Ticket' in delivered and not ems,
            'Frenzy': FRENZY in q['icons'], 'Apex': APEX in q['icons'],
            'Sub': '' if q['sub_text'] in ('', 'None') else q['sub_text'],
            'Minutes': q['minutes'], 'Fee': q['fee'], 'Reward': q['reward'], 'SubReward': q['sub_reward'],
            'Client': q['client'],
        })
    quests.append(guild_quest(raw))
    if missing:
        print('WARNING: not in the quest order table, sorted last:', missing)
    unknown_maps = sorted({q['Name'] for q in quests if not q['Locale'] and not q.get('Relic')})
    if unknown_maps:
        print('WARNING: no locale for', unknown_maps)
    unnamed = sorted(c for c in used if c not in cell_name)
    if unnamed:
        print('WARNING: quest icon cells with no name:', unnamed)

    # Variants drawn with their base monster's cell (the Apex) get a file under their own name
    # too, so the app can show any monster name it holds -- the Guild Quest swaps produce them.
    files = sorted(cell_name.items())
    files += [(cells[em], monster(em)) for em in sorted(VARIANTS)
              if em in cells and cell_name.get(cells[em]) != monster(em)]
    icons = write_monster_icons(files)
    weapons = {}
    for t, slug, table in TYPES:
        names = [n for n in msg(table) if n and not n.lower().startswith('dummy') and n not in ('(None)', '-')]
        weapons[COMMON[36 + t]] = list(dict.fromkeys(names))
    write_weapon_icons()

    data = {'quests': quests, 'weapons': weapons, 'weaponIcons': {COMMON[36 + t]: s for t, s, _ in TYPES},
            'icons': sorted(icons)}
    with open(os.path.join(DOCS, 'data.js'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('// Generated by scripts/build_data.py from the game itself. Do not edit by hand.\n')
        fh.write('window.MH4U_LOG_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(len(quests), 'quests', dict(collections.Counter(q['Type'] for q in quests)),
          sum(q['Urgent'] for q in quests), 'urgent,', sum(q['Key'] for q in quests), 'key,',
          sum(len(v) for v in weapons.values()), 'weapon names,', len(icons), 'icons')


# GUILD QUEST MONSTERS -- which large monsters the Expedition / Guild Quest generator can use.
# 0xfc0450: twelve pointers to monster blocks; block k serves rank k % 3 (Low, High, G -- the
# unlock quests run Caravan 1-6* / Hall 1-3*, Caravan 7-10* / Hall 4-7*, Hall G1-G3). A block is
# 8-byte records: u16 monster, u16 Gathering Hall quest, u16 Caravan quest (0xffff none; either
# clear unlocks it, 0 = from the start), u16 weight; monster 0 is a header, 255 ends the block.
#   READ 0x6a2328 (a quest's extra monsters): walks blocks rank, rank + 3, rank + 6; skips a
#   record whose unlock quest isn't cleared (0xc21920) or whose locale bit is off (u16 at
#   0xfbf5c8 + 30 * monster); gives no extra monster when the main one is in SOLO, never picks one
#   from SOLO, and never pairs two Najarala (0x17 / 0x5d).
#   READ 0x6b614c (the Expedition's main monster): checks the pick against blocks rank + 9.
# So rank r's pool is blocks r, r+3, r+6, r+9. The Elders, Rajang and Deviljho are only in
# blocks 9-11, which matches their being Guild-Quest-only in the Everwood. Title text, READ
# 0x6b7c14: "Slay" instead of "Hunt" for Kirin, Oroshi Kirin and the SOLO Elders.
#
# Level -> rank, READ 0xabe9e4 (a Guild Quest's per-monster counters): brackets Lv 1-30, 31-85,
# 86-140, and the 1-30 bracket counts exactly block 9's five monsters (Velocidrome, Yian Kut-Ku,
# Basarios, Yian Garuga, Kirin) -- so the brackets are Low, High and G Rank.
# Level swaps, READ 0x69b090: at quest start each monster is looked up in 5-byte rows at
# 0xe081d8 (u8 monster, u8 replacement, u8 min level, u8 max level, u8 1; 0 ends) and replaced
# when the quest's level is in range -- Rajang is Furious Rajang at Lv 76-85, the Apex at 136-140.
GQ_BLOCKS = 0xfc0450
GQ_RANK_MAX = [30, 85, 140]
GQ_SWAPS = 0xe07eb0 + 0x328
GQ_SOLO = {0x18, 0x1c, 0x1d, 0x1f, 0x20, 0x21, 0x2e, 0x4d, 0x4e, 0x4f, 0x52, 0x59, 0x61, 0x67, 0x6e, 0x75}
GQ_NO_PAIR = {0x17, 0x5d}


def guild_pool():
    """monster number -> set of ranks (1 Low, 2 High, 3 G) it can appear at."""
    ranks = collections.defaultdict(set)
    for k in range(12):
        va = struct.unpack_from('<I', CODE, GQ_BLOCKS + 4 * k - BASE)[0]
        while True:
            em = struct.unpack_from('<H', CODE, va - BASE)[0]
            if em == 0xff:
                break
            if em:
                ranks[em].add(k % 3 + 1)
            va += 8
    return ranks


def guild_swaps():
    """[(monster, replacement, min level, max level)] from GQ_SWAPS."""
    out, va = [], GQ_SWAPS
    while CODE[va - BASE]:
        a, b, lo, hi, _ = CODE[va - BASE:va - BASE + 5]
        out.append((a, b, lo, hi))
        va += 5
    return out


def guild_quest(raw):
    """One pickable entry standing for every Guild Quest. The cart's 451xx/452xx files are blank
    templates (no text, no monster, the Everwood as a placeholder map) that the game fills from
    relic data at run time, so there is nothing per-quest to list. Named Menu 278 ("Guild Quest");
    the hunter supplies the level (Lv 1-140), which the game's Guild Card logs as
    'Completed "{quest}" Lv {n}', and the monsters, from Pool (GUILD QUEST MONSTERS above): Solo
    ones come alone, and NoPair lists the two Najarala that never share a quest. Relic marks it
    for the app's Guild Quest fields."""
    assert 45100 in raw and not raw[45100]['name'], 'Guild Quest template 45100 changed'
    pool = guild_pool()
    ems = sorted(pool)
    swaps = guild_swaps()
    print('Guild Quest pool:', len(ems), 'monsters;',
          {r: sum(r in pool[em] for em in ems) for r in (1, 2, 3)}, 'per rank;', len(swaps), 'level swaps')
    named = set(ems) | {b for _, b, _, _ in swaps}
    return {
        'Id': 45100, 'Type': 'Guild Quest', 'Level': 1, 'Name': MENU[278], 'Main': '', 'Locale': '',
        'Monsters': [], 'Icon': 'Scroll', 'Relic': True,
        'Pool': [[monster(em), sorted(pool[em])] for em in ems],
        'RankMax': GQ_RANK_MAX,
        'Swaps': [[monster(a), monster(b), lo, hi] for a, b, lo, hi in swaps],
        'Solo': [monster(em) for em in sorted(named) if em in GQ_SOLO],
        'NoPair': [monster(em) for em in sorted(named) if em in GQ_NO_PAIR],
        'Urgent': False, 'Key': False, 'Capture': False, 'Repel': False, 'LgMonster': False,
        'SmMonsters': False, 'Delivery': False, 'Harvest': False, 'Frenzy': False, 'Apex': False,
        'Sub': '', 'Client': '',
    }


def monster_cells(quests):
    """monster number -> cmn_micon cell, voted from the quests (see ICONS in the header). A monster
    no quest pairs (Ruby Basarios, Purple Gypceros...) takes the cell between its neighbours' when
    they are two apart -- the cells run in monster-number order."""
    votes = collections.defaultdict(collections.Counter)
    for q in quests:
        icons = [i for i in q['icons'] if i not in (DANGER, FRENZY, APEX)]
        kills = [t for k, _, _, t, _ in q['main'] if k in (1, 0x81) and t]
        if len(kills) == 1 and icons:
            votes[kills[0]][icons[0]] += 1
        if q['waves'] and len(q['waves']) == len(icons):
            for em, c in zip(q['waves'], icons):
                votes[em][c] += 1
    cells = {em: v.most_common(1)[0][0] for em, v in votes.items()}
    for em in range(1, len(EM)):
        if em not in cells and em - 1 in cells and em + 1 in cells and cells[em + 1] - cells[em - 1] == 2:
            cells[em] = cells[em - 1] + 1
    return cells


def write_monster_icons(files):
    """One file per (cell, name): MH4U-<name>_Icon.png, the 34 px cell at 2x nearest."""
    from PIL import Image
    from pica_la4 import decode_rgba4
    atlas = decode_rgba4(open(MONSTER_TEX, 'rb').read())
    out = os.path.join(DOCS, 'assets', 'MonsterIcons')
    os.makedirs(out, exist_ok=True)
    written = []
    for c, name in files:
        stem = name.replace(' ', '_')
        r, k = divmod(c if c < 99 else c - 99, 7)
        x, y = (1 if c < 99 else 257) + 36 * k, 1 + 36 * r
        Image.fromarray(atlas[y:y + 34, x:x + 34]).resize((68, 68), Image.NEAREST).save(
            os.path.join(out, 'MH4U-%s_Icon.png' % stem), optimize=True)
        written.append(stem)
    return written


def write_weapon_icons():
    """The game's weapon-class player icons (the grey masks it tints by rarity), 14x16 centred in
    16x16, at 3x."""
    import numpy as np
    from PIL import Image
    from pica_la4 import decode_la4
    atlas = decode_la4(open(ICON_TEX, 'rb').read())
    out = os.path.join(DOCS, 'assets', 'WeaponIcons')
    os.makedirs(out, exist_ok=True)
    for t, slug, _ in TYPES:
        n = CODE[ICON_CELL_TABLE - BASE + CODE[CLASS_OF - BASE + t]]
        x, y = 14 * (n % 10), 160 + 16 * (n // 10)
        sq = np.zeros((16, 16, 4), np.uint8)
        sq[:, 1:15] = atlas[y:y + 16, x:x + 14]
        Image.fromarray(sq).resize((48, 48), Image.NEAREST).save(os.path.join(out, 'icon_%s.png' % slug), optimize=True)


if __name__ == '__main__':
    main()
