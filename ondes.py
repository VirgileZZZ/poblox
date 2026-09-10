# -*- coding: utf-8 -*-
"""
Longueur d'onde — axes de jeu prêts à l'emploi (mode « préfait »).

Chaque entrée : (thème, extrémité gauche, extrémité droite).
L'aiguille cachée tombe quelque part entre les deux ; le maître du tour
donne un indice qui se situe au bon endroit sur cet axe.

Contenu en français : l'interface du jeu l'est aussi, et le mode
« personnalisé » permet de jouer dans n'importe quelle langue.
"""

import random

WAVE_PAIRS = [
    # ---------------------------------------------------------- sensations
    ("Température", "Glacé", "Brûlant"),
    ("Le bruit", "Silencieux", "Assourdissant"),
    ("La lumière", "Sombre", "Éblouissant"),
    ("Une odeur", "Pestilentiel", "Enivrant"),
    ("Le toucher", "Rugueux", "Doux"),
    ("La vitesse", "Immobile", "Fulgurant"),
    ("Le poids", "Plume", "Enclume"),
    ("La taille", "Minuscule", "Gigantesque"),
    ("Le confort", "Torture", "Cocon"),
    ("La propreté", "Crasseux", "Immaculé"),

    # ---------------------------------------------------------- nourriture
    ("Un plat", "Immangeable", "Délicieux"),
    ("Le goût", "Salé", "Sucré"),
    ("Un repas", "Léger", "Bourratif"),
    ("Un aliment", "Diététique", "Régressif"),
    ("Une boisson", "Désaltérante", "Écœurante"),
    ("Un fruit", "Acide", "Sucré"),
    ("Un plat", "Fade", "Épicé"),
    ("La cuisine", "Fait maison", "Industriel"),
    ("Un petit-déjeuner", "Salé", "Sucré"),
    ("Un dessert", "Raisonnable", "Indécent"),

    # ---------------------------------------------------------- objets
    ("Un objet", "Inutile", "Indispensable"),
    ("Un objet", "Bon marché", "Hors de prix"),
    ("Une invention", "Ratée", "Géniale"),
    ("Un meuble", "Pratique", "Décoratif"),
    ("Un vêtement", "Confortable", "Élégant"),
    ("Un cadeau", "Décevant", "Inoubliable"),
    ("Une machine", "Simple", "Compliquée"),
    ("Un objet", "Fragile", "Incassable"),
    ("Un souvenir de vacances", "Kitsch", "Raffiné"),
    ("Un objet du quotidien", "Démodé", "Moderne"),

    # ---------------------------------------------------------- animaux
    ("Un animal", "Effrayant", "Adorable"),
    ("Un animal", "Domestique", "Sauvage"),
    ("Un animal", "Lent", "Rapide"),
    ("Un animal", "Discret", "Bruyant"),
    ("Un animal", "Inoffensif", "Mortel"),
    ("Un animal de compagnie", "Peu exigeant", "Épuisant"),
    ("Un insecte", "Fascinant", "Répugnant"),

    # ---------------------------------------------------------- personnes
    ("Un métier", "Ingrat", "Prestigieux"),
    ("Un métier", "Tranquille", "Stressant"),
    ("Une personne", "Timide", "Extravertie"),
    ("Un talent", "Banal", "Rare"),
    ("Un comportement", "Poli", "Grossier"),
    ("Une célébrité", "Oubliée", "Incontournable"),
    ("Un prénom", "Rare", "Répandu"),
    ("Un personnage", "Gentil", "Méchant"),
    ("Un héros", "Ordinaire", "Légendaire"),
    ("Un professeur", "Laxiste", "Tyrannique"),

    # ---------------------------------------------------------- culture
    ("Un film", "Navet", "Chef-d'œuvre"),
    ("Un film", "Pour enfants", "Pour adultes"),
    ("Une chanson", "Agaçante", "Entêtante"),
    ("Un livre", "Illisible", "Passionnant"),
    ("Un jeu", "Basé sur la chance", "Basé sur la stratégie"),
    ("Un dessin animé", "Pour les petits", "Pour les grands"),
    ("Une série", "À oublier", "À binge-watcher"),
    ("Un style de musique", "Calme", "Déchaîné"),
    ("Une œuvre d'art", "Incompréhensible", "Évidente"),
    ("Un spectacle", "Ennuyeux", "Époustouflant"),

    # ---------------------------------------------------------- société
    ("Une activité", "Barbante", "Palpitante"),
    ("Une activité", "Solitaire", "Collective"),
    ("Un endroit", "Glauque", "Paradisiaque"),
    ("Une ville", "Endormie", "Trépidante"),
    ("Un pays", "Méconnu", "Célèbre"),
    ("Une fête", "Intime", "Démesurée"),
    ("Un moyen de transport", "Écologique", "Polluant"),
    ("Un moyen de transport", "Lent", "Rapide"),
    ("Une règle", "Facultative", "Sacrée"),
    ("Un métier d'avenir", "Condamné", "Prometteur"),

    # ---------------------------------------------------------- sport
    ("Un sport", "Reposant", "Épuisant"),
    ("Un sport", "Individuel", "Collectif"),
    ("Un sport", "Sans risque", "Dangereux"),
    ("Un sport", "Confidentiel", "Populaire"),
    ("Un exercice", "Facile", "Impossible"),

    # ---------------------------------------------------------- école
    ("Une matière", "Inutile", "Essentielle"),
    ("Une matière", "Facile", "Cauchemardesque"),
    ("Un devoir", "Rapide", "Interminable"),
    ("Une excuse", "Pas crédible", "Imparable"),
    ("Une punition", "Symbolique", "Traumatisante"),

    # ---------------------------------------------------------- technologie
    ("Une technologie", "Dépassée", "Futuriste"),
    ("Une application", "Chronophage", "Utile"),
    ("Un mot de passe", "Ridicule", "Inviolable"),
    ("Un robot", "Rassurant", "Inquiétant"),
    ("Un site web", "Illisible", "Impeccable"),

    # ---------------------------------------------------------- abstrait
    ("Une idée", "Terrible", "Brillante"),
    ("Un mensonge", "Innocent", "Impardonnable"),
    ("Un secret", "Anodin", "Explosif"),
    ("Une peur", "Rationnelle", "Irrationnelle"),
    ("Un risque", "Négligeable", "Insensé"),
    ("Une décision", "Réversible", "Définitive"),
    ("Une émotion", "Agréable", "Insupportable"),
    ("Un défaut", "Charmant", "Rédhibitoire"),
    ("Un super-pouvoir", "Décevant", "Surpuissant"),
    ("Un rêve", "Réalisable", "Utopique"),
    ("Une tradition", "Ringarde", "Précieuse"),
    ("Un conseil", "Évident", "Éclairant"),
    ("Une question", "Simple", "Insoluble"),
    ("Un souvenir", "Flou", "Gravé à jamais"),
    ("Le temps qui passe", "Éphémère", "Éternel"),

    # ---------------------------------------------------------- quotidien
    ("Une corvée", "Supportable", "Détestable"),
    ("Le réveil", "Aux aurores", "En pleine journée"),
    ("Un weekend", "Sous la couette", "Debout à 6 h"),
    ("Une soirée", "Pyjama-canapé", "Jusqu'au petit matin"),
    ("Un bruit du quotidien", "Apaisant", "Insupportable"),
    ("Un achat", "Coup de tête", "Longuement réfléchi"),
    ("Un rangement", "Chaos total", "Rangé au millimètre"),
    ("Une file d'attente", "Deux minutes", "Une éternité"),
    ("Un trajet", "Du plaisir", "Un calvaire"),
    ("Un message non lu", "Sans importance", "Urgence absolue"),
]

