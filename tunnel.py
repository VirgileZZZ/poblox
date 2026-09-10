# -*- coding: utf-8 -*-
"""
PARTAGE — un lien https à envoyer, sans rien installer chez les invités.

Lance le serveur poblox puis un « tunnel rapide » Cloudflare : le lien
`https://xxxx.trycloudflare.com` affiché ici marche depuis n'importe où
(4G du téléphone, maison des copains…) tant que la fenêtre reste ouverte.
Aucun compte Cloudflare, aucune configuration.

Pourquoi Cloudflare et pas localtunnel / localhost.run : leurs domaines
(`*.loca.lt`, `*.lhr.life`) sont sur les listes noires de plusieurs
antivirus, ce qui donne un tunnel « qui bugue » sans dire pourquoi.

L'exécutable `cloudflared` est cherché dans .tools/, dans le PATH, puis
dans les autres projets du Bureau (même convention .tools/) et copié ici ;
en dernier recours il est téléchargé une fois (~55 Mo).
"""

import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

# la console Windows peut etre en cp850 : on remplace au lieu de planter
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

RACINE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(RACINE, ".tools")
EXE = os.path.join(TOOLS, "cloudflared.exe" if os.name == "nt" else "cloudflared")
TELECHARGEMENT = ("https://github.com/cloudflare/cloudflared/releases/"
                  "latest/download/cloudflared-windows-amd64.exe")
PORT = 5000
RE_LIEN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

# dossiers qu'on ne fouille jamais : gros et sans intérêt
IGNORES = {"node_modules", ".git", "dist", "build", "venv", ".venv",
           "__pycache__", "AppData", "OneDrive"}


def titre(txt):
    print("\n" + txt)
    print("-" * max(12, len(txt)))


# ───────────────────────────────────────────────── trouver cloudflared
def _chercher_bureau():
    """cloudflared déjà téléchargé par un autre projet (convention .tools/) ?"""
    bureau = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(bureau):
        return None
    base_prof = bureau.rstrip(os.sep).count(os.sep)
    for dossier, sous, fichiers in os.walk(bureau):
        if dossier.count(os.sep) - base_prof >= 4:
            sous[:] = []                       # on ne descend pas plus bas
        sous[:] = [d for d in sous if d not in IGNORES]
        if os.path.basename(dossier) == ".tools":
            for nom in ("cloudflared.exe", "cloudflared"):
                p = os.path.join(dossier, nom)
                if os.path.isfile(p) and os.path.getsize(p) > 1_000_000:
                    return p
    return None


def _telecharger():
    os.makedirs(TOOLS, exist_ok=True)
    part = EXE + ".part"
    print("   Téléchargement de cloudflared (une seule fois)…")
    with urllib.request.urlopen(TELECHARGEMENT, timeout=30) as r, \
            open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        lu = 0
        while True:
            bloc = r.read(262144)
            if not bloc:
                break
            f.write(bloc)
            lu += len(bloc)
            if total:
                print("\r   %3d %%  (%d / %d Mo)"
                      % (lu * 100 // total, lu >> 20, total >> 20), end="")
    print()
    os.replace(part, EXE)


def trouver_cloudflared():
    if os.path.isfile(EXE):
        return EXE
    dans_path = shutil.which("cloudflared")
    if dans_path:
        return dans_path
    ailleurs = _chercher_bureau()
    os.makedirs(TOOLS, exist_ok=True)
    if ailleurs:
        print("   cloudflared récupéré depuis %s" % ailleurs)
        shutil.copy2(ailleurs, EXE)
        return EXE
    _telecharger()
    return EXE


# ───────────────────────────────────────────────── serveur poblox
def poblox_repond():
    """Un poblox tourne-t-il déjà sur le port ? (et pas autre chose)"""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/" % PORT,
                                    timeout=2) as r:
            return b"poblox" in r.read(4000).lower()
    except Exception:
        return False


def port_occupe():
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def demarrer_serveur():
    import flask_app                      # charge les dictionnaires (~5 s)
    # Jamais debug=True derrière un tunnel public : la page d'erreur du
    # débogueur Werkzeug permet d'exécuter du code sur la machine.
    def _run():
        flask_app.app.run(host="0.0.0.0", port=PORT, debug=False,
                          use_reloader=False, threaded=True)
    threading.Thread(target=_run, daemon=True).start()
    for _ in range(80):                    # 40 s max
        if poblox_repond():
            return True
        time.sleep(.5)
    return False


# ───────────────────────────────────────────────── programme
def main():
    os.chdir(RACINE)

    titre("1. Serveur poblox")
    if poblox_repond():
        print("   Déjà lancé sur le port %d — on l'utilise." % PORT)
    elif port_occupe():
        print("   Le port %d est pris par un autre programme." % PORT)
        print("   Ferme-le (ou l'ancienne fenêtre poblox) puis relance.")
        return 1
    else:
        print("   Démarrage…")
        if not demarrer_serveur():
            print("   Le serveur n'a pas démarré. Essaie lancer.bat pour "
                  "voir l'erreur.")
            return 1
        print("   En ligne sur http://localhost:%d" % PORT)

    titre("2. Tunnel Cloudflare")
    try:
        exe = trouver_cloudflared()
    except Exception as e:
        print("   Impossible d'obtenir cloudflared : %s" % e)
        return 1

    proc = subprocess.Popen(
        [exe, "tunnel", "--no-autoupdate", "--url",
         "http://127.0.0.1:%d" % PORT],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1)
    print("   Ouverture du tunnel…")

    lien = None
    try:
        for ligne in proc.stdout:
            m = RE_LIEN.search(ligne)
            if m and not lien:
                lien = m.group(0)
                print("\n" + "=" * 62)
                print("   LIEN A ENVOYER :  " + lien)
                print("=" * 62)
                try:
                    subprocess.run("clip", input=lien, text=True, check=True)
                    print("   (copié dans le presse-papiers)")
                except Exception:
                    pass
                print("   Valable tant que cette fenêtre reste ouverte.")
                print("   Toi, joue plutôt sur http://localhost:%d" % PORT)
                print("   Ctrl+C ou fermer la fenêtre = lien coupé.\n")
            elif not lien and ("ERR" in ligne or "error" in ligne.lower()):
                print("   " + ligne.rstrip())
        code = proc.wait()
        if not lien:
            print("\n   Le tunnel s'est arrêté sans donner de lien "
                  "(code %s). Vérifie ta connexion." % code)
            return 1
    except KeyboardInterrupt:
        print("\n   Arrêt demandé.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
