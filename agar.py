# -*- coding: utf-8 -*-
"""
GLOUTON ! — l'arène façon agar.io de poblox.

Pas de salon, pas de code : une seule arène partagée, on tombe dedans avec
tout le monde. Des bots (de très nuls à franchement redoutables) complètent
la population quand il n'y a pas assez de vrais joueurs.

Ce module ne connaît pas Flask : c'est une simulation pure, testable à part.
`tick()` avance le monde selon l'horloge (cadence bornée), `snapshot()` rend
ce qu'un joueur donné doit voir.

Le serveur est autoritaire mais n'a pas de boucle de fond : la physique
avance à chaque requête reçue, `tick()` refusant simplement d'aller plus vite
que MAX_HZ. Quand personne ne joue, plus rien ne bouge — ce qui tombe bien.
"""

import math
import random
import time

# ─────────────────────────────────────────────────────────── réglages
MONDE = 4600.0            # arène carrée, en unités de jeu
MAX_HZ = 22.0             # cadence maxi de simulation (CPU PythonAnywhere)
DT_MAX = 0.12             # un pas ne saute jamais plus que ça

MASSE_DEPART = 24.0
MASSE_MIN = 12.0          # en dessous, une cellule ne peut plus se scinder
MASSE_MAX = 24000.0
CELLS_MAX = 8             # morceaux maxi par joueur (agar.io en met 16)
SPLIT_MIN = 36.0          # masse mini pour se couper en deux
FUSION_BASE = 11.0        # secondes avant de pouvoir refusionner
FUSION_PAR_MASSE = 0.018  # … + ça par point de masse
EJECT_COUT = 18.0         # masse perdue quand on crache
EJECT_MASSE = 13.0        # masse du crachat
MANGE_RATIO = 1.20        # il faut être 20 % plus gros pour manger
MANGE_COUV = 0.35         # … et recouvrir suffisamment le centre de l'autre
DECAY_SEUIL = 260.0       # au-dessus, on fond doucement
DECAY_TAUX = 0.0022       # par seconde

FOOD_MAX = 840
FOOD_MASSE = 1.5
VIRUS_MAX = 22
VIRUS_MASSE = 115.0

MAX_HUMAINS = 24          # au-delà, l'arène refuse du monde
POP_CIBLE = 13            # bots ajoutés pour atteindre ce total
TIMEOUT = 20.0            # secondes sans nouvelle avant d'être retiré
RESPAWN_BOT = 4.0         # secondes avant qu'un bot mangé revienne

COULEURS = [
    "#e0574f", "#3b7dd8", "#2f9e6b", "#9364d9", "#d98b2b", "#12a3b8",
    "#d4569b", "#7fa63c", "#5f5fd6", "#c2593c", "#2e8f8f", "#b5478f",
    "#4a7fb5", "#8a6bd1", "#3f9e5a", "#cf6a3a",
]

NOMS_BOTS = [
    "Bidule", "Grosminet", "Patapouf", "Croquette", "Roudoudou", "Bouboule",
    "Ninja", "Frimousse", "Chamallow", "Turbo", "Praline", "Ravioli",
    "Cannelle", "Pistache", "Grelot", "Moustache", "Zigzag", "Pépito",
    "Coquelicot", "Biscotte", "Nougat", "Tornade", "Ficelle", "Caramel",
    "Boulette", "Sushi", "Gaufrette", "Comète", "Nutella", "Pixel",
    "Vermicelle", "Popcorn", "Éclair", "Sardine", "Bulldozer", "Cachou",
]


# ─────────────────────────────────────────────────────────── utilitaires
def rayon(m):
    return math.sqrt(m) * 4.2


def vitesse(m):
    """Plus on est gros, plus on est lent (courbe d'agar.io)."""
    return 430.0 / (m ** 0.33)


