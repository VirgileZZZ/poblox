# poblox — hub de mini-jeux multijoueur

Un seul serveur Flask, un hub d'accueil façon « salle d'arcade », quatre jeux :

| Jeu | Principe |
|---|---|
| 🎨 **Griffonne !** | Type Skribbl : un joueur dessine un mot, les autres devinent dans le chat. |
| 🔗 **Enchaîne !** | À chaque tour, trouve un mot (vérifié au dictionnaire) qui **commence par les lettres tirées au sort**, interdit de rejouer un mot, et plus la partie dure, plus le début imposé est long (1 → 2 → 3 lettres). |
| 📡 **Longueur d'onde !** | Type Wavelength : un joueur voit une **cible cachée** sur un axe (ex. *un animal : effrayant ↔ adorable*) et donne **un seul indice** ; les autres placent leur aiguille sur le cadran. Au bon endroit 5 pts, juste à côté 3, un peu plus loin 1. |
| 🟢 **Glouton !** | Type agar.io, en temps réel : une **arène unique sans salon**, on mange les plus petits et on fuit les plus gros. Espace pour se diviser, W pour cracher de la masse, regroupement automatique après quelques secondes. Des **bots** complètent la population — certains pitoyables, d'autres capables de te dévorer. |

Depuis le hub : choisis ton pseudo, clique sur la carte du jeu pour **créer** un
salon, ou entre un **code à 4 lettres** pour **rejoindre** (le hub détecte tout
seul de quel jeu il s'agit).

## ⚡ Installation (Windows)

1. Installe [Python](https://www.python.org/downloads/) en cochant
   **« Add python.exe to PATH »** (une seule fois, si tu ne l'as pas déjà).
2. Télécharge ce dépôt (**Code → Download ZIP**, puis décompresse) ou
   `git clone https://github.com/VirgileZZZ/poblox.git`
3. Double-clique sur **`installation.bat`** : il crée un environnement isolé
   `.venv/` et y installe Flask. Une minute, une seule fois.
4. Ensuite, **`lancer.bat`** pour jouer.

Sur Linux / macOS :

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python flask_app.py     # puis http://localhost:5000
```

## 📦 Contenu

| Fichier | Rôle |
|---|---|
| `flask_app.py` | Backend Flask : hub, salons, les 3 jeux, scores |
| `words.py` | Dataset de 1270 mots en 5 langues (pour Griffonne) |
| `ondes.py` | Axes de Longueur d'onde : 235 écrits à la main + un assembleur thèmes × échelles (~2250 combinaisons) |
| `agar.py` | Moteur de l'arène Glouton : physique, bots, découpage de la vue (aucun import Flask) |
| `dicts/<lang>.txt` | Vrais lexiques (170k à 640k mots/langue, sans noms propres) pour valider Enchaîne |
| `users.db` | Créée automatiquement (SQLite) : comptes + sessions — jamais versionnée |
| `templates/index.html` | Toute l'interface : hub + les 3 jeux (HTML/CSS/JS) |
| `installation.bat` | Double-clic : crée `.venv/` et installe Flask (à faire une fois) |
| `lancer.bat` | Double-clic : démarre le serveur local et ouvre le navigateur |
| `partager.bat` + `tunnel.py` | Double-clic : serveur + tunnel Cloudflare → un lien https à envoyer |
| `.tools/` | `cloudflared` téléchargé à la première utilisation (ne pas uploader) |
| `preparer_upload.bat` + `preparer_upload.py` | Reconstruit `pythonanywhere/` : tout ce qu'il faut mettre en ligne, et rien d'autre |
| `pythonanywhere/` | Généré : `recre/` prêt à uploader, `recre.zip`, et `A_LIRE.txt` (les étapes) |
| `wsgi_pythonanywhere.py` | Modèle de fichier WSGI pour PythonAnywhere |
| `requirements.txt` | Dépendances (Flask uniquement) |

## 🧠 Comment marche le multijoueur (important)

PythonAnywhere **gratuit ne supporte pas les WebSockets**. Les deux jeux
utilisent donc du **polling HTTP** : chaque navigateur appelle
`GET /api/state` régulièrement avec des curseurs incrémentaux (`s` = traits,
`c` = chat, `w` = mots de la chaîne). Le serveur ne renvoie que les
nouveautés, donc les requêtes restent minuscules. La cible de Longueur d'onde
n'est envoyée qu'au maître du tour : impossible de la lire dans la réponse.

Tout l'état est en RAM (dictionnaire `ROOMS` + verrou). Pas de base de
données. Les machines à états avancent à chaque requête reçue via `_tick()` :
pas besoin de tâche de fond.

⚠️ Sur PythonAnywhere, garde **1 seul worker web** (défaut en gratuit) :
l'état étant en mémoire, plusieurs workers = plusieurs mondes parallèles.

## 🚀 Déploiement sur PythonAnywhere (pas à pas)

**Raccourci :** double-cliquer sur **`preparer_upload.bat`** — il fabrique le
dossier `pythonanywhere/` qui contient *exactement* ce qu'il faut mettre en
ligne (16 fichiers, 18 Mo), un `recre.zip` de 4 Mo pour tout envoyer d'un coup,
et un `A_LIRE.txt` avec les étapes. À relancer après chaque modification.

Détail complet :

1. Onglet **Files** : crée `/home/TON_USER/recre/`. Uploade `flask_app.py`,
   `words.py`, `ondes.py`, `requirements.txt`, le dossier `dicts/` (avec les 5 fichiers
   `fr.txt`…`it.txt`) et le dossier `templates/` (avec `index.html` dedans).
2. Onglet **Web** → *Add a new web app* → *Manual configuration* →
   Python 3.10 (ou plus récent).
3. Section *Code* : **Source code** = `/home/TON_USER/recre` et
   **Working directory** pareil.
4. Clique sur le lien du **WSGI configuration file**, efface tout et colle le
   contenu de `wsgi_pythonanywhere.py` (en remplaçant `TON_USER`).
5. (Flask est préinstallé, mais au besoin : **Consoles** → Bash →
   `pip3 install --user flask`.)
6. Bouton vert **Reload**. C'est en ligne sur
   `https://TON_USER.pythonanywhere.com` 🎉

Si tu mets à jour une installation existante de Griffonne : remplace
simplement `flask_app.py` et `templates/index.html`, puis **Reload**
(`words.py` n'a pas changé).

Test local : `python3 flask_app.py` puis http://localhost:5000 dans deux
onglets. Sous Windows, **`lancer.bat`** fait tout en double-clic
(`lancer.bat reseau` pour jouer aussi depuis le téléphone du wifi).

### 🔗 Jouer avec des amis sans rien déployer

**`partager.bat`** démarre le serveur *et* un tunnel Cloudflare, puis affiche
(et copie) un lien du type `https://xxxx.trycloudflare.com` : il s'envoie dans
un message, les amis l'ouvrent, ils arrivent sur le hub. Aucun compte, aucune
configuration ; le lien vit tant que la fenêtre reste ouverte et change à
chaque lancement. La première fois, `cloudflared` est récupéré dans `.tools/`
(~55 Mo). L'hôte, lui, joue sur http://localhost:5000.

> Pourquoi Cloudflare et pas localtunnel / localhost.run : leurs domaines
> (`*.loca.lt`, `*.lhr.life`) sont sur les listes noires de plusieurs
> antivirus, ce qui donne un tunnel « qui bugue » sans dire pourquoi.
> `*.trycloudflare.com` passe. À ne pas confondre avec **Cloudflare WARP**
> (le VPN) : c'est `cloudflared`, l'outil de tunnel, qui est utilisé ici.

## 🕹️ Règles & réglages

### 🎨 Griffonne !
- 2 à 10 joueurs. L'hôte règle dans le lobby : langue, mode
  (🌱/🔥/💀), tours (2-6), temps de dessin (45-120 s).
- Points devineur : `(100 + bonus de vitesse) × multiplicateur du mot`.
- Points dessinateur : `30 × bonnes réponses × multiplicateur`.
- Indices : lettres dévoilées à mi-temps puis au dernier quart.
- Outils : crayon, gomme, ligne, rectangle, cercle, pot de peinture,
  annuler, tout effacer, 14 couleurs, 3 épaisseurs.

### 🔗 Enchaîne !
- 2 à 10 joueurs, chacun son tour. À chaque tour, un **début de mot est tiré
  au sort** (seuls les débuts avec assez de mots possibles sont proposés).
- **Langue réglable** par l'hôte (🇫🇷 🇬🇧 🇪🇸 🇩🇪 🇮🇹) : tous les mots sont
  validés contre un **vrai dictionnaire** de 170k à 640k mots (fichiers `dicts/`).
  Les mots inventés ou mal orthographiés sont refusés.
- Ton mot doit **commencer par le début imposé** (affiché en tuiles jaunes) ;
  un nouveau tirage est fait pour le joueur suivant.
- **Interdit de rejouer un mot** déjà utilisé (comparaison insensible aux
  accents, majuscules et tirets : « Élo-ïse » = « eloise »).
- **Escalade** : tous les 8 mots, on passe au niveau supérieur — le début
  imposé passe à **2** lettres, puis **3** (annoncé dans le journal ⚡).
- Pas de mot avant la fin du chrono → **-1 ❤️** et un nouveau début est
  tiré pour relancer la partie. Plus de vies = éliminé 💀.
  Dernier survivant = 🏆.
- Points : `10 × niveau + 2 × longueur du mot + secondes restantes`.
- L'hôte règle : langue, temps par tour (10-45 s) et vies (1-5).
- Un **journal** (colonne de droite) relate les événements de la partie
  (nouveau mot, niveau, éliminations…). Pas de chat joueur : le mot se
  saisit dans la barre dédiée, pas dans une discussion. Celui qui rejoint
  en cours de partie est spectateur jusqu'à la manche suivante.

### 🟢 Glouton !
- **Pas de salon, pas de code** : le bouton du hub fait entrer directement dans
  l'arène commune. Jusqu'à 24 humains ; des **bots** maintiennent 11 joueurs en
  piste. Trois écoles de bots : ~40 % de tout nuls (ils errent et gobent sans
  regarder derrière eux), ~35 % de corrects, ~25 % de redoutables — ceux-là
  voient loin, fuient, chassent et **se divisent pour t'attraper**.
- **Espace** : chaque morceau assez gros (36 de masse) projette la moitié de
  lui-même, jusqu'à 8 morceaux. **W** : crache un peu de masse (à partir de 38).
- **Regroupement** : les morceaux refusionnent après `11 s + 0,018 × masse`,
  comme dans agar.io — d'où le risque de se diviser au mauvais moment.
- **Virus** (les ronds verts épineux) : avalés par une cellule assez grosse,
  ils la font éclater en plusieurs morceaux.
- Les grosses cellules **fondent** lentement, et on ralentit en grossissant :
  personne ne reste premier éternellement.
- Techniquement : le serveur est autoritaire, les clients l'interrogent ~9 fois
  par seconde (une requête = commandes + vue en retour), tout est interpolé et
  ses propres cellules sont **prédites** localement pour que la souris réponde
  tout de suite.

### 📡 Longueur d'onde !
- 2 à 10 joueurs. Chacun devient **maître** à tour de rôle ; l'hôte règle le
  **mode** et le nombre de **tours** (1-5).
- **📚 Axes préfaits** : le thème et les deux extrêmes sont tirés au sort
  parmi 235 axes écrits à la main plus ~2250 combinaisons assemblées à la volée (`ondes.py`), le maître n'a que l'indice à trouver.
  **✍️ Tout personnalisé** : le maître invente aussi le thème et les
  extrêmes (n'importe quelle langue, donc).
- La **cible** apparaît ensuite au maître seul, quelque part sur le cadran —
  le tirage est volontairement en U : un tour sur trois environ tombe tout
  au bord (gauche ou droite), c'est plus drôle à faire deviner qu'un milieu.
  Il donne **un indice** ; les autres font glisser leur aiguille et valident.
- Score : même endroit **5 pts**, une bande à côté **3**, deux bandes **1**,
  au-delà 0. Le maître empoche la **moyenne** de ce que son indice a
  rapporté — un bon indice profite d'abord à lui.
- Le tour se dévoile dès que tout le monde a répondu (ou au chrono) :
  cadran, aiguilles de chacun et points du tour. Classement cumulé à la fin.
- Un **chat** (colonne de droite) permet de discuter/râler pendant la partie.

## ⚙️ Réglages, thèmes et comptes

- Bouton ⚙ en haut à droite de l'accueil : **5 thèmes** (Clair, Sombre,
  Océan, Forêt, Sorbet) implémentés en variables CSS sur `<html data-theme>`.
  Le choix est gardé en `localStorage` (et sur le compte si connecté).
- **Comptes optionnels** (pseudo + mot de passe) : le compte retient le
  pseudo et le thème, et reconnecte automatiquement.
- Sécurité : mots de passe hachés (werkzeug `generate_password_hash`),
  session par cookie `httponly`/`SameSite=Lax` (+ `Secure` derrière HTTPS)
  dont le jeton n'est stocké qu'en SHA-256 dans `users.db` (SQLite),
  anti force brute simple (8 essais / 5 min / IP). Aucune donnée
  personnelle : juste pseudo, hash et thème.

## 💡 Idées d'évolutions

Thèmes imposés (animaux, villes…), mode équipe, sons, un 4ᵉ jeu sur le hub
(petit bac ? morpion géant ?), axes préfaits multilingues pour Longueur
d'onde, sauvegarde des scores dans un fichier JSON, lexiques plus riches
(mots rares acceptés).

---

## 🤖 Prompt réutilisable (si tu veux régénérer/faire évoluer le hub)

> Crée « poblox », un hub web de mini-jeux multijoueur en français, avec
> un backend **Flask (Python)** et un frontend **HTML/CSS/JS vanilla** (un
> seul template). Contrainte : hébergement sur **PythonAnywhere gratuit**,
> donc **pas de WebSockets** — synchronisation par **polling HTTP**
> (GET /api/state avec curseurs incrémentaux), état 100 % **en mémoire**
> (`threading.Lock`), sans base de données ni tâche de fond (la machine à
> états avance à chaque requête). Salons à code de 4 lettres partagés entre
> les jeux : le hub détecte le jeu d'un salon quand on le rejoint.
>
> Jeu 1 « Griffonne ! » : type Skribbl.io — un dessinateur choisit 1 mot
> parmi 3 (avec difficultés ★ à ★★★★ et multiplicateurs), dessine sur un
> canvas (outils, formes, remplissage, undo, coordonnées normalisées 0-1,
> tactile), les autres devinent dans le chat (tolérance aux fautes de
> frappe « tu chauffes », anti-triche, indices à mi-temps), podium final.
>
> Jeu 2 « Enchaîne ! » : jeu de mots au tour par tour — à chaque tour un
> début de mot est tiré au sort, **langue réglable** (fr/en/es/de/it) avec
> **validation contre un vrai dictionnaire** (170k à 640k mots/langue) qui refuse
> les mots inventés ou mal orthographiés, chaque mot doit commencer par les
> lettres imposées, mots à usage unique (comparaison sans
> accents/majuscules/tirets), **escalade** tous les 8 mots (début imposé de
> 2 puis 3 lettres, tiré parmi les débuts ayant assez de mots possibles),
> chrono par tour réglable, 1 à 5 vies, -1 ❤️ si le temps expire
> (et nouveau tirage pour relancer), élimination, dernier survivant
> vainqueur, points = 10×niveau + 2×longueur + secondes restantes, joueurs
> en retard spectateurs, **journal** de partie en colonne (pas de chat
> joueur : la saisie des mots est séparée).
>
> Gérer pour les deux : transfert d'hôte, purge des inactifs, départ du
> joueur actif, reconnexion après rechargement (sessionStorage), responsive
> mobile. Direction artistique commune « atelier la nuit » : fond encre bleu
> nuit avec taches de couleur, panneaux blancs « autocollant papier » aux
> bords irréguliers et ombre franche, titres manuscrits (Gochi Hand) + corps
> Nunito, accents crayon (jaune #ffc53d, corail #ff6b6b, turquoise #2ec4b6),
> cartes de jeu « affiches punaisées » sur le hub, débuts de mots imposés
> affichés en tuiles de lettres.
