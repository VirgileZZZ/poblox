# -*- coding: utf-8 -*-
"""
PREPARER L'UPLOAD — fabrique le dossier `pythonanywhere/`.

Il contient EXACTEMENT ce qu'il faut mettre en ligne, et rien d'autre :
ni les .bat (locaux), ni tunnel.py, ni .tools/, ni users.db (celui du
serveur contient les vrais comptes — l'écraser les supprimerait), ni les
__pycache__, ni la doc.

À relancer après chaque modif : le dossier est reconstruit à neuf, donc
il ne peut pas contenir une vieille version d'un fichier.
"""

import io
import os
import shutil
import sys
import time
import zipfile

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

RACINE = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(RACINE, "pythonanywhere")
APPLI = os.path.join(SORTIE, "recre")        # ira dans /home/TON_USER/recre
ZIP = os.path.join(SORTIE, "recre.zip")

# tout ce dont le serveur a besoin pour tourner
FICHIERS = ["flask_app.py", "words.py", "ondes.py", "agar.py",
            "requirements.txt"]
DOSSIERS = ["templates", "static", "dicts"]
# jamais copié, même s'il traîne dans un de ces dossiers
INTERDITS = {"__pycache__", ".tools", "users.db", ".DS_Store", "Thumbs.db"}

A_LIRE = """POBLOX — ce qu'il faut mettre sur PythonAnywhere
================================================
(dossier généré le {date} par preparer_upload.py — ne pas éditer à la main)

Le dossier `recre/` ci-contre est l'arborescence EXACTE à retrouver dans
/home/TON_USER/recre sur PythonAnywhere. Rien d'autre n'est nécessaire.

{liste}
Total : {total}

--------------------------------------------------------------------
LE PLUS RAPIDE : uploader le zip
--------------------------------------------------------------------
1. Onglet Files -> aller dans /home/TON_USER/ -> "Upload a file" ->
   choisir `recre.zip` ({tzip}).
2. Onglet Consoles -> "Bash" -> taper :

       cd ~
       unzip -o recre.zip
       rm recre.zip

   (`-o` écrase les anciens fichiers sans rien demander. users.db n'est
   PAS dans le zip : les comptes existants sont conservés.)
3. Onglet Web -> bouton vert **Reload**. C'est en ligne.

--------------------------------------------------------------------
OU : uploader à la main
--------------------------------------------------------------------
Onglet Files, recopier le contenu de `recre/` dans /home/TON_USER/recre
en respectant les sous-dossiers (templates/, static/, static/icons/,
dicts/), puis **Reload**.

Si le site tourne déjà, seuls les fichiers modifiés sont à renvoyer —
le plus souvent flask_app.py, ondes.py et templates/index.html.
`dicts/` et `static/` ne changent quasiment jamais.

--------------------------------------------------------------------
PREMIÈRE INSTALLATION SEULEMENT
--------------------------------------------------------------------
Onglet Web -> "Add a new web app" -> **Manual configuration** ->
Python 3.10 ou plus.
  . Source code       : /home/TON_USER/recre
  . Working directory : /home/TON_USER/recre
Puis cliquer sur le lien "WSGI configuration file", tout effacer et coller
le contenu de `wsgi_pythonanywhere.py` (ci-contre) en remplaçant TON_USER
par ton nom d'utilisateur PythonAnywhere. Enfin : **Reload**.

Flask est déjà installé sur PythonAnywhere. Au besoin :
Consoles -> Bash -> `pip3 install --user flask`

--------------------------------------------------------------------
À NE JAMAIS FAIRE
--------------------------------------------------------------------
. Ne pas uploader `users.db` : le fichier local est une copie de test,
  celui du serveur contient les vrais comptes. Les migrations de schéma
  se font toutes seules au Reload.
. Garder **1 seul worker web** (le défaut en gratuit) : l'état des salons
  vit en mémoire, plusieurs workers = plusieurs parties parallèles qui ne
  se voient pas.
. Les .bat, tunnel.py et .tools/ ne servent qu'en local : inutile de les
  envoyer (ils sont volontairement absents de ce dossier).
"""


def humain(octets):
    if octets >= 1024 * 1024:
        return "%.1f Mo" % (octets / 1024 / 1024)
    if octets >= 1024:
        return "%d ko" % (octets / 1024)
    return "%d o" % octets


def copiable(nom):
    return nom not in INTERDITS and not nom.endswith((".pyc", ".db"))


def main():
    manquants = [f for f in FICHIERS + DOSSIERS
                 if not os.path.exists(os.path.join(RACINE, f))]
    if manquants:
        print("Introuvable(s) : " + ", ".join(manquants))
        return 1

    if os.path.isdir(SORTIE):
        shutil.rmtree(SORTIE)              # reconstruction a neuf
    os.makedirs(APPLI)

    copies = []                            # (chemin relatif, taille)
    for nom in FICHIERS:
        src = os.path.join(RACINE, nom)
        shutil.copy2(src, os.path.join(APPLI, nom))
        copies.append((nom, os.path.getsize(src)))
    for dossier in DOSSIERS:
        for base, sous, fichiers in os.walk(os.path.join(RACINE, dossier)):
            sous[:] = [d for d in sous if copiable(d)]
            for f in fichiers:
                if not copiable(f):
                    continue
                src = os.path.join(base, f)
                rel = os.path.relpath(src, RACINE)
                dst = os.path.join(APPLI, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copies.append((rel.replace(os.sep, "/"),
                               os.path.getsize(src)))

    # le WSGI ne s'uploade pas : il se colle dans l'onglet Web
    shutil.copy2(os.path.join(RACINE, "wsgi_pythonanywhere.py"),
                 os.path.join(SORTIE, "wsgi_pythonanywhere.py"))

    # zip : les chemins commencent par recre/ pour se dezipper au bon endroit
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, _ in copies:
            z.write(os.path.join(APPLI, rel), "recre/" + rel)

    total = sum(t for _, t in copies)
    liste = "\n".join("  recre/%-28s %10s" % (rel, humain(t))
                      for rel, t in sorted(copies))
    io.open(os.path.join(SORTIE, "A_LIRE.txt"), "w", encoding="utf-8",
            newline="\r\n").write(A_LIRE.format(
                date=time.strftime("%d/%m/%Y a %H:%M"),
                liste=liste, total=humain(total),
                tzip=humain(os.path.getsize(ZIP))))

    print("\n  Dossier pret : %s\n" % SORTIE)
    print(liste)
    print("\n  %d fichiers, %s  ->  recre.zip = %s"
          % (len(copies), humain(total), humain(os.path.getsize(ZIP))))
    print("  Les etapes sont dans pythonanywhere/A_LIRE.txt\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
