# -*- coding: utf-8 -*-
"""
POBLOX — hub de mini-jeux multijoueur (compatible PythonAnywhere gratuit)

Quatre jeux dans le même serveur :
  🎨 Griffonne !      — dessin/devinette type Skribbl
  🔗 Enchaîne !       — trouver un mot qui commence par les lettres imposées
  📡 Longueur d'onde ! — faire deviner un point caché sur un axe, par un indice
  🟢 Glouton !        — arène type agar.io, sans salon, avec des bots

Multijoueur via polling HTTP (pas de WebSockets), état 100 % en RAM.

Déploiement PythonAnywhere :
  1. Uploader ce fichier + words.py + le dossier templates/ dans
     /home/VOTRE_USER/recre/
  2. Web > Add a new web app > Manual configuration > Python 3.10+
  3. Pointer le "Source code" vers /home/VOTRE_USER/recre
     et éditer le fichier WSGI pour importer `app` depuis flask_app.
  4. Reload. C'est tout — aucune base de données nécessaire.
"""

import hashlib
import hmac
import os
import random
import re
import secrets
import sqlite3
import string
import threading
import time
import unicodedata
from array import array
from collections import Counter

from flask import Flask, jsonify, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash

import agar
from ondes import WAVE_PAIRS, axe_genere
from words import WORDS, LANG_NAMES

app = Flask(__name__)

# ------------------------------------------------- paramètres Griffonne
CHOOSE_TIME = 15      # secondes pour choisir un mot
DRAW_TIME = 75        # secondes pour dessiner
REVEAL_TIME = 6       # secondes d'affichage du mot entre les rounds
MAX_ROUNDS = 3        # nombre de tours complets (chacun dessine 1x par tour)
PLAYER_TIMEOUT = 90   # secondes sans polling avant d'être retiré du salon
MAX_PLAYERS = 10
KICK_BAN_S = 600      # durée du blocage d'un pseudo exclu d'un salon

# ------------------------------------------------- paramètres Enchaîne
CHAIN_TURN_TIME = 20      # secondes par tour (réglable par l'hôte)
CHAIN_LIVES = 3           # vies par joueur (réglable par l'hôte)
CHAIN_ESC_EVERY = 8       # tous les N mots, on passe au niveau suivant
CHAIN_MAX_LEVEL = 3       # niveau max = longueur du début imposé (en lettres)
CHAIN_MIN_WORDS = {1: 300, 2: 80, 3: 25}  # mots min. pour qu'un début soit jouable
CHAIN_END_TIME = 12      # secondes d'affichage du podium… en fait état "end"

# ------------------------------------------------- paramètres Longueur d'onde
WAVE_ROUNDS = 2           # tours complets (chacun est maître 1x par tour)
WAVE_AXIS_TIME = 75       # secondes pour écrire thème + extrêmes (mode custom)
WAVE_CLUE_TIME = 60       # secondes pour trouver un indice
WAVE_GUESS_TIME = 50      # secondes pour placer son aiguille
WAVE_REVEAL_TIME = 9      # secondes d'affichage du résultat du tour
WAVE_BAND = 0.04          # largeur d'une bande de score (fraction du cadran)
WAVE_EDGE_BIAS = 0.62     # < 1 : la cible tombe plus souvent vers les bords
WAVE_GEN_SHARE = 0.55     # part des axes assemblés à la volée (vs liste écrite)
# distances (en fraction de cadran) sous lesquelles on marque 5, 3 puis 1 pt
WAVE_SCORES = ((WAVE_BAND * 0.5, 5), (WAVE_BAND * 1.5, 3),
               (WAVE_BAND * 2.5, 1))
WAVE_MODES = ("prefait", "custom")
WAVE_MODE_NAMES = {"prefait": "📚 Axes préfaits",
                   "custom": "✍️ Tout personnalisé"}

# ------------------------------------------------------------------ état RAM
ROOMS = {}
LOCK = threading.Lock()

# Glouton : une seule arène pour tout le monde, sans salon ni code. Son
# verrou est distinct pour ne pas bloquer les autres jeux (elle est
# sollicitée ~9 fois par seconde et par joueur).
ARENE = agar.nouveau_monde()
ARENE_LOCK = threading.Lock()

GAMES = ("draw", "chain", "wave")


def _now():
    return time.time()