# ═══════════════════════════════════════════════════════════════════════
# Rallonge : culture pop, loisirs, sucreries… et une section « ça va
# gueuler à table ». Les axes polémiques restent des ÉCHELLES D'OPINION,
# jamais un jugement sur quelqu'un de nommé : c'est le joueur qui choisit
# le nom qu'il met dessus, et c'est tout l'intérêt de la dispute.
# ═══════════════════════════════════════════════════════════════════════

WAVE_PAIRS += [
    # ------------------------------------------------- polémique / politique
    ("Un ou une politique", "Nuisible", "Providentiel"),
    ("Un chef d'État", "Catastrophique", "Exemplaire"),
    ("Une décision politique", "Scandaleuse", "Courageuse"),
    ("Un discours", "Langue de bois", "Vérité crue"),
    ("Une loi", "Absurde", "Indispensable"),
    ("Un scandale", "Vite oublié", "Historique"),
    ("Une manifestation", "Inutile", "Nécessaire"),
    ("Un impôt", "Symbolique", "Du racket"),
    ("Un sujet de débat", "Consensuel", "Explosif"),
    ("Une opinion", "Banale", "Indéfendable"),
    ("Un média", "Douteux", "Digne de confiance"),
    ("Une théorie", "Farfelue", "Crédible"),
    ("Un milliardaire", "Un fléau", "Un bienfaiteur"),
    ("Un régime politique", "Autoritaire", "Libertaire"),
    ("Une peine de justice", "Trop clémente", "Trop sévère"),
    ("Une promesse électorale", "Fantaisiste", "Crédible"),
    ("Une réforme", "Cosmétique", "Radicale"),
    ("Une cause", "Perdue d'avance", "Déjà gagnée"),
    ("Une tradition", "À abolir", "À protéger"),
    ("Un métier", "Sous-payé", "Trop payé"),
    ("Un sujet à éviter en famille", "Sans risque", "Dispute assurée"),
    ("Une célébrité", "Détestée", "Adorée"),
    ("Un pays", "Où je n'irais jamais", "Où je vivrais demain"),

    # ------------------------------------------------- anime & manga
    ("Un anime", "Pour débuter", "Pour initiés"),
    ("Un anime", "Tranquille", "Ultra-violent"),
    ("Un anime", "Confidentiel", "Phénomène mondial"),
    ("Un personnage d'anime", "Insupportable", "Iconique"),
    ("Un shonen", "Cliché", "Original"),
    ("Une fin d'anime", "Bâclée", "Parfaite"),
    ("Un générique d'anime", "Passe-partout", "Légendaire"),
    ("Un manga", "Vite lu", "Interminable"),
    ("Un personnage", "Trop faible", "Trop puissant"),
    ("Un méchant", "Ridicule", "Terrifiant"),
    ("Un arc narratif", "À sauter", "Culte"),
    ("Un doublage français", "Catastrophique", "Excellent"),

    # ------------------------------------------------- séries
    ("Une série", "À abandonner", "À dévorer"),
    ("Une saison", "Celle de trop", "La meilleure"),
    ("Une fin de série", "Une trahison", "Un chef-d'œuvre"),
    ("Une série", "Doudou réconfortant", "Éprouvante"),
    ("Un épisode", "Du remplissage", "Un événement"),
    ("Une série", "Pour ados", "Pour vieux"),
    ("Un personnage de série", "Qu'on veut voir mourir", "Qu'on protège"),
    ("Une série", "Annulée trop tôt", "Qui s'éternise"),

    # ------------------------------------------------- cinéma
    ("Un film", "À voir seul", "À voir en bande"),
    ("Un film", "Cerveau éteint", "Faut s'accrocher"),
    ("Une suite", "Inutile", "Meilleure que l'original"),
    ("Un film d'horreur", "Rigolo", "Traumatisant"),
    ("Une adaptation", "Trahison du livre", "Fidèle"),
    ("Un acteur", "Toujours le même rôle", "Caméléon"),
    ("Une bande-annonce", "Mensongère", "Honnête"),
    ("Un film culte", "Surcoté", "Mérité"),
    ("Un film de Noël", "Insupportable", "Obligatoire"),

    # ------------------------------------------------- jeux vidéo
    ("Un jeu vidéo", "Détente", "Manette par la fenêtre"),
    ("Un jeu", "Fini en deux heures", "Mille heures"),
    ("Un boss", "Une formalité", "Un cauchemar"),
    ("Un jeu", "Payer pour gagner", "Cent pour cent au mérite"),
    ("Un remaster", "Inutile", "Indispensable"),
    ("Une communauté de joueurs", "Accueillante", "Toxique"),

    # ------------------------------------------------- hobbies & activités
    ("Un loisir", "Bon marché", "Ruineux"),
    ("Un hobby", "On s'y met en 5 minutes", "Une vie pour le maîtriser"),
    ("Une activité", "On reste propre", "On finit plein de boue"),
    ("Un loisir", "Grand public", "De niche"),
    ("Un passe-temps", "Productif", "Pure perte de temps"),
    ("Une soirée jeux", "Conviviale", "Fin d'amitié"),
    ("Un instrument de musique", "Gratifiant vite", "Ingrat"),
    ("Un bricolage maison", "Réussi du premier coup", "Désastre assuré"),
    ("Une activité de vacances", "Farniente", "Réveil à 6 h"),
    ("Une sortie", "Entre amis", "En famille"),
    ("Un club", "Ouvert à tous", "Très fermé"),

    # ------------------------------------------------- bonbons & sucreries
    ("Un bonbon", "Fade", "Explosif en bouche"),
    ("Un bonbon", "Pour les enfants", "Pour les nostalgiques"),
    ("Un bonbon", "Acide", "Sucré"),
    ("Une sucrerie", "On en reprend", "Écœurante"),
    ("Un chocolat", "Bas de gamme", "Grand cru"),
    ("Un goûter", "Raisonnable", "Overdose de sucre"),
    ("Un gâteau industriel", "Honteux", "Assumé"),
    ("Une glace", "Parfum sage", "Parfum improbable"),

    # ------------------------------------------------- table & polémique
    ("Une recette", "Sacrilège", "Dans les règles de l'art"),
    ("Un aliment", "Détesté de tous", "Aimé de tous"),
    ("Une pizza", "Classique", "Hérésie"),
    ("Un fromage", "Discret", "Sent depuis le couloir"),
    ("Un restaurant", "Cantine", "Étoilé"),

    # ------------------------------------------------- internet & réseaux
    ("Un réseau social", "Sain", "Toxique"),
    ("Un influenceur", "Utile", "Nuisible"),
    ("Un mème", "Mort et enterré", "Éternel"),
    ("Un mot d'internet", "Démodé", "En vogue"),
    ("Un commentaire", "Constructif", "Haineux"),
    ("Une story", "Banale", "Beaucoup trop d'infos"),
    ("Un pseudo", "Sobre", "Honteux"),

    # ------------------------------------------------- entre nous
    ("Un comportement en public", "Normal", "Gênant"),
    ("Un retard", "Pardonnable", "Impardonnable"),
    ("Un message vocal", "Acceptable", "Une agression"),
    ("Une blague", "Fine", "Très lourde"),
    ("Un surnom", "Affectueux", "Vexant"),
    ("Un compliment", "Sincère", "Hypocrite"),
    ("Un service qu'on demande", "Rien du tout", "Un vrai sacrifice"),
    ("Un secret d'ami", "À garder", "À balancer tout de suite"),

    # ------------------------------------------------- style & choix de vie
    ("Une tenue", "Passe-partout", "Remarquée de loin"),
    ("Un tatouage", "Discret", "Impossible à cacher"),
    ("Une coupe de cheveux", "Classique", "Audacieuse"),
    ("Un animal de compagnie", "Raisonnable", "Complètement insensé"),
    ("Un achat", "Utile", "Caprice total"),
    ("Une application", "Indispensable", "À désinstaller"),
    ("Une décoration", "Sobre", "Kitsch assumé"),

    # ------------------------------------------------- boulot & études
    ("Un collègue", "Trop discret", "Envahissant"),
    ("Une réunion", "Utile", "Un mail aurait suffi"),
    ("Un chef", "Aux abonnés absents", "Sur ton dos"),
    ("Un job d'été", "Sympa", "Traumatisant"),
    ("Une formation", "Du vent", "Change une vie"),

    # ------------------------------------------------- musique
    ("Une chanson", "Plaisir coupable", "Fièrement assumée"),
    ("Un artiste", "Sous-coté", "Surcoté"),
    ("Un concert", "Intimiste", "Stade entier"),
    ("Un genre musical", "Grand public", "Underground"),
    ("Une reprise", "Massacre", "Mieux que l'originale"),

    # ------------------------------------------------- voyages
    ("Une destination", "Piège à touristes", "Hors des sentiers battus"),
    ("Un hébergement", "Spartiate", "Palace"),
    ("Un voyage", "Organisé au millimètre", "Totalement improvisé"),
    ("Un souvenir de voyage", "Anecdote", "Histoire à raconter à vie"),

    # ------------------------------------------------- sciences & futur
    ("Une intelligence artificielle", "Gadget", "Change tout"),
    ("Le futur", "Radieux", "Dystopique"),
    ("Une découverte", "Anecdotique", "Révolutionnaire"),
    ("Une prédiction", "Certaine", "Impossible à tenir"),
    ("Une invention du quotidien", "Qu'on oublie", "Qui a tout changé"),

    # ------------------------------------------------- sport (suite)
    ("Un sportif", "Sous-coté", "Légende absolue"),
    ("Une équipe", "Détestée", "Adorée"),
    ("Une règle du jeu", "Logique", "Absurde"),
    ("Un supporter", "Tranquille", "Ingérable"),
    ("Un sport extrême", "Sensations fortes", "Suicidaire"),
]