def _borne(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _grille(items, taille):
    """Index spatial jetable : évite le O(N²) sur la nourriture."""
    g = {}
    for it in items:
        g.setdefault((int(it["x"] / taille), int(it["y"] / taille)),
                     []).append(it)
    return g


def _autour(g, x, y, taille, rayon_rech):
    """Cases de la grille touchées par un cercle."""
    n = int(rayon_rech / taille) + 1
    cx, cy = int(x / taille), int(y / taille)
    out = []
    for i in range(cx - n, cx + n + 1):
        for j in range(cy - n, cy + n + 1):
            b = g.get((i, j))
            if b:
                out.extend(b)
    return out


# ─────────────────────────────────────────────────────────── le monde
def nouveau_monde():
    w = {
        "joueurs": {},        # pid -> joueur
        "food": [],
        "virus": [],
        "eject": [],
        "t": time.time(),     # horloge du dernier pas
        "seq": 1,             # compteur d'identifiants de cellules
        "couleur_i": 0,
        "morts": [],          # petit journal : (horodatage, texte)
        "morts_seq": 0,
    }
    for _ in range(FOOD_MAX):
        w["food"].append(_nouvelle_graine(w))
    for _ in range(VIRUS_MAX):
        w["virus"].append(_nouveau_virus(w))
    return w


def _nouvel_id(w):
    w["seq"] += 1
    return w["seq"]


def _nouvelle_graine(w):
    return {"x": random.uniform(10, MONDE - 10),
            "y": random.uniform(10, MONDE - 10),
            "c": random.randrange(len(COULEURS))}


def _nouveau_virus(w):
    return {"x": random.uniform(160, MONDE - 160),
            "y": random.uniform(160, MONDE - 160),
            "m": VIRUS_MASSE}


def _place_libre(w, m):
    """Un coin tranquille : pas de grosse cellule dans les parages."""
    r = rayon(m)
    for _ in range(30):
        x = random.uniform(120, MONDE - 120)
        y = random.uniform(120, MONDE - 120)
        ok = True
        for j in w["joueurs"].values():
            for c in j["cells"]:
                if c["m"] > m * 0.9:
                    d = math.hypot(c["x"] - x, c["y"] - y)
                    if d < rayon(c["m"]) + r + 240:
                        ok = False
                        break
            if not ok:
                break
        if ok:
            return x, y
    return random.uniform(120, MONDE - 120), random.uniform(120, MONDE - 120)


def _cellule(w, x, y, m, fus=0.0):
    return {"id": _nouvel_id(w), "x": x, "y": y, "m": m,
            "vx": 0.0, "vy": 0.0, "fus": fus}


def _nouveau_joueur(w, pid, nom, bot=False, skill=0.5, avatar="", user=None):
    x, y = _place_libre(w, MASSE_DEPART)
    w["couleur_i"] += 1
    return {
        "pid": pid,
        "nom": nom[:14],
        "couleur": w["couleur_i"] % len(COULEURS),
        "avatar": avatar,
        "user": user,             # compte connecté (pour les stats)
        "bot": bot,
        "skill": skill,           # 0 = pitoyable, 1 = redoutable
        "cells": [_cellule(w, x, y, MASSE_DEPART)],
        "tx": x, "ty": y,         # point visé
        "split": False, "eject": False,
        "vu": time.time(),
        "mort": None,             # horodatage de la mort
        "tueur": "",
        "record": MASSE_DEPART,   # plus grosse masse atteinte (cette vie)
        "manges": 0,              # joueurs/bots avalés (cette vie)
        "stats": False,           # vie déjà comptabilisée au tableau de bord
        "reflexe": 0.0,           # prochaine décision (bots)
        "errance": (x, y),
    }


# ─────────────────────────────────────────────────────────── entrée/sortie
def humains(w):
    return [j for j in w["joueurs"].values() if not j["bot"]]


def rejoindre(w, pid, nom, avatar="", user=None):
    if len([j for j in w["joueurs"].values() if not j["bot"]]) >= MAX_HUMAINS:
        return False
    w["joueurs"][pid] = _nouveau_joueur(w, pid, nom or "Anonyme",
                                        avatar=avatar, user=user)
    return True


def quitter(w, pid):
    j = w["joueurs"].pop(pid, None)
    if j:
        _semer_restes(w, j)
    return j


def renaitre(w, pid):
    j = w["joueurs"].get(pid)
    if not j or j["mort"] is None:
        return
    x, y = _place_libre(w, MASSE_DEPART)
    j["cells"] = [_cellule(w, x, y, MASSE_DEPART)]
    j["tx"], j["ty"] = x, y
    j["mort"] = None
    j["tueur"] = ""
    j["record"] = MASSE_DEPART    # les stats sont par vie, pas cumulées
    j["manges"] = 0
    j["stats"] = False


def entree(w, pid, tx, ty, split, eject):
    j = w["joueurs"].get(pid)
    if not j:
        return
    j["vu"] = time.time()
    if tx is not None and ty is not None:
        j["tx"] = _borne(float(tx), 0.0, MONDE)
        j["ty"] = _borne(float(ty), 0.0, MONDE)
    if split:
        j["split"] = True
    if eject:
        j["eject"] = True


def _semer_restes(w, j):
    """Un joueur parti laisse un peu de nourriture derrière lui."""
    for c in j["cells"]:
        for _ in range(min(6, int(c["m"] / 24) + 1)):
            a = random.uniform(0, 6.283)
            d = random.uniform(0, rayon(c["m"]))
            w["food"].append({"x": _borne(c["x"] + math.cos(a) * d, 5,
                                          MONDE - 5),
                              "y": _borne(c["y"] + math.sin(a) * d, 5,
                                          MONDE - 5),
                              "c": j["couleur"]})
    j["cells"] = []


# ─────────────────────────────────────────────────────────── actions
def _scinder(w, j, now):
    """Espace : chaque cellule assez grosse projette la moitié d'elle-même."""
    libres = CELLS_MAX - len(j["cells"])
    if libres <= 0:
        return
    # les plus grosses d'abord : c'est ce qui rend le split utile
    for c in sorted(j["cells"], key=lambda c: -c["m"])[:libres]:
        if c["m"] < SPLIT_MIN:
            continue
        dx, dy = j["tx"] - c["x"], j["ty"] - c["y"]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            a = random.uniform(0, 6.283)
            dx, dy, d = math.cos(a), math.sin(a), 1.0
        dx, dy = dx / d, dy / d
        c["m"] *= 0.5
        c["fus"] = now + FUSION_BASE + c["m"] * FUSION_PAR_MASSE
        n = _cellule(w, c["x"], c["y"], c["m"], c["fus"])
        v = 640.0 + rayon(c["m"]) * 2.2
        n["vx"], n["vy"] = dx * v, dy * v
        j["cells"].append(n)


def _cracher(w, j):
    """W : un petit crachat de masse, à donner ou à semer."""
    for c in j["cells"]:
        # comme agar.io : on peut cracher bien avant de pouvoir se diviser
        if c["m"] < EJECT_COUT + 20.0:
            continue
        dx, dy = j["tx"] - c["x"], j["ty"] - c["y"]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            continue
        dx, dy = dx / d, dy / d
        c["m"] -= EJECT_COUT
        r = rayon(c["m"])
        e = {"id": _nouvel_id(w), "x": c["x"] + dx * r, "y": c["y"] + dy * r,
             "m": EJECT_MASSE, "vx": dx * 760.0, "vy": dy * 760.0,
             "c": j["couleur"]}
        w["eject"].append(e)


def _exploser(w, j, c, now):
    """Un virus avalé fait éclater la cellule en plusieurs morceaux."""
    libres = CELLS_MAX - len(j["cells"])
    if libres <= 0:
        return
    n = min(libres, 6)
    part = c["m"] / (n + 1)
    c["m"] = part
    c["fus"] = now + FUSION_BASE + part * FUSION_PAR_MASSE
    for i in range(n):
        a = 6.283 * i / n + random.uniform(-0.3, 0.3)
        m = _cellule(w, c["x"], c["y"], part, c["fus"])
        v = 430.0 + random.uniform(0, 180)
        m["vx"], m["vy"] = math.cos(a) * v, math.sin(a) * v
        j["cells"].append(m)


# ─────────────────────────────────────────────────────────── bots
def _ajouter_bot(w):
    pris = {j["nom"] for j in w["joueurs"].values()}
    libres = [n for n in NOMS_BOTS if n not in pris] or NOMS_BOTS
    nom = random.choice(libres)
    # trois écoles : les touristes, les moyens, et ceux qui mordent
    r = random.random()
    if r < 0.40:
        skill = random.uniform(0.05, 0.28)     # très nul : erre, gobe, meurt
    elif r < 0.75:
        skill = random.uniform(0.40, 0.62)     # correct
    else:
        skill = random.uniform(0.78, 1.0)      # chasse le vrai joueur
    pid = "bot-%d" % _nouvel_id(w)
    w["joueurs"][pid] = _nouveau_joueur(w, pid, nom, bot=True, skill=skill)
    return pid


def _peupler(w, now):
    vivants = [j for j in w["joueurs"].values() if j["mort"] is None]
    if len(vivants) < POP_CIBLE:
        # un bot à la fois : la population monte en douceur
        _ajouter_bot(w)
    elif len(vivants) > POP_CIBLE + 2:
        for pid, j in list(w["joueurs"].items()):
            if j["bot"] and j["mort"] is None and \
                    sum(c["m"] for c in j["cells"]) < 80:
                quitter(w, pid)
                break


def _bot_pense(w, j, now, gfood):
    """Décision d'un bot. Le niveau conditionne ce qu'il voit et ose faire."""
    if now < j["reflexe"]:
        return
    j["reflexe"] = now + random.uniform(0.12, 0.34) * (2.2 - j["skill"])
    j["split"] = j["eject"] = False
    if not j["cells"]:
        return

    tete = max(j["cells"], key=lambda c: c["m"])
    ma = tete["m"]
    vue = 380 + 900 * j["skill"] + rayon(ma) * 3

    menace = None, 1e18
    proie = None, 1e18
    for autre in w["joueurs"].values():
        if autre is j or autre["mort"] is not None:
            continue
        for c in autre["cells"]:
            dx, dy = c["x"] - tete["x"], c["y"] - tete["y"]
            d2 = dx * dx + dy * dy
            if d2 > vue * vue:
                continue
            if c["m"] > ma * MANGE_RATIO:
                if d2 < menace[1]:
                    menace = c, d2
            elif ma > c["m"] * MANGE_RATIO:
                if d2 < proie[1]:
                    proie = c, d2

    # fuir : seuls les bots un peu réveillés regardent derrière eux
    if menace[0] is not None and j["skill"] > 0.32:
        c = menace[0]
        j["tx"] = _borne(tete["x"] - (c["x"] - tete["x"]) * 3, 40, MONDE - 40)
        j["ty"] = _borne(tete["y"] - (c["y"] - tete["y"]) * 3, 40, MONDE - 40)
        return

    # chasser : les bons bots coupent pour rattraper une proie qui fuit
    if proie[0] is not None and j["skill"] > 0.45:
        c = proie[0]
        j["tx"], j["ty"] = c["x"], c["y"]
        d = math.sqrt(proie[1])
        if (j["skill"] > 0.7 and ma > c["m"] * 2.6
                and len(j["cells"]) < CELLS_MAX - 1
                and ma / 2 > c["m"] * MANGE_RATIO
                and rayon(ma) * 1.2 < d < rayon(ma) * 4.2):
            j["split"] = True
        return

    # sinon : la nourriture la plus proche (les nuls la cherchent moins loin)
    portee = 200 + 700 * j["skill"]
    best, bd = None, portee * portee
    for f in _autour(gfood, tete["x"], tete["y"], 220, portee):
        dx, dy = f["x"] - tete["x"], f["y"] - tete["y"]
        d2 = dx * dx + dy * dy
        if d2 < bd:
            best, bd = f, d2
    if best is not None:
        j["tx"], j["ty"] = best["x"], best["y"]
        return

    # rien en vue : on erre vers un point au hasard
    ex, ey = j["errance"]
    if math.hypot(ex - tete["x"], ey - tete["y"]) < 120:
        j["errance"] = (random.uniform(80, MONDE - 80),
                        random.uniform(80, MONDE - 80))
    j["tx"], j["ty"] = j["errance"]


# ─────────────────────────────────────────────────────────── physique
def pas(w, dt, now):
    """Un pas de simulation."""
    gfood = _grille(w["food"], 220)

    # --- décisions
    for j in w["joueurs"].values():
        if j["mort"] is not None:
            if j["bot"] and now - j["mort"] > RESPAWN_BOT:
                renaitre(w, j["pid"])
            continue
        if j["bot"]:
            _bot_pense(w, j, now, gfood)
        if j["split"]:
            _scinder(w, j, now)
            j["split"] = False
        if j["eject"]:
            _cracher(w, j)
            j["eject"] = False

    # --- déplacement des cellules
    for j in w["joueurs"].values():
        cells = j["cells"]
        for c in cells:
            dx, dy = j["tx"] - c["x"], j["ty"] - c["y"]
            d = math.hypot(dx, dy)
            r = rayon(c["m"])
            if d > 1e-6:
                # on ralentit quand la cible est dans la cellule elle-même
                f = min(1.0, d / max(24.0, r))
                v = vitesse(c["m"]) * f
                c["x"] += dx / d * v * dt
                c["y"] += dy / d * v * dt
            # impulsion résiduelle (split, explosion) qui s'amortit
            if c["vx"] or c["vy"]:
                c["x"] += c["vx"] * dt
                c["y"] += c["vy"] * dt
                amorti = math.exp(-6.5 * dt)
                c["vx"] *= amorti
                c["vy"] *= amorti
                if abs(c["vx"]) < 4 and abs(c["vy"]) < 4:
                    c["vx"] = c["vy"] = 0.0
            c["x"] = _borne(c["x"], r, MONDE - r)
            c["y"] = _borne(c["y"], r, MONDE - r)

        # --- cohésion : fusionner si le délai est passé, sinon se repousser
        n = len(cells)
        for a in range(n):
            ca = cells[a]
            if ca["m"] <= 0:
                continue
            for b in range(a + 1, n):
                cb = cells[b]
                if cb["m"] <= 0:
                    continue
                dx, dy = cb["x"] - ca["x"], cb["y"] - ca["y"]
                d = math.hypot(dx, dy)
                ra, rb = rayon(ca["m"]), rayon(cb["m"])
                if d >= ra + rb:
                    continue
                if ca["fus"] <= now and cb["fus"] <= now:
                    if d < max(ra, rb) * 0.86:          # assez superposées
                        gros, petit = (ca, cb) if ca["m"] >= cb["m"] else (cb, ca)
                        t = gros["m"] + petit["m"]
                        gros["x"] = (gros["x"] * gros["m"] +
                                     petit["x"] * petit["m"]) / t
                        gros["y"] = (gros["y"] * gros["m"] +
                                     petit["y"] * petit["m"]) / t
                        gros["m"] = min(MASSE_MAX, t)
                        petit["m"] = 0.0
                        continue
                    # elles peuvent fusionner : on les laisse se chevaucher
                    continue
                # sinon on les écarte doucement (pas de tas informe)
                if d < 1e-6:
                    dx, dy, d = random.uniform(-1, 1), random.uniform(-1, 1), 1.0
                push = (ra + rb - d) * 0.5 * min(1.0, dt * 9)
                ca["x"] -= dx / d * push
                ca["y"] -= dy / d * push
                cb["x"] += dx / d * push
                cb["y"] += dy / d * push
        j["cells"] = [c for c in cells if c["m"] > 0]

    # --- crachats : ils volent puis se posent
    for e in w["eject"]:
        e["x"] += e["vx"] * dt
        e["y"] += e["vy"] * dt
        amorti = math.exp(-5.0 * dt)
        e["vx"] *= amorti
        e["vy"] *= amorti
        r = rayon(e["m"])
        e["x"] = _borne(e["x"], r, MONDE - r)
        e["y"] = _borne(e["y"], r, MONDE - r)

    # --- repas
    _manger(w, now, gfood)

    # --- fonte des gros + repop
    for j in w["joueurs"].values():
        for c in j["cells"]:
            if c["m"] > DECAY_SEUIL:
                c["m"] -= c["m"] * DECAY_TAUX * dt
        if j["cells"]:
            j["record"] = max(j["record"], sum(c["m"] for c in j["cells"]))
    while len(w["food"]) < FOOD_MAX:
        w["food"].append(_nouvelle_graine(w))
    while len(w["virus"]) < VIRUS_MAX:
        w["virus"].append(_nouveau_virus(w))


def _manger(w, now, gfood):
    vivants = [j for j in w["joueurs"].values() if j["mort"] is None]

    # --- nourriture et crachats (grille : on ne teste que le voisinage)
    geject = _grille(w["eject"], 220)
    mange_f, mange_e = set(), set()
    for j in vivants:
        for c in j["cells"]:
            r = rayon(c["m"])
            for f in _autour(gfood, c["x"], c["y"], 220, r):
                if id(f) in mange_f:
                    continue
                if (f["x"] - c["x"]) ** 2 + (f["y"] - c["y"]) ** 2 < r * r:
                    mange_f.add(id(f))
                    c["m"] = min(MASSE_MAX, c["m"] + FOOD_MASSE)
                    r = rayon(c["m"])
            for e in _autour(geject, c["x"], c["y"], 220, r):
                if id(e) in mange_e or e["m"] >= c["m"]:
                    continue
                if (e["x"] - c["x"]) ** 2 + (e["y"] - c["y"]) ** 2 < r * r:
                    mange_e.add(id(e))
                    c["m"] = min(MASSE_MAX, c["m"] + e["m"])
                    r = rayon(c["m"])
    if mange_f:
        w["food"] = [f for f in w["food"] if id(f) not in mange_f]
    if mange_e:
        w["eject"] = [e for e in w["eject"] if id(e) not in mange_e]

    # --- virus : seuls les gros les avalent, et le regrettent
    for v in list(w["virus"]):
        for j in vivants:
            touche = None
            for c in j["cells"]:
                r = rayon(c["m"])
                if c["m"] > VIRUS_MASSE * 1.15 and \
                        (v["x"] - c["x"]) ** 2 + (v["y"] - c["y"]) ** 2 < \
                        (r - rayon(v["m"]) * 0.4) ** 2:
                    touche = c
                    break
            if touche is not None:
                touche["m"] = min(MASSE_MAX, touche["m"] + v["m"] * 0.4)
                _exploser(w, j, touche, now)
                w["virus"].remove(v)
                break

    # --- joueurs entre eux : peu de cellules, une double boucle suffit
    toutes = []
    for j in vivants:
        for c in j["cells"]:
            toutes.append((c, j))
    toutes.sort(key=lambda t: -t[0]["m"])       # les gros mangent en premier
    morts = set()
    for i in range(len(toutes)):
        ca, ja = toutes[i]
        if ca["m"] <= 0:
            continue
        for k in range(i + 1, len(toutes)):
            cb, jb = toutes[k]
            if jb is ja or cb["m"] <= 0 or ca["m"] <= 0:
                continue
            if ca["m"] < cb["m"] * MANGE_RATIO:
                continue
            ra, rb = rayon(ca["m"]), rayon(cb["m"])
            d = math.hypot(cb["x"] - ca["x"], cb["y"] - ca["y"])
            if d < ra - rb * MANGE_COUV:
                ca["m"] = min(MASSE_MAX, ca["m"] + cb["m"])
                cb["m"] = 0.0
                if len([c for c in jb["cells"] if c["m"] > 0]) == 0:
                    morts.add((jb["pid"], ja["pid"]))
    for j in vivants:
        j["cells"] = [c for c in j["cells"] if c["m"] > 0]
    for pid, tueur_pid in morts:
        j = w["joueurs"].get(pid)
        t = w["joueurs"].get(tueur_pid)
        if not j or j["cells"]:
            continue
        j["mort"] = now
        j["tueur"] = t["nom"] if t else "?"
        if t:
            t["manges"] += 1
            w["morts_seq"] += 1
            w["morts"].append({"seq": w["morts_seq"],
                               "txt": "%s a mangé %s" % (t["nom"], j["nom"])})
            w["morts"] = w["morts"][-30:]


def tick(w):
    """Avance le monde selon l'horloge réelle, sans dépasser MAX_HZ."""
    now = time.time()
    dt = now - w["t"]
    if dt < 1.0 / MAX_HZ:
        return
    w["t"] = now
    # --- ménage : joueurs muets, bots en trop
    for pid, j in list(w["joueurs"].items()):
        if not j["bot"] and now - j["vu"] > TIMEOUT:
            quitter(w, pid)
    _peupler(w, now)
    pas(w, min(dt, DT_MAX), now)


# ─────────────────────────────────────────────────────────── snapshot
def masse_totale(j):
    return sum(c["m"] for c in j["cells"])


def classement(w, n=10):
    tab = [(masse_totale(j), j) for j in w["joueurs"].values()
           if j["mort"] is None and j["cells"]]
    tab.sort(key=lambda t: -t[0])
    return tab[:n]


def snapshot(w, pid, seen=0):
    """Ce que ce joueur doit recevoir : sa vue, et rien de plus."""
    j = w["joueurs"].get(pid)
    if not j:
        return None
    now = time.time()

    if j["cells"]:
        mt = masse_totale(j)
        cx = sum(c["x"] * c["m"] for c in j["cells"]) / mt
        cy = sum(c["y"] * c["m"] for c in j["cells"]) / mt
        # plafonné : même énorme, on ne voit jamais toute la carte —
        # sinon plus aucune tension pour le leader, et le snapshot enfle
        demi = min(rayon(mt) * 5.2 + 520, MONDE * 0.38)
    else:
        mt = 0.0
        cx = cy = MONDE / 2
        demi = 700

    x0, x1 = cx - demi, cx + demi
    y0, y1 = cy - demi, cy + demi

    def dans(o, marge=0.0):
        return x0 - marge <= o["x"] <= x1 + marge and \
               y0 - marge <= o["y"] <= y1 + marge

    cells = []
    for autre in w["joueurs"].values():
        if autre["mort"] is not None:
            continue
        for c in autre["cells"]:
            if dans(c, rayon(c["m"])):
                cells.append([c["id"], round(c["x"], 1), round(c["y"], 1),
                              round(c["m"], 1), autre["couleur"],
                              autre["pid"] == pid, autre["nom"]])

    tab = classement(w)
    rang = 0
    for i, (m, jj) in enumerate(tab, 1):
        if jj is j:
            rang = i

    return {
        "t": round(now, 3),
        "monde": MONDE,
        "vivant": j["mort"] is None,
        "tueur": j["tueur"],
        "masse": int(mt),
        "rang": rang,
        "cam": [round(cx, 1), round(cy, 1)],
        "demi": round(demi, 1),
        "cells": cells,
        "food": [[round(f["x"], 1), round(f["y"], 1), f["c"]]
                 for f in w["food"] if dans(f, 20)],
        "virus": [[round(v["x"], 1), round(v["y"], 1)]
                  for v in w["virus"] if dans(v, 60)],
        "eject": [[e["id"], round(e["x"], 1), round(e["y"], 1), e["c"]]
                  for e in w["eject"] if dans(e, 20)],
        "lead": [[jj["nom"], int(m), jj["pid"] == pid] for m, jj in tab],
        "joueurs": len([x for x in w["joueurs"].values()
                        if x["mort"] is None]),
        "humains": len([x for x in humains(w) if x["mort"] is None]),
        "journal": [m for m in w["morts"] if m["seq"] > seen],
        "record": int(j["record"]),
        "manges": j["manges"],
    }