def _norm(s):
    """minuscules, sans accents, espaces compactés — pour comparer les mots"""
    s = unicodedata.normalize("NFD", s.lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\-']+", " ", s)


def _letters_only(s):
    """minuscules, sans accents, uniquement a-z — pour la chaîne de mots.
    œ/æ/ß ne se décomposent pas en NFD : on les mappe à la main, sinon
    « œuf » devenait « uf »."""
    s = s.lower().replace("ß", "ss").replace("œ", "oe").replace("æ", "ae")
    s = unicodedata.normalize("NFD", s.strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", s)


# ------------------------------------------------- dictionnaires Enchaîne
# Vrais lexiques (170k à 640k mots/langue, sans noms propres) chargés depuis
# dicts/<lang>.txt, complétés par les mots de words.py pour ne jamais rejeter
# un mot de jeu valide.
DICT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dicts")
CHAIN_DICT = {}       # lang -> WordSet de mots normalisés (a-z, sans accents)
CHAIN_START = {}      # lang -> {longueur -> débuts jouables (assez de mots)}


class WordSet:
    """Lexique compact : un seul blob trié + offsets, recherche dichotomique.
    ~6x moins de RAM qu'un set de str (compte avec 1,6 M de mots au total)."""
    __slots__ = ("_blob", "_offs")

    def __init__(self, words):
        words = sorted(words)
        self._blob = "\n".join(words)
        self._offs = array("I")
        pos = 0
        for w in words:
            self._offs.append(pos)
            pos += len(w) + 1

    def _at(self, i):
        start = self._offs[i]
        end = (self._offs[i + 1] - 1 if i + 1 < len(self._offs)
               else len(self._blob))
        return self._blob[start:end]

    def __contains__(self, w):
        lo, hi = 0, len(self._offs) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            x = self._at(mid)
            if x == w:
                return True
            if x < w:
                lo = mid + 1
            else:
                hi = mid - 1
        return False

    def _lower_bound(self, target):
        lo, hi = 0, len(self._offs)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._at(mid) < target:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def count_prefix(self, prefix):
        """Nombre de mots commençant par prefix (mots a-z uniquement)."""
        return (self._lower_bound(prefix + "{")
                - self._lower_bound(prefix))

    def prefix_list(self, prefix, limit=30):
        """Jusqu'à `limit` mots commençant par prefix (blob trié)."""
        i = self._lower_bound(prefix)
        out = []
        while i < len(self._offs) and len(out) < limit:
            w = self._at(i)
            if not w.startswith(prefix):
                break
            out.append(w)
            i += 1
        return out

    def __len__(self):
        return len(self._offs)


def _load_dicts():
    for lang in WORDS:
        path = os.path.join(DICT_DIR, lang + ".txt")
        s = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if not parts:
                        continue
                    raw = parts[0].strip().lower()
                    if " " in raw or any(c.isdigit() for c in raw):
                        continue
                    w = _letters_only(raw)
                    if len(w) >= 2:
                        s.add(w)
        for diff in WORDS[lang].values():   # on garde toujours les mots du jeu
            for w in diff:
                s.add(_letters_only(w))
        CHAIN_DICT[lang] = WordSet(s)
        # débuts de 1 à CHAIN_MAX_LEVEL lettres ayant assez de mots possibles
        starts = {}
        for n in range(1, CHAIN_MAX_LEVEL + 1):
            counts = Counter(w[:n] for w in s if len(w) > n)
            good = [p for p, c in counts.items() if c >= CHAIN_MIN_WORDS[n]]
            starts[n] = good or starts.get(n - 1) \
                or list("abcdefghijklmnoprstuvwxyz")
        CHAIN_START[lang] = starts


_load_dicts()


def _chain_new_prefix(room):
    """Tire au sort un nouveau début imposé, de la longueur du niveau.
    Garantie : il reste au moins 3 mots jouables (dans le dictionnaire,
    plus longs que le préfixe, pas encore utilisés dans la partie)."""
    lang = room.get("lang", "fr")
    starts = CHAIN_START.get(lang, CHAIN_START["fr"])
    pool = starts.get(room.get("level", 1)) or starts[1]
    ws = CHAIN_DICT.get(lang)
    used = room.get("words_used", set()) or set()
    prefix = random.choice(pool)
    for _ in range(40):
        cand = random.choice(pool)
        if cand == room.get("prefix") and len(pool) > 1:
            continue
        playable = ws.count_prefix(cand) if ws else 0
        playable -= (1 if ws and cand in ws else 0)       # mot == préfixe
        playable -= sum(1 for w in used if w.startswith(cand))
        if playable >= 3:
            return cand
        prefix = cand
    return prefix


BUCKETS = WORDS  # words.py : 4 niveaux "1".."4" par langue
DIFF_MULT = {"1": 1.0, "2": 1.5, "3": 2.0, "4": 3.0}
DIFF_LABEL = {"1": "★", "2": "★★", "3": "★★★", "4": "★★★★"}
DIFF_NAME = {"1": "facile", "2": "simple", "3": "moyen", "4": "impossible"}

# composition des 3 propositions selon le mode de partie
MODES = {
    "debutant":      ["1", "1", "2"],
    "intermediaire": ["2", "2", "3"],
    "aguerri":       ["3", "4", "4"],
}
MODE_NAMES = {"debutant": "🌱 Débutant", "intermediaire": "🔥 Intermédiaire",
              "aguerri": "💀 Aguerri"}


def _lev(a, b, cap=4):
    """Distance de Levenshtein (coupée court si trop différent)."""
    if abs(len(a) - len(b)) > cap:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _typo_ok(a, b):
    """Tolérance aux fautes de frappe, proportionnelle à la longueur."""
    n = max(len(a), len(b))
    tol = 1 if n <= 5 else 2 if n <= 9 else 3
    return _lev(a, b, cap=tol + 1) <= tol


def _is_close(guess, word):
    """Vrai si la proposition est 'proche' du mot.
    Ex : micro/microphone, pome/pomme, chatau/château de sable, bato/bateau."""
    g, w = _norm(guess), _norm(word)
    if g == w or len(g) < 3:
        return False
    # morceau du mot (>= 4 lettres) dans un sens ou dans l'autre
    if min(len(g), len(w)) >= 4 and (g in w or w in g):
        return True
    # début commun d'au moins 4 lettres et longueurs comparables
    common = 0
    for ca, cb in zip(g, w):
        if ca != cb:
            break
        common += 1
    if common >= 4 or (common >= 3 and common >= len(g) - 1):
        return True
    # faute(s) de frappe sur l'ensemble
    if _typo_ok(g, w):
        return True
    # mots composés : on compare chaque morceau (>=4 lettres)
    gt = [t for t in g.split() if len(t) >= 4]
    wt = [t for t in w.split() if len(t) >= 4]
    for a in gt or [g]:
        for b in wt:
            if a == b or _typo_ok(a, b):
                return True
    return False


def _new_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in ROOMS:
            return code


def _new_player(name):
    return {"name": name[:16], "score": 0, "round_gain": 0,
            "guessed": False, "lives": CHAIN_LIVES, "alive": True,
            "words": 0, "last_seen": _now(),
            "user": None, "avatar": "", "admin": False, "s_guessed": 0}


def _new_room(host_pid, host_name, game="draw"):
    room = {
        "game": game,
        "players": {host_pid: _new_player(host_name)},
        "order": [host_pid],
        "host": host_pid,
        "state": "lobby",
        "chat": [],                # {seq, name, text, kind}
        "chat_seq": 0,
        "feed": [],                # journal système (Enchaîne) : même structure
        "feed_seq": 0,
        "kicked_pids": {},         # pid exclu -> horodatage (signal client)
        "kicked_names": {},        # _norm(nom) exclu -> horodatage (anti re-join)
        "created": _now(),
    }
    if game == "draw":
        room.update({
            # lobby | choosing | drawing | reveal | end
            "round": 0,
            "max_rounds": MAX_ROUNDS,
            "lang": "fr",
            "mode": "debutant",
            "draw_time": DRAW_TIME,
            "drawer": None,
            "drawer_queue": [],
            "word": None,
            "word_diff": "2",
            "word_mult": 1.0,
            "choices": [],
            "choice_diff": {},
            "hint": "",
            "timer_end": 0,
            "strokes": [],         # liste de traits {seq, color, size, pts, tool}
            "stroke_seq": 0,
            "clear_seq": 0,        # incrémenté quand le canvas est effacé
        })
    elif game == "wave":
        room.update({
            # lobby | axis | clue | guess | reveal | end
            "mode": "prefait",
            "round": 0,
            "max_rounds": WAVE_ROUNDS,
            "master": None,        # pid du maître du tour (celui qui indice)
            "master_queue": [],
            "theme": "", "left": "", "right": "",
            "clue": "",
            "target": 0.5,         # position cachée sur l'axe, entre 0 et 1
            "guesses": {},         # pid -> position proposée (0..1)
            "gains": {},           # pid -> points du tour (affichage reveal)
            "pairs_used": set(),   # index des axes préfaits déjà tirés
            "timer_end": 0,
        })
    else:  # chain — lobby | playing | end
        room.update({
            "lang": "fr",
            "turn_time": CHAIN_TURN_TIME,
            "lives_max": CHAIN_LIVES,
            "prefix": "",          # lettres imposées au début du prochain mot
            "level": 1,            # longueur du début imposé (en lettres)
            "words_count": 0,
            "words_used": set(),   # formes normalisées (a-z) déjà jouées
            "chain": [],           # {seq, name, word, lvl}
            "chain_seq": 0,
            "turn_pid": None,
            "turn_end": 0,
            "winner": "",
            "elim": [],            # pids dans l'ordre d'élimination

        })
    return room


def _save_stats(room):
    """Fin de partie : crédite les stats des joueurs connectés (compte).
    Ne doit jamais casser une partie — erreurs avalées."""
    try:
        rows = []   # (préfixe colonnes, username, victoire, compteur)
        players = room["players"]
        if room["game"] == "wave":
            best = max((p["score"] for p in players.values()), default=0)
            for p in players.values():
                if p.get("user"):
                    rows.append(("wv", p["user"],
                                 1 if best > 0 and p["score"] == best else 0,
                                 p["score"]))
        elif room["game"] == "draw":
            best = max((p["score"] for p in players.values()), default=0)
            for p in players.values():
                if p.get("user"):
                    rows.append(("dg", p["user"],
                                 1 if best > 0 and p["score"] == best else 0,
                                 p.get("s_guessed", 0)))
        else:
            elim = set(room.get("elim", []))
            for k, p in players.items():
                # les spectateurs arrivés en cours de partie ne comptent pas
                played = p["alive"] or p.get("words", 0) or k in elim
                if p.get("user") and played:
                    rows.append(("ch", p["user"],
                                 1 if p["alive"] else 0,
                                 p.get("words", 0)))
        if not rows:
            return
        con = _db()
        try:
            with con:
                for g, user, win, words in rows:
                    wcol = {"dg": "dg_guessed", "ch": "ch_words",
                            "wv": "wv_points"}[g]
                    con.execute(
                        f"UPDATE users SET {g}_games = {g}_games + 1, "
                        f"{g}_wins = {g}_wins + ?, {wcol} = {wcol} + ? "
                        "WHERE username = ?", (win, words, user))
        finally:
            con.close()
    except Exception:
        pass


def _chat(room, text, kind="system", name=""):
    """Journal système. Enchaîne n'a pas de chat joueur : ses messages
    vont dans `feed` ; Griffonne utilise `chat`."""
    if room["game"] == "chain":
        room["feed_seq"] += 1
        room["feed"].append({"seq": room["feed_seq"], "name": name,
                             "text": text, "kind": kind})
        room["feed"] = room["feed"][-80:]
        return
    room["chat_seq"] += 1
    room["chat"].append({"seq": room["chat_seq"], "name": name,
                         "text": text, "kind": kind})
    room["chat"] = room["chat"][-80:]


# ══════════════════════════════════════════════════ GRIFFONNE (dessin)

def _mask(word, reveal=0):
    """Transforme 'feu de camp' en '___ __ ____', avec `reveal` lettres dévoilées."""
    letters = [i for i, c in enumerate(word) if c.isalnum()]
    shown = set(random.Random(word).sample(letters, min(reveal, len(letters))))
    return "".join(c if (not c.isalnum() or i in shown) else "_"
                   for i, c in enumerate(word))


def _start_turn(room):
    """Passe au dessinateur suivant (ou termine la partie)."""
    room["strokes"] = []
    room["clear_seq"] += 1
    for p in room["players"].values():
        p["guessed"] = False
        p["round_gain"] = 0

    # file des dessinateurs pour le tour en cours
    while not room["drawer_queue"]:
        room["round"] += 1
        if room["round"] > room["max_rounds"]:
            room["state"] = "end"
            _chat(room, "🏁 Partie terminée !")
            _save_stats(room)
            return
        room["drawer_queue"] = [p for p in room["order"]
                                if p in room["players"]]
        _chat(room, f"— Tour {room['round']} / {room['max_rounds']} —")

    drawer = room["drawer_queue"].pop(0)
    if drawer not in room["players"]:
        return _start_turn(room)

    room["drawer"] = drawer
    # composition des propositions selon le mode de partie
    room["choices"] = []
    room["choice_diff"] = {}
    for diff in MODES.get(room.get("mode", "debutant"), MODES["debutant"]):
        pool = BUCKETS[room["lang"]][diff]
        w = random.choice(pool)
        tries = 0
        while w in room["choice_diff"] and tries < 50:
            w = random.choice(pool)
            tries += 1
        room["choices"].append(w)
        room["choice_diff"][w] = diff
    room["word"] = None
    room["hint"] = ""
    room["state"] = "choosing"
    room["timer_end"] = _now() + CHOOSE_TIME
    _chat(room, f"✏️ {room['players'][drawer]['name']} choisit un mot…")


def _begin_drawing(room, word):
    room["word"] = word
    diff = room.get("choice_diff", {}).get(word, "2")
    room["word_diff"] = diff
    room["word_mult"] = DIFF_MULT[diff]
    room["hint"] = _mask(word, 0)
    room["state"] = "drawing"
    room["timer_end"] = _now() + room["draw_time"]
    _chat(room, f"🎨 Ça dessine ! Mot {DIFF_LABEL[diff]} "
                f"({DIFF_NAME[diff]}, points ×{DIFF_MULT[diff]:g}). "
                f"Devinez dans le chat.")


def _end_turn(room, found_all=False):
    drawer = room.get("drawer")
    if drawer in room["players"]:
        # le dessinateur gagne selon la PART de joueurs qui ont trouvé :
        # tout le monde trouve = 120 pts (x multiplicateur), la moitié = 60…
        # équitable quel que soit le nombre de joueurs dans le salon.
        others = max(1, len(room["players"]) - 1)
        found = sum(1 for k, p in room["players"].items()
                    if k != drawer and p["guessed"])
        gain = int(120 * found / others * room.get("word_mult", 1.0))
        room["players"][drawer]["score"] += gain
        room["players"][drawer]["round_gain"] = gain
    msg = "🎉 Tout le monde a trouvé !" if found_all else "⏰ Temps écoulé !"
    _chat(room, f"{msg} Le mot était « {room['word']} ».")
    room["state"] = "reveal"
    room["timer_end"] = _now() + REVEAL_TIME


def _tick_draw(room):
    now = _now()
    if room["state"] in ("choosing", "drawing", "reveal") \
            and len(room["players"]) < 2:
        room["state"] = "lobby"
        room["round"] = 0
        room["drawer_queue"] = []
        room["drawer"] = None
        _chat(room, "Plus assez de joueurs — retour au salon.")
        return

    if room["state"] == "choosing" and now >= room["timer_end"]:
        _begin_drawing(room, random.choice(room["choices"]))
    elif room["state"] == "drawing":
        # indice : 1 lettre à mi-temps, 2 lettres au dernier quart
        left = room["timer_end"] - now
        if left <= room["draw_time"] * 0.25:
            room["hint"] = _mask(room["word"], 2)
        elif left <= room["draw_time"] * 0.5:
            room["hint"] = _mask(room["word"], 1)
        if now >= room["timer_end"]:
            _end_turn(room)
    elif room["state"] == "reveal" and now >= room["timer_end"]:
        _start_turn(room)


# ══════════════════════════════════════════════════ ENCHAÎNE (chaîne de mots)

def _chain_alive(room):
    return [pid for pid in room["order"]
            if pid in room["players"] and room["players"][pid]["alive"]]


def _chain_advance(room, from_pid=None):
    """Donne la main au joueur vivant suivant (après from_pid ou le joueur
    courant). Termine la partie s'il ne reste qu'un survivant."""
    alive = _chain_alive(room)
    if len(alive) <= 1:
        room["state"] = "end"
        room["winner"] = (room["players"][alive[0]]["name"] if alive else "")
        if room["winner"]:
            _chat(room, f"🏆 {room['winner']} remporte la partie !")
        else:
            _chat(room, "🏁 Partie terminée !")
        _save_stats(room)
        return
    cur = from_pid or room["turn_pid"]
    order = room["order"]
    i = order.index(cur) if cur in order else -1
    for step in range(1, len(order) + 1):
        nxt = order[(i + step) % len(order)]
        if nxt in alive:
            room["turn_pid"] = nxt
            break
    room["turn_end"] = _now() + room["turn_time"]


def _chain_start(room):
    room["state"] = "playing"
    room["level"] = 1
    room["words_count"] = 0
    room["words_used"] = set()
    room["chain"] = []
    room["winner"] = ""
    room["elim"] = []
    room["prefix"] = _chain_new_prefix(room)
    for p in room["players"].values():
        p["words"] = 0
        p["lives"] = room["lives_max"]
        p["alive"] = True
    room["turn_pid"] = random.choice(room["order"])
    room["turn_end"] = _now() + room["turn_time"]
    _chat(room, f"🔗 C'est parti ! Trouve un mot qui commence par "
                f"« {room['prefix'].upper()} » — il doit exister dans le "
                f"dictionnaire ! Niveau 1 : début imposé d'une lettre.")


def _tick_chain(room):
    now = _now()
    if room["state"] != "playing":
        return
    if len(room["players"]) < 2:
        room["state"] = "lobby"
        room["turn_pid"] = None
        _chat(room, "Plus assez de joueurs — retour au salon.")
        return
    # le joueur dont c'est le tour a peut-être quitté
    if room["turn_pid"] not in room["players"]:
        room["prefix"] = _chain_new_prefix(room)
        _chain_advance(room, from_pid=room["order"][0]
                       if room["order"] else None)
        return
    if now >= room["turn_end"]:
        p = room["players"][room["turn_pid"]]
        p["lives"] -= 1
        if p["lives"] <= 0:
            p["alive"] = False
            room.setdefault("elim", []).append(room["turn_pid"])
            _chat(room, f"💀 {p['name']} n'a rien trouvé… éliminé !")
        else:
            _chat(room, f"⏰ {p['name']} sèche ! (-1 ❤️ — il lui en reste "
                        f"{p['lives']})")
        # nouveau tirage pour relancer la machine
        room["prefix"] = _chain_new_prefix(room)
        _chain_advance(room)



# ══════════════════════════════════════════ LONGUEUR D'ONDE (cadran caché)
# Un joueur (le « maître ») voit une cible cachée sur un axe qui va d'un
# extrême à l'autre (ex. Un animal : Effrayant ↔ Adorable). Il donne un
# indice qui se situe pile à cet endroit ; les autres placent leur aiguille.
# Au même endroit = 5 pts, une bande à côté = 3, deux bandes = 1.

def _wave_new_target():
    """Position cachée. Loi en U (bêta de paramètre < 1) : les bords
    sortent plus souvent que le centre — « complètement à gauche » est un
    indice bien plus drôle à faire deviner qu'un tiède milieu. Environ un
    tour sur trois tombe dans les 10 % extrêmes ; tout reste atteignable."""
    x = random.betavariate(WAVE_EDGE_BIAS, WAVE_EDGE_BIAS)
    return round(min(0.98, max(0.02, x)), 4)


def _wave_pick_pair(room):
    """Un axe pas encore sorti dans la partie : tantôt assemblé à la volée
    (thème × échelle compatible, des milliers de combinaisons), tantôt tiré
    de la liste écrite à la main — celle-ci est plus typée, les combinaisons
    évitent de tourner en rond."""
    used = room.setdefault("pairs_used", set())
    axe = None
    for _ in range(40):
        axe = (axe_genere(random) if random.random() < WAVE_GEN_SHARE
               else random.choice(WAVE_PAIRS))
        if axe not in used:
            break
    else:
        used.clear()                 # tout est sorti : on repart à zéro
    used.add(axe)
    return axe


def _wave_score(target, pos):
    d = abs(pos - target) - 1e-9      # marge : les bornes exactes comptent
    for limit, pts in WAVE_SCORES:
        if d <= limit:
            return pts
    return 0


def _wave_begin_clue(room):
    room["state"] = "clue"
    room["timer_end"] = _now() + WAVE_CLUE_TIME
    name = room["players"].get(room["master"], {}).get("name", "?")
    _chat(room, f"🎯 {name} cherche un indice entre « {room['left']} » "
                f"et « {room['right']} »…")


def _wave_begin_guess(room):
    room["state"] = "guess"
    room["timer_end"] = _now() + WAVE_GUESS_TIME
    _chat(room, f"💡 Indice : « {room['clue']} » — placez votre aiguille !")


def _wave_start_turn(room):
    """Passe au maître suivant (ou termine la partie)."""
    room["guesses"] = {}
    room["gains"] = {}
    room["clue"] = ""
    for p in room["players"].values():
        p["round_gain"] = 0

    while not room["master_queue"]:
        room["round"] += 1
        if room["round"] > room["max_rounds"]:
            room["state"] = "end"
            _chat(room, "🏁 Partie terminée !")
            _save_stats(room)
            return
        room["master_queue"] = [p for p in room["order"]
                                if p in room["players"]]
        _chat(room, f"— Tour {room['round']} / {room['max_rounds']} —")

    master = room["master_queue"].pop(0)
    if master not in room["players"]:
        return _wave_start_turn(room)

    room["master"] = master
    room["target"] = _wave_new_target()
    name = room["players"][master]["name"]
    if room.get("mode") == "custom":
        room["theme"] = room["left"] = room["right"] = ""
        room["state"] = "axis"
        room["timer_end"] = _now() + WAVE_AXIS_TIME
        _chat(room, f"🎛️ {name} choisit un thème et ses deux extrêmes…")
    else:
        room["theme"], room["left"], room["right"] = _wave_pick_pair(room)
        _wave_begin_clue(room)


def _wave_reveal(room):
    """Compte les points du tour et dévoile la cible."""
    target = room["target"]
    master = room.get("master")
    gains = {pid: _wave_score(target, pos)
             for pid, pos in room["guesses"].items()
             if pid in room["players"]}
    for pid, g in gains.items():
        room["players"][pid]["score"] += g
        room["players"][pid]["round_gain"] = g
    if master in room["players"]:
        # le maître gagne la moyenne de ce que son indice a rapporté :
        # un bon indice profite à tout le monde, à lui le premier.
        bonus = round(sum(gains.values()) / len(gains)) if gains else 0
        room["players"][master]["score"] += bonus
        room["players"][master]["round_gain"] = bonus
        gains[master] = bonus
    room["gains"] = gains
    room["state"] = "reveal"
    room["timer_end"] = _now() + WAVE_REVEAL_TIME
    pile = [room["players"][k]["name"] for k, g in gains.items()
            if g == 5 and k != master]
    if pile:
        _chat(room, "🎯 En plein dans le mille : " + ", ".join(pile) + " !")


def _tick_wave(room):
    now = _now()
    playing = ("axis", "clue", "guess", "reveal")
    if room["state"] in playing and len(room["players"]) < 2:
        room["state"] = "lobby"
        room["round"] = 0
        room["master_queue"] = []
        room["master"] = None
        _chat(room, "Plus assez de joueurs — retour au salon.")
        return

    if room["state"] == "axis" and now >= room["timer_end"]:
        room["theme"], room["left"], room["right"] = _wave_pick_pair(room)
        _chat(room, "⏰ Trop tard — l'axe est tiré au sort !")
        _wave_begin_clue(room)
    elif room["state"] == "clue" and now >= room["timer_end"]:
        _chat(room, "⏰ Aucun indice donné — tour annulé.")
        _wave_start_turn(room)
    elif room["state"] == "guess":
        others = [k for k in room["players"] if k != room["master"]]
        if (others and all(k in room["guesses"] for k in others))                 or now >= room["timer_end"]:
            _wave_reveal(room)
    elif room["state"] == "reveal" and now >= room["timer_end"]:
        _wave_start_turn(room)


# ══════════════════════════════════════════════════════════ commun

def _remove_player(room, pid, text):
    """Retire un joueur du salon (timeout ou exclusion) : nettoie l'ordre,
    réassigne l'hôte et relance le tour si besoin."""
    del room["players"][pid]
    room["order"] = [x for x in room["order"] if x != pid]
    _chat(room, text)
    if pid == room["host"] and room["order"]:
        room["host"] = room["order"][0]
    if room["game"] == "draw":
        room["drawer_queue"] = [x for x in room["drawer_queue"]
                                if x != pid]
        if pid == room["drawer"] and room["state"] in ("choosing",
                                                       "drawing"):
            _chat(room, "Le dessinateur est parti, on passe au suivant.")
            _start_turn(room)
    elif room["game"] == "wave":
        room["master_queue"] = [x for x in room["master_queue"] if x != pid]
        room["guesses"].pop(pid, None)
        if pid == room["master"] and room["state"] in ("axis", "clue",
                                                       "guess"):
            _chat(room, "Le maître du tour est parti, on passe au suivant.")
            _wave_start_turn(room)
    elif room["state"] == "playing":
        if pid == room["turn_pid"]:
            room["prefix"] = _chain_new_prefix(room)
            _chain_advance(room, from_pid=room["order"][0]
                           if room["order"] else None)
        elif len(_chain_alive(room)) <= 1:
            _chain_advance(room)   # déclenche la fin de partie


def _tick(room):
    """Fait avancer la machine à états (appelé à chaque requête)."""
    now = _now()
    # purge des joueurs inactifs (commun aux deux jeux)
    gone = [pid for pid, p in room["players"].items()
            if now - p["last_seen"] > PLAYER_TIMEOUT]
    for pid in gone:
        name = room["players"][pid]["name"]
        _remove_player(room, pid, f"👋 {name} a quitté la partie.")

    if room["game"] == "draw":
        _tick_draw(room)
    elif room["game"] == "wave":
        _tick_wave(room)
    else:
        _tick_chain(room)


def _room_or_404(code):
    room = ROOMS.get((code or "").upper())
    if not room:
        return None, (jsonify(error="Salon introuvable."), 404)
    return room, None


# ══════════════════════════════════════════════════ COMPTES (SQLite)
# Comptes persistants : mots de passe hachés (werkzeug), sessions par cookie
# httponly dont le jeton n'est stocké qu'en version hachée (SHA-256) en base.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
THEMES = {"clair", "sombre", "ocean", "foret", "sorbet"}
AVATARS = ["🦊", "🐼", "🐸", "🐙", "🦖", "🦉", "🐝", "🐢", "🦩", "🐬",
           "🦔", "🐯", "🦄", "👻", "🤖", "👽", "🧙", "🥷", "🍄", "🌵",
           "⚡", "🌙", "🍕", "🎩"]
STAT_COLS = ("dg_games", "dg_wins", "dg_guessed",   # Griffonne
             "ch_games", "ch_wins", "ch_words",     # Enchaîne
             "wv_games", "wv_wins", "wv_points",    # Longueur d'onde
             "ag_games", "ag_best", "ag_eaten")     # Glouton
SESSION_COOKIE = "poblox_session"
SESSION_DAYS = 90
USER_RE = re.compile(r"^[a-zA-Z0-9à-öø-ÿÀ-ÖØ-Þ_-]{3,16}$")
_LOGIN_TRIES = {}          # ip -> liste d'horodatages (anti force brute)

# Mode admin : le code n'existe nulle part en clair, seulement son SHA-256.
ADMIN_HASH = "449f674a47d5e6bf901ab1af5aa741db102ba4f304db64981bf0794b996b1448"
ADMIN_COOKIE = "poblox_admin"
_ADMIN_TOKS = set()        # sha256 des jetons admin anonymes (RAM, perdu au restart)
_ADMIN_TRIES = {}          # ip -> liste d'horodatages (anti force brute)


def _db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY, display TEXT NOT NULL, pw TEXT NOT NULL,
        theme TEXT NOT NULL DEFAULT 'clair', created REAL NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY, username TEXT NOT NULL,
        created REAL NOT NULL)""")
    return con


def _migrate_db():
    """Ajoute les colonnes apparues après la création de la table users."""
    con = _db()
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
        with con:
            if "avatar" not in cols:
                con.execute("ALTER TABLE users ADD COLUMN "
                            "avatar TEXT NOT NULL DEFAULT ''")
            if "admin" not in cols:
                con.execute("ALTER TABLE users ADD COLUMN "
                            "admin INTEGER NOT NULL DEFAULT 0")
            for c in STAT_COLS:
                if c not in cols:
                    con.execute(f"ALTER TABLE users ADD COLUMN "
                                f"{c} INTEGER NOT NULL DEFAULT 0")
    finally:
        con.close()


def _tok_hash(tok):
    return hashlib.sha256(tok.encode()).hexdigest()


def _current_user(con):
    """(username, display, theme, avatar, admin) du visiteur, ou None."""
    tok = request.cookies.get(SESSION_COOKIE)
    if not tok:
        return None
    return con.execute(
        "SELECT s.username, u.display, u.theme, u.avatar, u.admin "
        "FROM sessions s "
        "JOIN users u ON u.username = s.username "
        "WHERE s.token = ? AND s.created > ?",
        (_tok_hash(tok), _now() - SESSION_DAYS * 86400)).fetchone()


def _admin_cookie_ok():
    """Vrai si la requête porte un jeton admin valide (session sans compte)."""
    tok = request.cookies.get(ADMIN_COOKIE)
    return bool(tok) and _tok_hash(tok) in _ADMIN_TOKS


def _visitor_profile():
    """(username, avatar, admin) du visiteur, sinon (None, '', admin)."""
    con = _db()
    try:
        row = _current_user(con)
        admin = bool(row and row[4]) or _admin_cookie_ok()
        return (row[0], row[3] or "", admin) if row else (None, "", admin)
    finally:
        con.close()


_migrate_db()


def _session_resp(con, username, display, theme):
    """Ouvre une session et renvoie la réponse avec le cookie posé."""
    tok = secrets.token_urlsafe(32)
    with con:
        con.execute("INSERT INTO sessions VALUES(?,?,?)",
                    (_tok_hash(tok), username, _now()))
        con.execute("DELETE FROM sessions WHERE created < ?",
                    (_now() - SESSION_DAYS * 86400,))
    resp = jsonify(ok=True, name=display, theme=theme)
    secure = (request.is_secure
              or request.headers.get("X-Forwarded-Proto") == "https")
    resp.set_cookie(SESSION_COOKIE, tok, max_age=SESSION_DAYS * 86400,
                    httponly=True, samesite="Lax", secure=secure)
    return resp


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True)
    name = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    if not USER_RE.match(name):
        return jsonify(error="Pseudo : 3 à 16 caractères "
                             "(lettres, chiffres, - et _)."), 400
    if len(pw) < 6:
        return jsonify(error="Mot de passe : 6 caractères minimum."), 400
    con = _db()
    try:
        exists = con.execute("SELECT 1 FROM users WHERE username = ?",
                             (name.lower(),)).fetchone()
        if exists:
            return jsonify(error="Ce pseudo est déjà pris."), 400
        with con:
            con.execute("INSERT INTO users(username, display, pw, theme, "
                        "created) VALUES(?,?,?,?,?)",
                        (name.lower(), name, generate_password_hash(pw),
                         "clair", _now()))
        return _session_resp(con, name.lower(), name, "clair")
    finally:
        con.close()


@app.route("/api/login", methods=["POST"])
def api_login():
    ip = request.remote_addr or "?"
    now = _now()
    tries = [t for t in _LOGIN_TRIES.get(ip, []) if now - t < 300]
    if len(tries) >= 8:
        return jsonify(error="Trop d'essais — réessaie dans 5 minutes."), 429
    _LOGIN_TRIES[ip] = tries + [now]
    data = request.get_json(force=True)
    name = (data.get("username") or "").strip().lower()
    pw = data.get("password") or ""
    con = _db()
    try:
        row = con.execute(
            "SELECT username, display, theme, pw FROM users "
            "WHERE username = ?", (name,)).fetchone()
        if not row or not check_password_hash(row[3], pw):
            return jsonify(error="Pseudo ou mot de passe incorrect."), 401
        return _session_resp(con, row[0], row[1], row[2])
    finally:
        con.close()


@app.route("/api/logout", methods=["POST"])
def api_logout():
    tok = request.cookies.get(SESSION_COOKIE)
    if tok:
        con = _db()
        try:
            with con:
                con.execute("DELETE FROM sessions WHERE token = ?",
                            (_tok_hash(tok),))
        finally:
            con.close()
    resp = jsonify(ok=True)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.route("/api/me")
def api_me():
    con = _db()
    try:
        row = _current_user(con)
        if not row:
            return jsonify(name=None, admin=_admin_cookie_ok())
        st = con.execute(
            "SELECT " + ", ".join(STAT_COLS) + " FROM users "
            "WHERE username = ?", (row[0],)).fetchone()
        return jsonify(name=row[1], theme=row[2], avatar=row[3] or "",
                       admin=bool(row[4]) or _admin_cookie_ok(),
                       stats=dict(zip(STAT_COLS, st)))
    finally:
        con.close()


@app.route("/api/avatar", methods=["POST"])
def api_avatar():
    data = request.get_json(force=True)
    avatar = data.get("avatar")
    if avatar not in AVATARS:
        return jsonify(error="Avatar inconnu."), 400
    con = _db()
    try:
        row = _current_user(con)
        if not row:
            return jsonify(ok=False)
        with con:
            con.execute("UPDATE users SET avatar = ? WHERE username = ?",
                        (avatar, row[0]))
        return jsonify(ok=True)
    finally:
        con.close()


@app.route("/api/theme", methods=["POST"])
def api_theme():
    data = request.get_json(force=True)
    theme = data.get("theme")
    if theme not in THEMES:
        return jsonify(error="Thème inconnu."), 400
    con = _db()
    try:
        row = _current_user(con)
        if not row:
            return jsonify(ok=False)   # pas connecté : le client garde le sien
        with con:
            con.execute("UPDATE users SET theme = ? WHERE username = ?",
                        (theme, row[0]))
        return jsonify(ok=True)
    finally:
        con.close()


@app.route("/api/admin_activate", methods=["POST"])
def api_admin_activate():
    ip = request.remote_addr or "?"
    now = _now()
    tries = [t for t in _ADMIN_TRIES.get(ip, []) if now - t < 300]
    if len(tries) >= 8:
        return jsonify(error="Trop d'essais — réessaie dans 5 minutes."), 429
    _ADMIN_TRIES[ip] = tries + [now]
    data = request.get_json(force=True)
    code = (data.get("code") or "").strip()
    if not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(),
                               ADMIN_HASH):
        return jsonify(error="Code incorrect."), 403
    con = _db()
    try:
        row = _current_user(con)
        if row:
            with con:
                con.execute("UPDATE users SET admin = 1 WHERE username = ?",
                            (row[0],))
    finally:
        con.close()
    # jeton httponly pour les sessions sans compte (RAM, perdu au restart)
    tok = secrets.token_urlsafe(32)
    _ADMIN_TOKS.add(_tok_hash(tok))
    resp = jsonify(ok=True, admin=True)
    secure = (request.is_secure
              or request.headers.get("X-Forwarded-Proto") == "https")
    resp.set_cookie(ADMIN_COOKIE, tok, max_age=SESSION_DAYS * 86400,
                    httponly=True, samesite="Lax", secure=secure)
    return resp


@app.route("/api/admin_deactivate", methods=["POST"])
def api_admin_deactivate():
    con = _db()
    try:
        row = _current_user(con)
        if row:
            with con:
                con.execute("UPDATE users SET admin = 0 WHERE username = ?",
                            (row[0],))
    finally:
        con.close()
    tok = request.cookies.get(ADMIN_COOKIE)
    if tok:
        _ADMIN_TOKS.discard(_tok_hash(tok))
    resp = jsonify(ok=True, admin=False)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


# ------------------------------------------------------------------- routes
@app.route("/")
def index():
    return render_template("index.html")


# PWA : le service worker doit être servi à la racine pour contrôler tout
# le site, et le manifest y gagne un chemin stable.
@app.route("/sw.js")
def sw():
    return app.send_static_file("sw.js")


@app.route("/manifest.webmanifest")
def manifest():
    resp = app.send_static_file("manifest.webmanifest")
    resp.mimetype = "application/manifest+json"
    return resp


@app.route("/favicon.ico")
def favicon():
    # certains navigateurs demandent /favicon.ico sans lire le HTML
    return app.send_static_file("icons/icon-192.png")


@app.route("/api/create", methods=["POST"])
def api_create():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    game = data.get("game") if data.get("game") in GAMES else "draw"
    if not name:
        return jsonify(error="Choisis un pseudo."), 400
    user, avatar, admin = _visitor_profile()
    sent = data.get("avatar")
    if sent in AVATARS:
        avatar = sent
    with LOCK:
        # ménage : salons de plus de 3 h
        for c in [c for c, r in ROOMS.items() if _now() - r["created"] > 10800]:
            del ROOMS[c]
        code = _new_code()
        pid = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        ROOMS[code] = _new_room(pid, name, game)
        ROOMS[code]["players"][pid].update(user=user, avatar=avatar,
                                           admin=admin)
        _chat(ROOMS[code], f"🎈 {name} a créé le salon.")
    return jsonify(room=code, pid=pid, game=game)


@app.route("/api/join", methods=["POST"])
def api_join():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="Choisis un pseudo."), 400
    user, avatar, admin = _visitor_profile()
    sent = data.get("avatar")
    if sent in AVATARS:
        avatar = sent
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if len(room["players"]) >= MAX_PLAYERS:
            return jsonify(error="Salon complet."), 400
        t = room["kicked_names"].get(_norm(name))
        if t and _now() - t < KICK_BAN_S:
            return jsonify(error="Tu as été exclu(e) de ce salon."), 403
        pid = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        p = _new_player(name)
        p.update(user=user, avatar=avatar, admin=admin)
        if room["game"] == "chain":
            p["lives"] = room["lives_max"]
            if room["state"] == "playing":
                p["alive"] = False    # spectateur jusqu'à la prochaine manche
                p["lives"] = 0
        room["players"][pid] = p
        room["order"].append(pid)
        _chat(room, f"👋 {name} a rejoint la partie."
              + (" (spectateur jusqu'à la prochaine manche)"
                 if room["game"] == "chain" and room["state"] == "playing"
                 else ""))
    return jsonify(room=data["room"].upper(), pid=pid, game=room["game"])


@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if data.get("pid") != room["host"]:
            return jsonify(error="Seul l'hôte peut lancer."), 403
        if len(room["players"]) < 2:
            return jsonify(error="Il faut au moins 2 joueurs."), 400
        if room["state"] in ("lobby", "end"):
            if room["game"] == "draw":
                room["round"] = 0
                room["drawer_queue"] = []
                for p in room["players"].values():
                    p["score"] = 0
                    p["s_guessed"] = 0
                _start_turn(room)
            elif room["game"] == "wave":
                room["round"] = 0
                room["master_queue"] = []
                room["pairs_used"] = set()
                for p in room["players"].values():
                    p["score"] = 0
                    p["round_gain"] = 0
                _wave_start_turn(room)
            else:
                _chain_start(room)
    return jsonify(ok=True)


@app.route("/api/config", methods=["POST"])
def api_config():
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if data.get("pid") != room["host"] or room["state"] not in ("lobby", "end"):
            return jsonify(error="Seul l'hôte peut régler la partie."), 403
        if room["game"] == "draw":
            if data.get("lang") in WORDS:
                room["lang"] = data["lang"]
            if data.get("mode") in MODES:
                room["mode"] = data["mode"]
            if data.get("rounds"):
                room["max_rounds"] = max(1, min(10, int(data["rounds"])))
            if data.get("draw_time"):
                room["draw_time"] = max(30, min(180, int(data["draw_time"])))
            _chat(room, f"⚙️ Réglages : {LANG_NAMES[room['lang']]} · "
                        f"{MODE_NAMES[room['mode']]} · "
                        f"{room['max_rounds']} tours · {room['draw_time']} s")
        elif room["game"] == "wave":
            if data.get("mode") in WAVE_MODES:
                room["mode"] = data["mode"]
            if data.get("rounds"):
                room["max_rounds"] = max(1, min(8, int(data["rounds"])))
            _chat(room, f"⚙️ Réglages : {WAVE_MODE_NAMES[room['mode']]} · "
                        f"{room['max_rounds']} tours")
        else:
            if data.get("lang") in WORDS:
                room["lang"] = data["lang"]
            if data.get("turn_time"):
                room["turn_time"] = max(8, min(60, int(data["turn_time"])))
            if data.get("lives"):
                room["lives_max"] = max(1, min(5, int(data["lives"])))
            _chat(room, f"⚙️ Réglages : {LANG_NAMES[room['lang']]} · "
                        f"{room['turn_time']} s par tour · "
                        f"{room['lives_max']} ❤️ par joueur")
    return jsonify(ok=True)


@app.route("/api/choose", methods=["POST"])
def api_choose():
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if room["game"] == "draw" and room["state"] == "choosing" \
                and data.get("pid") == room["drawer"] \
                and data.get("word") in room["choices"]:
            _begin_drawing(room, data["word"])
    return jsonify(ok=True)


@app.route("/api/stroke", methods=["POST"])
def api_stroke():
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if room["game"] != "draw" or room["state"] != "drawing" \
                or data.get("pid") != room["drawer"]:
            return jsonify(ok=False)
        if data.get("clear"):
            room["strokes"] = []
            room["clear_seq"] += 1
        if data.get("undo") and room["strokes"]:
            last_gid = room["strokes"][-1].get("gid")
            room["strokes"] = [s for s in room["strokes"]
                               if s.get("gid") != last_gid]
            room["clear_seq"] += 1     # les clients rejouent tout le dessin
        for s in (data.get("strokes") or [])[:40]:
            pts = s.get("pts") or []
            tool = s.get("tool", "pen")
            if not pts or tool not in ("pen", "eraser", "line",
                                       "rect", "circle", "fill"):
                continue
            room["stroke_seq"] += 1
            room["strokes"].append({
                "seq": room["stroke_seq"],
                "gid": str(s.get("gid", room["stroke_seq"]))[:16],
                "tool": tool,
                "color": str(s.get("color", "#1c1c28"))[:9],
                "size": max(1, min(40, int(s.get("size", 4)))),
                "pts": [[round(float(x), 4), round(float(y), 4)]
                        for x, y in pts[:600]],
            })
        room["strokes"] = room["strokes"][-2000:]
    return jsonify(ok=True)


@app.route("/api/guess", methods=["POST"])
def api_guess():
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        pid = data.get("pid")
        player = room["players"].get(pid)
        text = (data.get("text") or "").strip()[:80]
        if not player or not text:
            return jsonify(ok=False)
        player["last_seen"] = _now()

        # Enchaîne n'a pas de chat joueur : on se contente de rafraîchir
        # la présence (le mot est soumis via /api/word, pas ici).
        if room["game"] == "chain":
            return jsonify(ok=True)

        # Aide admin privée : réponse dans le JSON uniquement, jamais dans
        # room["chat"] — invisible des autres joueurs, même côté réseau.
        if text.startswith("?") and player.get("admin"):
            q = _letters_only(text[1:])
            if not q:
                if room["game"] == "wave":
                    priv = (f"🔎 Cible cachée : {room['target'] * 100:.0f} %"
                            if room["state"] in ("clue", "guess")
                            else "🔎 Aucun tour en cours.")
                else:
                    priv = (f"🔎 Mot à deviner : « {room['word']} »"
                            if room["state"] == "drawing" and room.get("word")
                            else "🔎 Aucun mot en cours.")
                return jsonify(ok=True, priv=priv)
            ws = CHAIN_DICT.get(room.get("lang", "fr"))
            total = ws.count_prefix(q) if ws else 0
            if not total:
                return jsonify(ok=True, priv=f"🔎 Aucun mot en « {q}… ».")
            words = ws.prefix_list(q, 30)
            priv = (f"🔎 {total} mot(s) en « {q}… » : " + ", ".join(words)
                    + (" …" if total > len(words) else ""))
            return jsonify(ok=True, priv=priv)

        drawing = room["game"] == "draw" and room["state"] == "drawing"
        is_drawer = room["game"] == "draw" and pid == room["drawer"]

        if drawing and not is_drawer and not player["guessed"]:
            if _norm(text) == _norm(room["word"]):
                # 100 pts de base + jusqu'à 100 selon le temps restant
                # + 30 de prime au premier qui trouve, le tout x multiplicateur
                first = not any(p["guessed"] for p in room["players"].values())
                player["guessed"] = True
                player["s_guessed"] = player.get("s_guessed", 0) + 1
                left = max(0, room["timer_end"] - _now())
                gain = int((100 + left / room["draw_time"] * 100
                            + (30 if first else 0))
                           * room.get("word_mult", 1.0))
                player["score"] += gain
                player["round_gain"] = gain
                _chat(room, f"✅ {player['name']} a trouvé le mot !", "correct")
                others = [p for k, p in room["players"].items()
                          if k != room["drawer"]]
                if all(p["guessed"] for p in others):
                    _end_turn(room, found_all=True)
                return jsonify(ok=True)
            if _is_close(text, room["word"]):
                # proche du mot : popup côté client, rien dans le chat
                return jsonify(ok=True, close=True)
            if _norm(room["word"]) in _norm(text):
                return jsonify(ok=True)  # anti-triche : mot noyé dans une phrase
        # le dessinateur et ceux qui ont trouvé ne peuvent pas révéler le mot
        if drawing and (is_drawer or player["guessed"]) \
                and _norm(room["word"]) in _norm(text):
            return jsonify(ok=True)
        _chat(room, text, "guess" if drawing else "chat", player["name"])
    return jsonify(ok=True)


@app.route("/api/kick", methods=["POST"])
def api_kick():
    """Exclusion d'un joueur par un admin (jamais soi-même ni l'hôte)."""
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        pid, target = data.get("pid"), data.get("target")
        me = room["players"].get(pid)
        if not me or not me.get("admin"):
            return jsonify(error="Réservé aux admins."), 403
        tp = room["players"].get(target)
        if not tp or target == pid or target == room["host"]:
            return jsonify(error="Impossible d'exclure ce joueur."), 400
        room["kicked_pids"][target] = _now()
        room["kicked_names"][_norm(tp["name"])] = _now()
        _remove_player(room, target,
                       f"⛔ {tp['name']} a été exclu(e) du salon.")
    return jsonify(ok=True)


CHAIN_WORD_RE = re.compile(
    r"^[a-zà-öø-ÿœæß]+(?:[-'][a-zà-öø-ÿœæß]+)*$")


@app.route("/api/word", methods=["POST"])
def api_word():
    """Enchaîne ! — soumettre un mot quand c'est son tour."""
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if room["game"] != "chain":
            return jsonify(error="Mauvais type de salon."), 400
        pid = data.get("pid")
        player = room["players"].get(pid)
        if not player:
            return jsonify(ok=False)
        player["last_seen"] = _now()
        _tick(room)
        if room["state"] != "playing" or pid != room["turn_pid"]:
            return jsonify(error="Ce n'est pas ton tour !")

        raw = (data.get("word") or "").strip().lower()[:30]
        if not raw or not CHAIN_WORD_RE.match(raw):
            return jsonify(error="Un seul mot, uniquement des lettres "
                                 "(les tirets sont acceptés).")
        letters = _letters_only(raw)
        prefix = room["prefix"]
        if not letters.startswith(prefix):
            return jsonify(error=f"Le mot doit commencer par "
                                 f"« {prefix.upper()} ».")
        if len(letters) <= max(len(prefix), 1):
            return jsonify(error="Trop court ! Il faut au moins une lettre "
                                  "de plus que le début imposé.")
        dict_set = CHAIN_DICT.get(room["lang"], set())
        if letters not in dict_set:
            return jsonify(error=f"« {raw} » n'est pas un mot valide en "
                                 f"{LANG_NAMES[room['lang']]} (orthographe ou "
                                 f"langue ?).")
        if letters in room["words_used"]:
            return jsonify(error=f"« {raw} » a déjà été joué !")

        # ✔ mot accepté (pas de points dans Enchaîne : on survit, c'est tout)
        room["words_used"].add(letters)
        player["words"] = player.get("words", 0) + 1
        room["words_count"] += 1
        room["chain_seq"] += 1
        room["chain"].append({"seq": room["chain_seq"],
                              "name": player["name"],
                              "word": raw, "lvl": room["level"]})
        room["chain"] = room["chain"][-150:]

        # escalade : plus la partie dure, plus le début imposé est long
        new_lvl = min(CHAIN_MAX_LEVEL,
                      1 + room["words_count"] // CHAIN_ESC_EVERY)
        if new_lvl != room["level"]:
            room["level"] = new_lvl
            _chat(room, f"⚡ Ça se corse ! Niveau {new_lvl} : le début "
                        f"imposé fait maintenant {new_lvl} lettres !")
        room["prefix"] = _chain_new_prefix(room)
        _chain_advance(room, from_pid=pid)
    return jsonify(ok=True)


def _wave_room(data, states):
    """Salon Longueur d'onde dont c'est bien le maître qui parle."""
    room, err = _room_or_404(data.get("room"))
    if err:
        return None, err
    if room["game"] != "wave":
        return None, (jsonify(error="Mauvais type de salon."), 400)
    _tick(room)
    if data.get("pid") != room.get("master") or room["state"] not in states:
        return None, (jsonify(error="Ce n'est pas à toi de jouer."), 403)
    return room, None


@app.route("/api/wave_axis", methods=["POST"])
def api_wave_axis():
    """Mode personnalisé : le maître pose le thème et les deux extrêmes."""
    data = request.get_json(force=True)
    with LOCK:
        room, err = _wave_room(data, ("axis",))
        if err:
            return err
        left = (data.get("left") or "").strip()[:28]
        right = (data.get("right") or "").strip()[:28]
        theme = (data.get("theme") or "").strip()[:32]
        if not left or not right:
            return jsonify(error="Il faut les deux extrêmes de l'axe."), 400
        room["theme"] = theme or "Libre"
        room["left"], room["right"] = left, right
        _wave_begin_clue(room)
    return jsonify(ok=True)


@app.route("/api/wave_clue", methods=["POST"])
def api_wave_clue():
    """Le maître donne son indice : le tour passe en devinette."""
    data = request.get_json(force=True)
    with LOCK:
        room, err = _wave_room(data, ("clue",))
        if err:
            return err
        clue = " ".join((data.get("clue") or "").split())[:60]
        if len(clue) < 2:
            return jsonify(error="Écris un indice (2 caractères min.)."), 400
        room["clue"] = clue
        _wave_begin_guess(room)
    return jsonify(ok=True)


@app.route("/api/wave_place", methods=["POST"])
def api_wave_place():
    """Un joueur valide la position de son aiguille (0 = gauche, 1 = droite)."""
    data = request.get_json(force=True)
    with LOCK:
        room, err = _room_or_404(data.get("room"))
        if err:
            return err
        if room["game"] != "wave":
            return jsonify(error="Mauvais type de salon."), 400
        pid = data.get("pid")
        player = room["players"].get(pid)
        if not player:
            return jsonify(ok=False)
        player["last_seen"] = _now()
        _tick(room)
        if room["state"] != "guess" or pid == room.get("master"):
            return jsonify(error="Ce n'est pas le moment de répondre."), 403
        if pid in room["guesses"]:
            return jsonify(error="Tu as déjà répondu !"), 400
        try:
            pos = float(data.get("pos"))
        except (TypeError, ValueError):
            return jsonify(error="Position invalide."), 400
        room["guesses"][pid] = max(0.0, min(1.0, pos))
        _chat(room, f"✋ {player['name']} a placé son aiguille.", "system")
        _tick(room)      # tout le monde a répondu ? on révèle tout de suite
    return jsonify(ok=True)


# ══════════════════════════════════════════════════ GLOUTON (arène agar.io)

def _agar_stats(j):
    """Une vie terminée : on crédite le compte (jamais bloquant)."""
    if not j.get("user"):
        return
    try:
        con = _db()
        try:
            with con:
                con.execute(
                    "UPDATE users SET ag_games = ag_games + 1, "
                    "ag_best = MAX(ag_best, ?), ag_eaten = ag_eaten + ? "
                    "WHERE username = ?",
                    (int(j["record"]), int(j["manges"]), j["user"]))
        finally:
            con.close()
    except Exception:
        pass


@app.route("/api/agar/join", methods=["POST"])
def api_agar_join():
    """Pas de salon : on entre directement dans l'arène commune."""
    data = request.get_json(force=True)
    nom = (data.get("name") or "").strip()
    if not nom:
        return jsonify(error="Choisis un pseudo."), 400
    user, avatar, admin = _visitor_profile()
    sent = data.get("avatar")
    if sent in AVATARS:
        avatar = sent
    pid = secrets.token_urlsafe(9)
    with ARENE_LOCK:
        agar.tick(ARENE)
        if not agar.rejoindre(ARENE, pid, nom, avatar=avatar, user=user):
            return jsonify(error="L'arène est pleine — réessaie dans un "
                                 "instant."), 400
    return jsonify(pid=pid, palette=agar.COULEURS, monde=agar.MONDE)


@app.route("/api/agar/play", methods=["POST"])
def api_agar_play():
    """Une requête = les commandes du joueur + la vue qu'on lui renvoie."""
    data = request.get_json(force=True)
    pid = data.get("pid")
    with ARENE_LOCK:
        j = ARENE["joueurs"].get(pid)
        if not j:
            return jsonify(perdu=True)      # jeton oublié : le client rejoint
        agar.entree(ARENE, pid, data.get("tx"), data.get("ty"),
                    bool(data.get("split")), bool(data.get("eject")))
        agar.tick(ARENE)
        snap = agar.snapshot(ARENE, pid, int(data.get("seen") or 0))
        if snap is None:
            return jsonify(perdu=True)
        if not snap["vivant"] and not j.get("stats"):
            j["stats"] = True
            _agar_stats(j)
    return jsonify(snap)


@app.route("/api/agar/respawn", methods=["POST"])
def api_agar_respawn():
    data = request.get_json(force=True)
    with ARENE_LOCK:
        agar.tick(ARENE)
        agar.renaitre(ARENE, data.get("pid"))
    return jsonify(ok=True)


@app.route("/api/agar/leave", methods=["POST"])
def api_agar_leave():
    data = request.get_json(force=True)
    with ARENE_LOCK:
        j = ARENE["joueurs"].get(data.get("pid"))
        if j and j["mort"] is None and not j.get("stats"):
            j["stats"] = True
            _agar_stats(j)
        agar.quitter(ARENE, data.get("pid"))
    return jsonify(ok=True)


@app.route("/api/state")
def api_state():
    code = request.args.get("room")
    pid = request.args.get("pid")
    s_from = int(request.args.get("s", 0))
    c_from = int(request.args.get("c", 0))
    w_from = int(request.args.get("w", 0))
    f_from = int(request.args.get("f", 0))
    with LOCK:
        room, err = _room_or_404(code)
        if err:
            return err
        if pid in room["players"]:
            room["players"][pid]["last_seen"] = _now()
        _tick(room)
        # seul un admin voit les pids des autres (nécessaires pour /api/kick)
        is_admin = bool(room["players"].get(pid, {}).get("admin"))
        kicked = pid in room["kicked_pids"]

        if room["game"] == "wave":
            master = room.get("master")
            me_master = pid == master
            revealing = room["state"] == "reveal"
            # la cible n'est envoyée qu'au maître (et à tous au dévoilement) :
            # aucun joueur ne peut la lire dans la réponse réseau.
            show_target = revealing or (me_master and
                                        room["state"] in ("clue", "guess"))
            gains = room.get("gains", {})
            players = [{"name": p["name"], "score": p["score"],
                        "gain": p["round_gain"], "avatar": p.get("avatar", ""),
                        "master": k == master, "host": k == room["host"],
                        "done": k in room["guesses"], "me": k == pid,
                        **({"pid": k} if is_admin else {})}
                       for k, p in sorted(room["players"].items(),
                                          key=lambda kv: -kv[1]["score"])]
            needles = []
            if revealing:
                needles = [{"name": room["players"][k]["name"],
                            "avatar": room["players"][k].get("avatar", ""),
                            "pos": v, "pts": gains.get(k, 0), "me": k == pid}
                           for k, v in room["guesses"].items()
                           if k in room["players"]]
                needles.sort(key=lambda n: n["pos"])
            return jsonify(
                game="wave",
                state=room["state"],
                round=room["round"], max_rounds=room["max_rounds"],
                mode=room.get("mode", "prefait"), mode_names=WAVE_MODE_NAMES,
                players=players,
                theme=room["theme"], left=room["left"], right=room["right"],
                clue=room["clue"] if room["state"] in ("guess",
                                                       "reveal") else "",
                target=room["target"] if show_target else None,
                band=WAVE_BAND,
                master_name=(room["players"].get(master, {})
                             .get("name", "")),
                me_master=me_master,
                my_pos=room["guesses"].get(pid),
                needles=needles,
                answered=len(room["guesses"]),
                need=max(0, len(room["players"]) - 1),
                time_left=max(0, int(room["timer_end"] - _now()))
                if room["state"] in ("axis", "clue", "guess") else 0,
                chat=[m for m in room["chat"] if m["seq"] > c_from],
                in_room=pid in room["players"],
                kicked=kicked,
            )

        if room["game"] == "chain":
            # classement : vivants (ordre d'arrivée), puis éliminés du plus
            # récent au plus ancien — pas de points dans Enchaîne.
            elim = room.get("elim", [])
            order = room["order"]

            def _rank(kv):
                k, p = kv
                if p["alive"]:
                    return (0, order.index(k) if k in order else 99)
                return (1, -elim.index(k) if k in elim else 1)

            players = [{"name": p["name"], "words": p.get("words", 0),
                        "lives": p["lives"], "avatar": p.get("avatar", ""),
                        "alive": p["alive"], "host": k == room["host"],
                        "turn": k == room["turn_pid"], "me": k == pid,
                        **({"pid": k} if is_admin else {})}
                       for k, p in sorted(room["players"].items(),
                                          key=_rank)]
            me = room["players"].get(pid, {})
            return jsonify(
                game="chain",
                state=room["state"],
                lang=room["lang"], lang_names=LANG_NAMES,
                players=players,
                prefix=room["prefix"] if room["state"] == "playing" else "",
                level=room["level"],
                words_count=room["words_count"],
                turn_time=room["turn_time"], lives_max=room["lives_max"],
                turn_name=(room["players"].get(room["turn_pid"], {})
                           .get("name", "")),
                me_turn=(pid == room["turn_pid"]
                         and room["state"] == "playing"),
                me_alive=bool(me.get("alive")),
                winner=room.get("winner", ""),
                time_left=max(0, int(room["turn_end"] - _now()))
                if room["state"] == "playing" else 0,
                chain=[e for e in room["chain"] if e["seq"] > w_from],
                feed=[m for m in room["feed"] if m["seq"] > f_from],
                in_room=pid in room["players"],
                kicked=kicked,
            )

        me_drawer = pid == room["drawer"]
        players = [{"name": p["name"], "score": p["score"],
                    "guessed": p["guessed"], "gain": p["round_gain"],
                    "avatar": p.get("avatar", ""),
                    "drawer": k == room["drawer"], "host": k == room["host"],
                    "me": k == pid,
                    **({"pid": k} if is_admin else {})}
                   for k, p in sorted(room["players"].items(),
                                      key=lambda kv: -kv[1]["score"])]
        word_view = ""
        if room["state"] == "drawing":
            word_view = room["word"] if me_drawer else room["hint"]
        elif room["state"] in ("reveal",):
            word_view = room["word"] or ""

        return jsonify(
            game="draw",
            state=room["state"],
            round=room["round"], max_rounds=room["max_rounds"],
            lang=room["lang"], lang_names=LANG_NAMES,
            mode=room.get("mode", "debutant"), mode_names=MODE_NAMES,
            draw_time=room["draw_time"],
            players=players,
            drawer_name=(room["players"].get(room["drawer"], {})
                         .get("name", "")),
            me_drawer=me_drawer,
            choices=[{"word": w,
                      "diff": room["choice_diff"].get(w, "2"),
                      "label": DIFF_LABEL[room["choice_diff"].get(w, "2")],
                      "name": DIFF_NAME[room["choice_diff"].get(w, "2")],
                      "mult": DIFF_MULT[room["choice_diff"].get(w, "2")]}
                     for w in room["choices"]]
            if (me_drawer and room["state"] == "choosing") else [],
            word=word_view,
            time_left=max(0, int(room["timer_end"] - _now()))
            if room["state"] in ("choosing", "drawing") else 0,
            strokes=[s for s in room["strokes"] if s["seq"] > s_from],
            clear_seq=room["clear_seq"],
            chat=[m for m in room["chat"] if m["seq"] > c_from],
            in_room=pid in room["players"],
            kicked=kicked,
        )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