# ═══════════════════════════════════════════════════════════════════════
# AXES ASSEMBLÉS À LA VOLÉE
#
# La liste ci-dessus est écrite à la main : elle est bonne, mais finie —
# au bout de quelques soirées, on retombe sur les mêmes. Ici on garde deux
# réservoirs séparés, des THÈMES et des ÉCHELLES, et on les combine au
# tirage : des milliers d'axes possibles au lieu d'un catalogue figé.
#
# Pour que ça ne sorte pas n'importe quoi (« Un bonbon : autoritaire ↔
# libertaire »), chaque thème porte des étiquettes et chaque échelle dit à
# quelles étiquettes elle s'applique ; « tout » = valable partout.
#
# Accord en genre : quand un pôle change au féminin, on écrit les DEUX
# formes complètes séparées par « / » — « Nul/Nulle », « Très collectif/
# Très collective ». Le genre est déduit de l'article du thème.
# ═══════════════════════════════════════════════════════════════════════

WAVE_THEMES = [
    # ---------------------------------------------------------- objets
    ("Un objet du quotidien", {"objet"}),
    ("Un meuble", {"objet"}),
    ("Un vêtement", {"objet"}),
    ("Un cadeau", {"objet"}),
    ("Un outil", {"objet"}),
    ("Un gadget", {"objet"}),
    ("Un jouet", {"objet"}),
    ("Une voiture", {"objet"}),
    ("Un téléphone", {"objet"}),
    ("Une paire de chaussures", {"objet"}),
    ("Un souvenir de vacances", {"objet"}),
    ("Une décoration", {"objet"}),
    ("Un sac", {"objet"}),
    ("Un meuble en kit", {"objet"}),
    # ------------------------------------------------------ nourriture
    ("Un plat", {"bouffe"}),
    ("Un dessert", {"bouffe"}),
    ("Une boisson", {"bouffe"}),
    ("Un fruit", {"bouffe"}),
    ("Un légume", {"bouffe"}),
    ("Un fromage", {"bouffe"}),
    ("Un bonbon", {"bouffe"}),
    ("Un gâteau", {"bouffe"}),
    ("Une pizza", {"bouffe"}),
    ("Une sauce", {"bouffe"}),
    ("Un petit-déjeuner", {"bouffe", "moment"}),
    ("Un plat de cantine", {"bouffe"}),
    # ----------------------------------------------------------- êtres
    ("Un animal", {"etre"}),
    ("Un insecte", {"etre"}),
    ("Un animal de compagnie", {"etre"}),
    ("Une personne célèbre", {"etre"}),
    ("Un personnage de fiction", {"etre", "oeuvre"}),
    ("Un super-héros", {"etre", "oeuvre"}),
    ("Un méchant de film", {"etre", "oeuvre"}),
    ("Un professeur", {"etre"}),
    ("Un voisin", {"etre"}),
    ("Un collègue", {"etre"}),
    ("Un sportif", {"etre"}),
    ("Une équipe", {"etre"}),
    # ---------------------------------------------------------- œuvres
    ("Un film", {"oeuvre"}),
    ("Une série", {"oeuvre"}),
    ("Un livre", {"oeuvre"}),
    ("Une chanson", {"oeuvre"}),
    ("Un jeu vidéo", {"oeuvre", "activite"}),
    ("Un anime", {"oeuvre"}),
    ("Un dessin animé", {"oeuvre"}),
    ("Une émission de télé", {"oeuvre"}),
    ("Un manga", {"oeuvre"}),
    ("Une application", {"oeuvre", "objet"}),
    ("Un album de musique", {"oeuvre"}),
    # -------------------------------------------------------- activités
    ("Un sport", {"activite"}),
    ("Un loisir", {"activite"}),
    ("Un métier", {"activite"}),
    ("Une matière scolaire", {"activite"}),
    ("Une corvée", {"activite"}),
    ("Un jeu de société", {"activite", "oeuvre"}),
    ("Une soirée", {"activite", "moment"}),
    ("Un voyage", {"activite", "moment"}),
    ("Une fête", {"activite", "moment"}),
    ("Un examen", {"activite", "moment"}),
    ("Un entraînement", {"activite"}),
    # ------------------------------------------------------------ lieux
    ("Un pays", {"lieu"}),
    ("Une ville", {"lieu"}),
    ("Un restaurant", {"lieu"}),
    ("Un magasin", {"lieu"}),
    ("Un musée", {"lieu"}),
    ("Une chambre d'hôtel", {"lieu"}),
    ("Un quartier", {"lieu"}),
    ("Une salle de classe", {"lieu"}),
    # ------------------------------------------------------------ idées
    ("Une loi", {"idee"}),
    ("Une règle", {"idee"}),
    ("Une décision", {"idee"}),
    ("Une opinion", {"idee"}),
    ("Un conseil", {"idee"}),
    ("Une théorie", {"idee"}),
    ("Une excuse", {"idee"}),
    ("Une promesse", {"idee"}),
    ("Un mensonge", {"idee"}),
    ("Un secret", {"idee"}),
    ("Une tradition", {"idee"}),
    ("Un rêve", {"idee"}),
    ("Une insulte", {"idee"}),
    # ---------------------------------------------------------- moments
    ("Un souvenir", {"moment"}),
    ("Un rendez-vous", {"moment"}),
    ("Une rencontre", {"moment"}),
    ("Un anniversaire", {"moment"}),
    ("Un lundi matin", {"moment"}),
    ("Une réunion", {"moment", "activite"}),
    ("Un trajet", {"moment", "activite"}),
    ("Une dispute", {"moment"}),
]

WAVE_SCALES = [
    # ------------------------------------------------- valables partout
    ("Nul/Nulle", "Génial/Géniale", {"tout"}),
    ("Banal/Banale", "Inoubliable", {"tout"}),
    ("Surcoté/Surcotée", "Sous-coté/Sous-cotée", {"tout"}),
    ("Détesté/Détestée", "Adoré/Adorée", {"tout"}),
    ("Sans intérêt", "Fascinant/Fascinante", {"tout"}),
    ("Ringard/Ringarde", "Dans l'air du temps", {"tout"}),
    ("Ordinaire", "Exceptionnel/Exceptionnelle", {"tout"}),
    ("Rassurant/Rassurante", "Inquiétant/Inquiétante", {"tout"}),
    ("Confidentiel/Confidentielle", "Célèbre", {"tout"}),
    ("Démodé/Démodée", "Très moderne", {"tout"}),
    ("Simple", "Compliqué/Compliquée", {"tout"}),
    ("Discret/Discrète", "Voyant/Voyante", {"tout"}),
    ("Qu'on oublie", "Qu'on raconte à vie", {"tout"}),
    ("Ridicule", "Impressionnant/Impressionnante", {"tout"}),
    ("Pour tout le monde", "Pour une poignée d'initiés", {"tout"}),
    # ---------------------------------------------------------- objets
    ("Bon marché", "Hors de prix", {"objet"}),
    ("Inutile", "Indispensable", {"objet"}),
    ("Moche", "Superbe", {"objet"}),
    ("Encombrant/Encombrante", "Tient dans la poche", {"objet"}),
    ("Fragile", "Increvable", {"objet"}),
    ("Bas de gamme", "Grand luxe", {"objet"}),
    ("Bricolé/Bricolée", "Impeccable", {"objet"}),
    # ------------------------------------------------------ nourriture
    ("Fade", "Explosif en bouche/Explosive en bouche", {"bouffe"}),
    ("Immangeable", "Délicieux/Délicieuse", {"bouffe"}),
    ("Léger/Légère", "Bourratif/Bourrative", {"bouffe"}),
    ("Salé/Salée", "Sucré/Sucrée", {"bouffe"}),
    ("Acide", "Doux/Douce", {"bouffe"}),
    ("Diététique", "Régressif/Régressive", {"bouffe"}),
    ("Écœurant/Écœurante", "On en reprend", {"bouffe"}),
    ("Glacé/Glacée", "Brûlant/Brûlante", {"bouffe"}),
    # ----------------------------------------------------------- êtres
    ("Timide", "Extraverti/Extravertie", {"etre"}),
    ("Inoffensif/Inoffensive", "Redoutable", {"etre"}),
    ("Insupportable", "Attachant/Attachante", {"etre"}),
    ("Lent/Lente", "Rapide", {"etre"}),
    ("Gentil/Gentille", "Méchant/Méchante", {"etre"}),
    ("Sous-estimé/Sous-estimée", "Légendaire", {"etre"}),
    ("Fainéant/Fainéante", "Increvable", {"etre"}),
    # ---------------------------------------------------------- œuvres
    ("Navet", "Chef-d'œuvre", {"oeuvre"}),
    ("Pour les petits", "Pour les grands", {"oeuvre"}),
    ("Cerveau éteint", "Faut s'accrocher", {"oeuvre"}),
    ("Vite oublié/Vite oubliée", "Culte", {"oeuvre"}),
    ("Court/Courte", "Interminable", {"oeuvre"}),
    ("Cliché", "Original/Originale", {"oeuvre"}),
    ("Réconfortant/Réconfortante", "Éprouvant/Éprouvante", {"oeuvre"}),
    ("Phénomène mondial", "Que personne n'a vu", {"oeuvre"}),
    # -------------------------------------------------------- activités
    ("Reposant/Reposante", "Épuisant/Épuisante", {"activite"}),
    ("Solitaire", "Très collectif/Très collective", {"activite"}),
    ("Sans risque", "Dangereux/Dangereuse", {"activite"}),
    ("Gratuit/Gratuite", "Ruineux/Ruineuse", {"activite"}),
    ("Barbant/Barbante", "Palpitant/Palpitante", {"activite"}),
    ("On reste propre", "On finit plein de boue", {"activite"}),
    ("On s'y met en 5 minutes", "Une vie pour maîtriser", {"activite"}),
    # ------------------------------------------------------------ lieux
    ("Glauque", "Paradisiaque", {"lieu"}),
    ("Désert/Déserte", "Bondé/Bondée", {"lieu"}),
    ("Piège à touristes", "Hors des sentiers battus", {"lieu"}),
    ("Endormi/Endormie", "Trépidant/Trépidante", {"lieu"}),
    ("Spartiate", "Palace", {"lieu"}),
    ("Sinistre", "Chaleureux/Chaleureuse", {"lieu"}),
    # ------------------------------------------------------------ idées
    ("Absurde", "Imparable", {"idee"}),
    ("Anodin/Anodine", "Explosif/Explosive", {"idee"}),
    ("Consensuel/Consensuelle", "Clivant/Clivante", {"idee"}),
    ("Farfelu/Farfelue", "Crédible", {"idee"}),
    ("Réversible", "Définitif/Définitive", {"idee"}),
    ("Évident/Évidente", "Éclairant/Éclairante", {"idee"}),
    ("Innocent/Innocente", "Impardonnable", {"idee"}),
    ("Cosmétique", "Radical/Radicale", {"idee"}),
    # ---------------------------------------------------------- moments
    ("Interminable", "Passé en un éclair/Passée en un éclair", {"moment"}),
    ("Confortable", "Très gênant/Très gênante", {"moment"}),
    ("Anodin/Anodine", "Traumatisant/Traumatisante", {"moment"}),
    ("Improvisé/Improvisée", "Réglé au millimètre/Réglée au millimètre",
     {"moment"}),
    ("Qu'on veut oublier", "Qu'on garde pour toujours", {"moment"}),
    # --------------------------------------------------- à cheval sur 2
    ("Kitsch", "Raffiné/Raffinée", {"objet", "lieu", "oeuvre"}),
    ("Écologique", "Polluant/Polluante", {"objet", "activite", "lieu"}),
    ("Sain/Saine", "Toxique", {"bouffe", "etre", "activite", "idee"}),
    ("Silencieux/Silencieuse", "Assourdissant/Assourdissante",
     {"lieu", "objet", "etre"}),
    ("Pour les nostalgiques", "Tout neuf/Toute neuve",
     {"objet", "oeuvre", "bouffe"}),
]


def _forme(pole, feminin):
    """« Nul/Nulle » -> la forme qui va avec le genre du thème."""
    if "/" not in pole:
        return pole
    masculin, feminine = pole.split("/", 1)
    return feminine if feminin else masculin


def echelles_pour(tags):
    return [s for s in WAVE_SCALES if "tout" in s[2] or (s[2] & tags)]


def axe_genere(rng=random):
    """Un axe (thème, extrême gauche, extrême droite) assemblé au tirage."""
    theme, tags = rng.choice(WAVE_THEMES)
    feminin = theme.startswith(("Une ", "La "))
    gauche, droite, _ = rng.choice(echelles_pour(tags))
    return (theme, _forme(gauche, feminin), _forme(droite, feminin))


# nombre d'axes différents que la combinaison peut produire
NB_COMBINAISONS = sum(len(echelles_pour(tags)) for _, tags in WAVE_THEMES)
