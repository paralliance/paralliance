"""Lot 3 : clubs repérés dans le Répertoire national des associations (RNA), relus un par un.

Source : ministère de l'Intérieur, « Répertoire national des associations », fichier rna_waldec_20261001
(données au 1er octobre 2026), publié sur data.gouv.fr sous Licence Ouverte : réutilisation libre en citant
la source et la date. Chaque association y déclare elle-même son objet.

1. Candidats : associations actives dont le dernier dossier déposé en préfecture date de moins de 3 ans
   (depuis le 8 novembre 2023) et dont l'objet parle de sport et de handicap (ou classées « handisport »).
2. Écartés d'office : comités, ligues, fédérations, établissements (IME, ESAT, écoles…), associations de soutien
   ou de sport-santé, et clubs déjà sur Paralliance.
3. Relecture une par une des fiches restantes : décision et raison dans rna_relecture.json. Seules les fiches
   relues et retenues sont importées.
4. Fiche : nom, commune et code postal du siège, centre de la commune pour la carte, sports, handicaps et pratique
   tirés de l'objet déclaré (à défaut, du code d'activité), extrait de l'objet. Site : seulement ceux de la liste
   « sites » de rna_relecture.json, contrôlés le 8 novembre 2026 avec verifier_site() (réponse en https, pas de
   contenu suspect, page qui parle bien du club).
   Ni adresse, ni dirigeant, ni téléphone, ni mail : le RNA ne publie pas ces informations.
   Les collectivités d'outre-mer (Saint-Barthélemy, Nouvelle-Calédonie…) sont mises de côté : le site ne gère que
   les départements.

Utilisation (dans le dossier supabase) :
  python import_rna.py rna_waldec_20261001.zip           (télécharge les communes sur geo.api.gouv.fr)
  python import_rna.py rna_waldec_20261001.zip dossier    (communes.json et arrondissements.json déjà téléchargés)
  -> 17_import_rna_1.sql, 17_import_rna_2.sql…  (un fichier par tranche de 500 clubs, à coller dans l'ordre)
"""
import csv
import io
import json
import os
import re
import ssl
import sys
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from difflib import SequenceMatcher

from csv_vers_sql import requete

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCE = "Répertoire national des associations (ministère de l'Intérieur), octobre 2026, Licence Ouverte"
DEPUIS = "2023-11-08"                     # règle des 3 ans : dernier dossier déposé depuis cette date
PAR_FICHIER = 500
COLLECTIVITES = ("975", "977", "978", "984", "986", "987", "988", "989")
GEO = "https://geo.api.gouv.fr/communes?fields=nom,code,centre,codesPostaux,codeDepartement&format=json"
SUPABASE = "https://aogcjrfrfdasxesntlpk.supabase.co/rest/v1/clubs"
CLE = "sb_publishable_ZNohzowK1cNBG_-qukzemQ_KAG9EX-Z"     # clé publique (lecture des clubs publiés)
csv.field_size_limit(10 ** 7)


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower().replace("’", "'").replace("œ", "oe")
    return re.sub(r"\s+", " ", s)


# ---------- 1-2. Candidats (même tri que pour la relecture) ----------
HANDI = re.compile(r"handi|sport adapte|sports adaptes|activites? physiques? (?:et sportives? )?adaptees?|aps ?a\b|en situation de handicap|"
                   r"deficien|malvoyant|mal-voyant|non[- ]voyant|aveugle|\bsourds?\b|malentendant|surdi|fauteuil|cecifoot|torball|goalball|"
                   r"boccia|paralymp|parasport|para-sport|para sport|trisomi|autis|paraplegi|tetraplegi|amput|myopath|polyhandi|"
                   r"\bimc\b|infirmes? moteurs?|mobilite reduite|deficience|psychique|mental")
SPORT = re.compile(r"sport|club|athle|basket|foot|tennis|natation|nage|judo|gym|danse|escalade|voile|kayak|canoe|aviron|rugby|hand ?ball|"
                   r"volley|\btir\b|escrime|badminton|ping|equitation|equestre|cyclis|velo|tandem|randonn|petanque|boule|karate|boxe|plong|"
                   r"\bski\b|golf|marche|surf|roller|hockey|bowling|billard|echecs|aikido|taekwondo|lutte|musculation|halterophil|triathlon|"
                   r"course|trail|cecifoot|torball|goalball|boccia|baskin|sarbacane|quilles|petanque|nautique|glisse|parapente|planeur|ulm|"
                   r"peche|fitness|yoga|pilates|qi gong|tai chi|arts? martia|capoeira|sauvetage|patin|biathlon|pentathlon|ball")
FORT = re.compile(r"handi ?-?sport|sports? adaptes?|para ?-?sports?|paralympi|cecifoot|torball|goalball|showdown|"
                  r"(?:foot|basket|rugby|tennis|hand|handball|ski|volley|hockey|badminton|danse)[ -]?(?:ball )?(?:a 7 |a 13 |a xiii )?(?:en )?fauteuil|"
                  r"fauteuil[ -]?(?:roulant )?(?:foot|basket|rugby|tennis|hand|hockey)|handibasket|handi[ -]?(?:basket|voile|ski|judo|tennis|natation|rugby|escrime|tir|danse|golf|equitation|cheval|kayak|plongee|surf|velo|cyclisme|foot|athle|escalade|boxe|karate|aviron|nautique|glisse|roller|hockey|ping|boccia|badminton|bad|volley|cecifoot)|"
                  r"handbike|baskin|para[ -](?:aviron|tir|canoe|kayak|natation|athle|cyclisme|judo|tennis|badminton|escalade|surf|equitation|triathlon|taekwondo|karate|escrime|tennis de table|ski|hockey|rugby|basket|foot|voile)")
PERS = re.compile(r"personnes? (?:en situation de |porteuses? de |a )?handicap|handicapes?|situation d.?handicap|porteurs? d.?(?:un )?handicap|"
                  r"deficients? (?:visuel|auditif|mentaux|mental|intellectuel|moteur)|deficiences? (?:visuelle|auditive|motrice|mentale|intellectuelle|sensorielle|physique)|"
                  r"malvoyant|mal-voyant|non[- ]voyant|aveugle|\bsourds?\b|malentendant|trisomi|\bautis|paraplegi|tetraplegi|amput|mobilite reduite|infirmes? moteur|\bimc\b|polyhandicap|myopath|"
                  r"handicaps? (?:mental|mentaux|moteur|psychique|physique|visuel|auditif|sensoriel|intellectuel)|en fauteuil|fauteuil roulant|valides? et (?:non[- ]valides?|handicap)|handi[- ]?valides?|valides?[- ]handicap")
PRATIQUE = re.compile(r"pratiqu|enseign|entrain|initi|apprentissage|decouverte|activites? (?:physiques?|sportives?|nautiques?|de pleine nature)|seances?|cours\b|"
                      r"\bclub\b|section|competition|championnat|loisirs? sportifs?|jouer|disciplines?|accueil")
INSTIT = re.compile(r"\b(?:ime|impro|imp|esat|ehpad|fam|mas|sessad|itep|iem|cme|crf|chu)\b|foyer (?:de vie|d.?hebergement|occupationnel|medicalise|d.?accueil)|"
                    r"residents?\b|etablissements?\b|centre (?:de|du) reeducation|reeducation fonctionnelle|hopital|hospitali|clinique|institut medico|"
                    r"maison d.?accueil|maison d.?enfants|centre medico|centre helio|\bapajh\b|\badapei\b|\bapei\b|\bunapei\b|papillons blancs|"
                    r"\bcollege\b|\blycee\b|ecole (?:primaire|elementaire|maternelle|nationale|superieure|d.?ingenieur|de commerce|normale)|universit|etudiants?\b|\bunss\b|\bugsel\b|\busep\b|"
                    r"inscrits dans l.?etablissement|eleves")
COMITE = re.compile(r"^(?:le |la )?(?:comite|ligue|federation|district|union (?:departementale|regionale|nationale|francaise|sportive des sourds de france)|"
                    r"office (?:municipal|intercommunal)|cdos|cros|cdsa|crsa|cdh|crh|ufolep|ffsa|ffh|federation|groupement d.?employeurs|delegation)\b")
SOUTIEN = re.compile(r"soutenir (?:le |la |les |un |une )?(?:projet|athlete|sportif|sportive|joueu|equipe de france)|accompagner (?:madame|monsieur|mme|m\.)|"
                     r"collecte|recolter|lever des fonds|financer|financement|mecenat|sponsor|rallye|aicha|cagnotte|prestations? de services?|"
                     r"entrepreneuri|recherche (?:medicale|scientifique)|sensibilis")
SANTE = re.compile(r"maladies? chroniques?|obesite|surpoids|cancer|seniors?|personnes? agees|ald\b|affection de longue duree|sport[- ]sante|prevention")


def candidat(r):
    """Premier tri automatique : True si l'association part en relecture."""
    codes = (r["objet_social1"], r["objet_social2"])
    t = norm(r["titre"] + " " + r["titre_court"] + " " + r["objet"])
    sportcode = any(c.startswith("011") for c in codes)
    if r["position"] != "A" or not ("011018" in codes or (HANDI.search(t) and (sportcode or SPORT.search(t)))):
        return False
    titre = norm(r["titre"])
    fort, pers = bool(FORT.search(t)), bool(PERS.search(t))
    if (r["date_decla"] or "") < DEPUIS or COMITE.search(titre) or INSTIT.search(t):
        return False
    if not (fort or (pers and (sportcode or "011018" in codes))):
        return False
    if fort and not pers and SANTE.search(t) and not re.search(r"handi|paralymp|cecifoot|torball|goalball|fauteuil", t):
        return False
    if not PRATIQUE.search(t) and not re.search(r"handisport|sport adapte|club", titre):
        return False
    return not (SOUTIEN.search(t) and not re.search(r"pratiqu|enseign|entrain|seances?|cours\b|\bclub\b|section|competition", t))


# ---------- Déjà sur Paralliance (même département, nom très proche) ----------
def nom_court(s):
    s = re.sub(r"\(.*?\)", " ", norm(s))
    s = re.sub(r"\b(association|asso|ass|club|sportive?s?|sport|section|de|du|des|la|le|les|l|d|et|en)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def dep_cp(cp):
    cp = (cp or "").strip()
    return cp[:3] if cp.startswith("97") else cp[:2]


def deja_present(r, base):
    nr, nc = nom_court(r["titre"]), nom_court(r["titre_court"])
    for b in base.get(dep_cp(r["adrs_codepostal"]), []):
        nb = nom_court(b["nom"])
        s = max(SequenceMatcher(None, nr, nb).ratio(), SequenceMatcher(None, nc, nb).ratio() if nc else 0)
        if nb and (nb in nr or nr in nb) and min(len(nb), len(nr)) >= 6:
            s = max(s, 0.9)
        meme_commune = not b.get("ville") or nom_court(b["ville"]) == nom_court(r["adrs_libcommune"])
        if s >= 0.92 or (s >= 0.82 and meme_commune):
            return b
    return None


# ---------- 4. Fiches ----------
def texte(r):
    """Nom + objet, sans accents ni majuscules, tirets et barres remplacés par des espaces."""
    return re.sub(r"\s+", " ", re.sub(r"[-/]", " ", norm(r["titre"] + " ; " + r["objet"])))


# Sport cité dans le nom ou l'objet -> écriture utilisée sur le site. L'ordre compte : « basket fauteuil » avant « basket ».
# Une expression sans sport ("") efface seulement le passage (ex. le « tir sur cible » des plongeurs n'est pas du tir sportif).
SPORTS = [(re.compile(m), s) for m, s in [
    (r"\bfoot(?:ball)? (?:en )?fauteuils?(?: (?:roulant|electrique)s?)?\b|\bfootfauteuil\b", "foot fauteuil"),
    (r"\bceci ?foot\w*|\bfoot(?:ball)? (?:pour )?(?:les )?(?:non |mal )voyants\b|\bfoot(?:ball)? (?:pour )?deficients? visuels?\b", "cécifoot"),
    (r"\bfoot ?golf\b|\bgolf foot\b", "footgolf"),
    (r"\bfoot(?:ball)? americain\b|\bflag football\b", "football américain"),
    (r"\btennis ballon\b|\bfoot tennis\b", ""),
    (r"\bfutsal\b|\bfoot(?:ball)?\b|\bsoccer\b", "football"),
    (r"\bbasket(?:ball| ball)? (?:en )?fauteuils?(?: roulants?)?\b|\bhandi ?basket(?:ball)?\b|\bfauteuil basket\b", "basket fauteuil"),
    (r"\bbaskin\b", "baskin"),
    (r"\bbasket(?:ball| ball)?\b", "basket"),
    (r"\bhand(?:ball| ball)? ?(?:en )?fauteuils?\b|\bhand'fauteuil\b|\bhandfauteuil\b", "hand fauteuil"),
    (r"\bsandball\b|\bhand(?:ball| ball)?\b|\bparahand\b|\bhandi ?hand\b|\bangill'hand\b", "handball"),
    (r"\brugby (?:a (?:13|xiii|7) )?(?:en )?fauteuils?\b|\bquad rugby\b|\bfauteuil rugby\b", "rugby fauteuil"),
    (r"\brugby (?:a )?(?:xiii|13)\b|\bjeu a xiii\b|\brugby league\b", "rugby à xiii"),
    (r"\brugby\b", "rugby"),
    (r"\bvolley(?:ball| ball)? assis\b|\bsitting volley\b", "volley assis"),
    (r"\bbeach volley\w*\b|\bvolley(?:ball| ball)?\b", "volley-ball"),
    (r"\btennis de table\b|\bping ?pong\w*\b|\bhandi ?ping\b|\bpongistes?\b|\bping\b|\btt\b", "tennis de table"),
    (r"\btennis (?:en )?fauteuils?\b|\bfauteuil tennis\b", "tennis fauteuil"),
    (r"\bbeach tennis\b|\btennis de plage\b", "beach tennis"),
    (r"\bpadel\b", "padel"),
    (r"\bpickle ?ball\b", "pickleball"),
    (r"\bsquash\b", "squash"),
    (r"\bpelote basque\b", "pelote basque"),
    (r"\bpara ?tennis\b|\btennis\b", "tennis"),
    (r"\bpara ?badminton\b|\bair ?badminton\b|\bbadminton\b|\bbad\b", "badminton"),
    (r"\btir a l'arc\b|\barchers?\b|\bcompagnies? d'arc\b|(?<!jeanne d')\barc\b(?! en ciel)", "tir à l'arc"),
    (r"\bsarbacanes?\b", "sarbacane"),
    (r"\btir sur cible\b", ""),
    (r"\btir (?:a (?:la )?|de |sportif a la )?sarbacanes?\b", "sarbacane"),
    (r"\btir sportif\b|\bcarabine\b|\bpistolet\b|\bball trap\b|\btir a balles?\b|\bprecision rifle\b", "tir sportif"),
    (r"\bboccia\b", "boccia"),
    (r"\bpetanque\b|\bjeu provencal\b", "pétanque"),
    (r"\bboules? lyonnaises?\b|\bsport boules\b", "boule lyonnaise"),
    (r"\bpalets?\b", "palet"),
    (r"\bboules?\b", "boules"),
    (r"\bbowling\b", "bowling"),
    (r"\bbillards?\b|\bbillardeux\b", "billard"),
    (r"\bflechettes?\b|\bdarts?\b|\bsoft ?darts?\b", "fléchettes"),
    (r"\bnatation (?:artistique|synchronisee)\b", "natation artistique"),
    (r"\bwater ?polo\b", "water-polo"),
    (r"\baqua ?gym\b|\baquaforme\b|\baqua ?fitness\b|\baquabike\b", "aquagym"),
    (r"\bhockey subaquatique\b", "hockey subaquatique"),
    (r"\bapnee\b|\bapneistes?\b", "apnée"),
    (r"\bplongee\w*\b|\bsub ?aquatiques?\b|\bscaphandre\b|\bplongeurs?\b|\bdiving\b", "plongée"),
    (r"\blonge ?cote\b|\bmarche aquatique\b", "longe-côte"),
    (r"\bsauvetage sportif\b|\bsauvetage cotier\b", "sauvetage sportif"),
    (r"\bnatation\b|\bnageurs?\b|\bswim\w*\b|\bnage\b", "natation"),
    (r"\bhandi ?aviron\b|\bpara ?aviron\b|\baviron\b", "aviron"),
    (r"\bdragon ?boat\b", "dragon boat"),
    (r"\bcanoe\w*\b|\bkayak\w*\b|\bpagaies?\b|\bpirogues?\b|\bva'a\b|\brafting\b", "canoë-kayak"),
    (r"\bstand up paddle\b|\bpaddle\b", "paddle"),
    (r"\bchar a voile\b|\bkart a voile\b", "char à voile"),
    (r"\bvol a (?:la )?voile\b|\bplaneurs?\b", "vol à voile"),
    (r"\bhandi ?voile\b|\bpara ?voile\b|\bplanche a voile\b|\bvoile\b|\bvoiliers?\b|\bderiveurs?\b|\bcatamarans?\b|\bwindsurf\w*\b|\bsailing\b|\byachting\b", "voile"),
    (r"\bkite ?surf\w*\b|\bsit ?kite\b|\bkite\b", "kitesurf"),
    (r"\bwing ?foil\b", "wingfoil"),
    (r"\bfoils?\b", "foil"),
    (r"\bhandi ?surf\b|\bpara ?surf\b|\bsurf\b|\bsurfeurs?\b|\bsurfer\b|\bbody ?board\b", "surf"),
    (r"\bwake ?board\w*\b|\bsite? ?wake\b|\bwake skate\b|\bwake\b", "wakeboard"),
    (r"\bski nautique\b", "ski nautique"),
    (r"\bjet ?ski\b|\bmotonautisme\b", "motonautisme"),
    (r"\bski de fond\b", "ski de fond"),
    (r"\bbiathlon\b", "biathlon"),
    (r"\bski ?joe?ring\b", "ski-joëring"),
    (r"\bsnowboard\b", "snowboard"),
    (r"\bhockey sur glace\b|\bpara ?hockey\b|\bhockey luge\b", "hockey sur glace"),
    (r"\bhandi ?ski\b|\bpara ?ski\b|\bsit ?ski\b|\bski alpin\b|\bski\b|\bskis\b|\bskieurs?\b|\bsports? de neige\b|\bsports? d'hiver\b|\bdual ?ski\b|\buni ?ski\b", "ski"),
    (r"\broller hockey\b|\bhockey\b", "hockey"),
    (r"\bcurling\b", "curling"),
    (r"\bpatinage artistique\b", "patinage artistique"),
    (r"\bhandiglace\b|\bpatinage\b|\bpatin a glace\b|\bsports? de glace\b", "patinage"),
    (r"\bskate ?board\b|\bskate\b", "skateboard"),
    (r"\brollers?\b|\btrottinette\b", "roller"),
    (r"\bbmx\b", "bmx"),
    (r"\bhand ?bikes?\b|\bhandcycle\w*\b|\bhandi ?velo\b", "handbike"),
    (r"\bvtt\b|\bvelo tout terrain\b", "vtt"),
    (r"\btandems?\b|\bcyclotouris\w*\b|\bcyclo ?sport\w*\b|\bcyclisme\b|\bcyclistes?\b|\bvelos?\b|\bgravel\b|\bcyclo\b|\bbicyclette\b|"
     r"\bpara ?cyclisme\b|\bcycling\b|\bvelocipedique\b", "cyclisme"),
    (r"\bduathlon\b", "duathlon"),
    (r"\bpara ?triathlon\b|\btriathlon\b|\btriath\w*", "triathlon"),
    (r"\bpentathlon\b|\blaser run\b", "pentathlon"),
    (r"\bpara ?athletisme\b|\bathletisme\b|\bathle\b|\bcourse en fauteuil\b|\bathletics\b", "athlétisme"),
    (r"\bultra ?trail\b|\btrail\b", "trail"),
    (r"\bcourses? a pieds?\b|\brunning\b|\bjogging\b|\bfooting\b|\bcourses? sur route\b|\brun\b|\brunners?\b", "course à pied"),
    (r"\bmarche nordique\b", "marche nordique"),
    (r"\bmarche (?:sportive|rapide|athletique)\b", "marche à pied"),
    (r"\bjoelettes?\b|\bjoelottes\b", "joëlette"),
    (r"\brandonnee\w*\b|\brandonneurs?\b|\brando\b|\btrekking\b", "randonnée"),
    (r"\bgrimpe (?:encadree )?(?:dans les |d')arbres?\b", "grimpe d'arbres"),
    (r"\bpara ?escalade\b|\bescalade\b|\bgrimpe\b|\bvia ferrata\b|\bgrimpeurs?\b", "escalade"),
    (r"\bspeleo\w*\b|\bmilieu souterrain\b|\bcanyon\w*\b", "spéléologie"),
    (r"\bmontagne\b|\balpinisme\b", "montagne"),
    (r"\bparapente\b|\bdelta ?planes?\b|\bvol libre\b", "parapente"),
    (r"\bparamoteur\b", "paramoteur"),
    (r"\bulm\b|\bultra leger motorise\b", "ulm"),
    (r"\bparachutisme\b|\bskydiv\w*\b|\bchute libre\b", "parachutisme"),
    (r"\bmontgolfiere\w*\b|\baerostat\w*\b|\bvol en ballon\b", "montgolfière"),
    (r"\baeromodelisme\b", "aéromodélisme"),
    (r"\bmodelisme\b|\bmodeles? reduits?\b|\bradio ?commande\w*\b", "modélisme"),
    (r"\baviation\b|\bavions?\b|\baeronautique\w*\b|\baero ?club\b|\bsports? aeriens?\b", "aéronautique"),
    (r"\bkarting\b|\bkarts?\b|\bhandikart\b", "karting"),
    (r"\bsports? automobiles?\b|\bsport auto\b|\bdrift\b|\bbuggy\b|\bautomobiles?\b|\bmotorsport\b", "sport automobile"),
    (r"\bmoto ?cross\b|\bmotocyclis\w*\b|\bmotos?\b|\bside ?cars?\b", "moto"),
    (r"\bequitation\b|\bequestres?\b|\bcavaliers?\b|\bponeys?\b|\bchevaux\b|\bcheval\b|\battelage\b|\bdressage\b|\bhippiques?\b|"
     r"\bequihandi\b|\bequimotricite\b|\bequicie\b", "équitation"),
    (r"\bju ?jitsu bresilien\b|\bjiu ?jitsu bresilien\b|\bjjb\b|\bbjj\b", "jiu-jitsu brésilien"),
    (r"\bjudo\w*\b|\bkodokan\b", "judo"),
    (r"\btai ?jitsu\w*\b", "taï-jitsu"),
    (r"\bju ?jitsu\w*\b|\bjiu ?jitsu\w*\b|\bju ?jutsu\b", "jujitsu"),
    (r"\btaiso\b|\btai so\b", "taïso"),
    (r"\bkarate\w*\b|\bshotokan\b|\bkyokushin\b", "karaté"),
    (r"\btae ?kwon ?do\b|\btaekwondo\b|\bhapkido\b", "taekwondo"),
    (r"\baikido\b|\baikibudo\b", "aïkido"),
    (r"\bkendo\b", "kendo"),
    (r"\bkung ?fu\b|\bwushu\b|\bwing ?tsun\b|\bwing ?chun\b|\barts? martiaux chinois\b", "kung fu"),
    (r"\bviet vo dao\b|\bvovinam\b", "viet vo dao"),
    (r"\bsambo\b", "sambo"),
    (r"\bgrappling\b|\bgrappeling\b", "grappling"),
    (r"\bmma\b|\bmixed martial arts?\b|\bpancrace\b", "mma"),
    (r"\bsumo\b", "sumo"),
    (r"\bmuay thai\b|\bboxe thai\w*\b|\bk ?1\b", "muay-thaï"),
    (r"\bsavate\b|\bboxe francaise\b", "savate"),
    (r"\bkick ?box\w*\b|\bfull contact\b|\bhandi ?boxe\b|\bboxe\w*\b|\bbox\b|\bboxing\b|\bpugilisti\w*\b|\bnoble art\b", "boxe"),
    (r"\blutte\b(?! contre| pour| active| anti)|\blutteurs?\b|\bbras de fer\b", "lutte"),
    (r"\bself ?defen[cs]e\b|\bself close defense\b|\bkrav ?maga\b", "self-défense"),
    (r"\bsabre laser\b", "sabre laser"),
    (r"\bescrime\w*\b|\bsalle d'armes\b|\bfleuret\b|\bsabre\b", "escrime"),
    (r"\btrampoline\b|\btumbling\b|\bgymnastique\w*\b|\beveil gymnique\b|\bactivites? gymniques?\b|\bhanditrampgym\b|\bbaby gym\b|"
     r"\bgym (?:volontaire|douce|tonic|enfants?|adaptee|sportive|artistique|rythmique|acrobatique)\b", "gymnastique"),
    (r"\btwirling\w*\b", "twirling bâton"),
    (r"\bcheer\w*\b|\bpom ?pom\w*\b", "cheerleading"),
    (r"\bdanse (?:en )?fauteuil\b|\bfauteuil danse\b", "danse fauteuil"),
    (r"\bzumba\b", "zumba"),
    (r"\bhandi ?danse\b|\bdanses?\b|\bdanseurs?\b|\bhip hop\b|\bbiodanza\b|\bmodern jazz\b|\bclaquettes\b|\bchoregraphi\w*\b|\bdance\b", "danse"),
    (r"\byoga\b", "yoga"),
    (r"\bpilates\b", "pilates"),
    (r"\bqi ?gong\b", "qi-gong"),
    (r"\btai ?chi\w*\b", "taï chi chuan"),
    (r"\bhalterophil\w*\b|\bforce athletique\b|\bbarbell\b|\bpowerlifting\b", "haltérophilie"),
    (r"\bmusculation\b|\bculturisme\b|\bbody ?building\b|\bstreet lifting\b", "musculation"),
    (r"\bfitness\b|\bremise en forme\b|\bcross ?training\b|\bcross ?fit\b|\btraining fonctionnel\b|\bbootcamp\b|\bcardio\w*\b|"
     r"\bentretien physique\b|\bcircuit training\b|\bcross gym\b", "remise en forme"),
    (r"\bswin ?golf\b", "swin golf"),
    (r"\bhandi ?golf\b|\bpara ?golf\b|\bgolf\b|\bgolfs\b|\bgolfeurs?\b|\bgolfiques?\b", "golf"),
    (r"\bjeu d'echecs\b|\bechecs\b(?! scolaires)", "échecs"),
    (r"\bshowdown\b", "showdown"),
    (r"\bgoal ?ball\b", "goalball"),
    (r"\btorball\b", "torball"),
    (r"\bultimate\b|\bfrisbee\b|\bdisques? volants?\b", "ultimate"),
    (r"\bbaseball\w*\b|\bsoftball\b|\bwiffle ?ball\b|\bstickball\b|\bsports? de battes?\b", "baseball"),
    (r"\bcricket\b", "cricket"),
    (r"\bcani ?cross\b|\bsports? canins?\b|\bchiens? d'attelage\b|\bmushing\b|\bcani ?rando\b|\bcani ?vtt\b", "sports canins"),
    (r"\bairsoft\b", "airsoft"),
    (r"\bpeche\b|\bpecheurs?\b", "pêche"),
    (r"\bkin ?ball\b", "kinball"),
    (r"\btchoukball\b", "tchoukball"),
    (r"\bparkour\b", "parkour"),
    (r"\bcirque\b", "cirque"),
    (r"\bjeux finlandais\b|\bmolkky\b", "mölkky"),
    (r"\bcourse d'orientation\b", "course d'orientation"),
    (r"\bplaisance\b|\bactivites? nautiques\b|\bsports? nautiques\b|\bnautisme\b", "nautisme"),
]]
# Seulement quand aucun sport précis n'est cité
GENERIQUES = [(re.compile(m), s) for m, s in [
    (r"\btir\b", "tir sportif"),
    (r"\bactivites? aquatiques\b", "natation"),
    (r"\barts? martiaux\b|\bbudo\b|\bdojos?\b", "arts martiaux"),
    (r"\bsports? de combat\b", "sports de combat"),
    (r"\bactivites? (?:physiques? )?(?:et sportives? )?de pleine nature\b|\bsports? de pleine nature\b", "sports de pleine nature"),
]]
EAU = {"voile", "aviron", "canoë-kayak", "plongée", "natation", "surf", "paddle", "ski nautique", "wakeboard", "motonautisme",
       "char à voile", "kitesurf", "wingfoil", "foil", "dragon boat", "apnée", "longe-côte"}
AIR = {"vol à voile", "ulm", "parapente", "paramoteur", "parachutisme", "montgolfière", "aéromodélisme"}
# Code d'activité déclaré (nomenclature officielle) quand l'objet ne cite aucun sport ; les codes qui regroupent plusieurs sports
# (nautisme, sports de combat, tir…) ne sont pas utilisés
CODES = {"011020": "athlétisme", "011035": "pétanque", "011040": "bowling", "011045": "danse", "011050": "équitation",
         "011060": "escrime", "011065": "basket", "011070": "handball", "011075": "football", "011080": "rugby",
         "011085": "volley-ball", "011100": "golf", "011110": "haltérophilie", "011115": "randonnée",
         "011120": "musculation", "011130": "roller", "011140": "judo", "011155": "ski", "011165": "tennis",
         "011170": "tennis de table", "011180": "cyclisme", "011185": "voile"}


def sports(r):
    t, trouves = texte(r), []
    for motif, sport in SPORTS:
        if motif.search(t):
            t = motif.sub(" # ", t)
            if sport and sport not in trouves:
                trouves.append(sport)
    if not {"tir à l'arc", "tir sportif", "sarbacane"} & set(trouves) and re.search(r"\btir\b", t):
        trouves.append("tir sportif")                     # « tir » seul : tir sportif, sauf dans un club de tir à l'arc
    if not trouves:
        trouves = [s for m, s in GENERIQUES[1:] if m.search(t)][:1]
    if set(trouves) & EAU and "nautisme" in trouves:
        trouves.remove("nautisme")                        # « activités nautiques » d'un club de voile, d'aviron…
    if set(trouves) & AIR and "aéronautique" in trouves:
        trouves.remove("aéronautique")
    if not trouves:
        code = next((c for c in (r["objet_social1"], r["objet_social2"]) if c in CODES), None)
        trouves = [CODES[code]] if code else ["multisport"]
    return trouves


# Handicaps : seulement ceux que l'objet nomme. Un mot comme « physique » ne compte que juste après « handicap » ou « déficience ».
ANCRE = re.compile(r"\bhandicap\w*|\bdeficien\w*|\binfirmes?\b")
FIN_FENETRE = re.compile(r"[;.:()]| afin | pour | dans | ainsi | et de | de developper| notamment| aupres| a la pratique| de pratiquer| par la pratique|"
                         r" pratiquant| activites? physiques?| education physique| preparation physique| grace a| sante mentale|, la |, le |, les | la promotion")
TYPES = [(re.compile(m), h) for m, h in [
    (r"\bphysiques?\b|\bmoteurs?\b|\bmotrices?\b", ("moteur",)), (r"\bvisuel\w*", ("visuel",)),
    (r"\baudit\w*|\bsourd\w*", ("auditif",)), (r"\bmenta\w*|\bintellectuel\w*|\bcogniti\w*", ("mental",)),
    (r"\bpsychiques?\b", ("psychique",)), (r"\bsensoriel\w*", ("visuel", "auditif")),
    (r"\bautis(?:me|tes?|tiques?)\b|\btsa\b", ("autisme",)), (r"\bpolyhandicap\w*", ("polyhandicap",))]]
PARTOUT = [(re.compile(m), h) for m, h in [
    (r"malvoyant|mal voyant|non voyant|\baveugles?\b|\bcecite\b|cecifoot|goal ?ball|torball|showdown|deficients? visuels?", "visuel"),
    (r"\bsourd(?:e|es|s)?\b|malentendant|\bsurdite\b|deficients? auditifs?", "auditif"),
    (r"paraplegi|tetraplegi|\bamput\w*|fauteuil|mobilite reduite|\bpmr\b|infirmes? moteurs?|hand ?bike|myopath|\bparalyses?\b|paralysie cerebrale", "moteur"),
    (r"trisomi", "mental"), (r"\bautis(?:me|tes?|tiques?)\b|\btsa\b|troubles? du spectre autistique", "autisme"),
    (r"alteration de (?:la |leur )?sante mentale|troubles? psychiques?", "psychique"),
    (r"polyhandicap", "polyhandicap")]]
ORDRE_HANDICAPS = ["moteur", "visuel", "auditif", "mental", "psychique", "autisme", "polyhandicap"]


def handicaps(r):
    t, trouves = texte(r), set()
    for m in ANCRE.finditer(t):
        fenetre = FIN_FENETRE.split(t[m.end():m.end() + 70])[0]
        for motif, h in TYPES:
            if motif.search(fenetre):
                trouves.update(h)
    for motif, h in PARTOUT:
        if motif.search(t):
            trouves.add(h)
    return [h for h in ORDRE_HANDICAPS if h in trouves]


def pratique(r, hand):
    t = texte(r)
    hs = bool(re.search(r"handi ?sports?|\bffh\b|federation francaise (?:de )?handisport|paralympi", t)) or bool({"moteur", "visuel", "auditif"} & set(hand))
    sa = bool(re.search(r"sports? adaptes?|\bffsa\b|federation francaise (?:du |de )?sports? adaptes?", t)) or bool({"mental", "psychique", "autisme"} & set(hand))
    return "les deux" if hs and sa else "handisport" if hs else "sport adapte" if sa else ""


# Noms : le RNA les écrit en majuscules sans accents. Mots accentués relevés dans les objets des associations
# (on n'ajoute un accent que s'il est l'écriture courante du mot ; un mot déjà accentué n'est jamais modifié).
def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


ACCENTS = {sans_accents(m): m for m in (
    "abréviation académie accès accessibilité activité activités adapté adaptée adaptées adaptés adhérents aéro "
    "aéroclub aéronautique agglomération aïkido albères alençon alès amitié amputé amputés andré angoulême "
    "appropriés ardèche ariège ariégeoise asnières associées athlé athlète athlétique athlétisme auprès azuréenne "
    "azuréens bagnères barthélemy béarn beauté béthune béthunois béziers brétigny canoë caractère caraïbe "
    "carrières cécifoot châlons chamalières chambéry châtaigneraie châteauroux compétences compétition "
    "compétitions corrèze côte création créteil dauphiné défense delà départemental destinés détente développement "
    "développer dié différences différentes dracénie drôme échirolles éco école écureuils écurie écuries éducation "
    "électricité électrique élite émeraude énergie épée épernay équestre équestres équidé équine équitation ère "
    "espérance étienne étincelle étoile étoiles étranger être étréchy européenne évasion évreux évry fécamp fête "
    "flèche flèches fléchettes fougères grégoire grésivaudan haltérophile haltérophilie handicapées handicapés "
    "hérouville hôtel île isère joëlettes joué karaté kilomètre laïque lédonien léo liberté liées liévin loudéac "
    "lozère lunéville macé mâcon mâconnais marées médiation méditerranée même méthode métropole mézières "
    "miséricorde modèle montélimar montluçon motricité nécessaires nîmes nîmois ouvrière oxygène paralysés "
    "particulièrement péage pédagogique pépinière périgord périgueux péronne pétanque pézenas phénix plérin "
    "ploërmel plongée pôle première pyrénées raphaël ré régates région régional rémoise réunionnaise réunis "
    "samouraï santé saône sénart sèvres société taï télécom thorigné treillières trièves unifié unité vélo "
    "vélocipédique vendée vitalité vitréen zéro "
).split()}
PETITS = {"de", "du", "des", "la", "le", "les", "et", "sur", "en", "d", "l", "sous", "à", "au", "aux", "pour", "par", "avec",
          "dans", "ou", "un", "une", "lès"}
VOYELLES = set("aeiouyàâäéèêëîïôöùûü")
SIGLES = {"AS", "US", "CA", "ASC", "ASL", "ASPTT", "ASVEL", "CS", "CSA", "FC", "AC", "SC", "ES", "JS", "OC", "UC", "UA",
          "AJ", "EP", "AB", "ALC", "AMA", "APT", "ASAD", "ASAF", "ASAL", "ASAM", "ASET", "ASJ", "ASLM", "ASSL", "ASSR", "ASTT",
          "AVR", "OSM", "CLARA", "UOL", "GUC", "PUC", "USM", "SRD", "COSPI", "ANISA", "AMISS", "AHSAN", "AFACH", "ADAE", "ACSF",
          "ABY", "IHL", "SOR", "MJC", "ACI", "AJSM", "ASAMB", "USSA", "PSA", "OCC", "ACPV", "AGL", "AMP", "ACC", "ACH", "AJSS",
          "ASGP", "ASPAR", "ASPHT", "ASSAB", "ASSHAV", "ASNCM", "CEFC", "AAC", "CAH", "CEPL", "CEV", "CMO", "CSADN", "CSASP",
          "CSINI", "CSPG", "UBAA", "MBC", "CMH", "TCA", "TPP", "SPEC", "CNT", "APSA", "USPGA", "ESMCA", "JAD", "ESEG", "EHB",
          "ASJ", "ASEP", "UVS", "VPP", "PSCB", "TCMB", "AMI", "ASP", "CER", "CPG", "RSH", "ABBF", "PBV", "RMA", "CNH", "ASBOXE",
          "OSE", "UNIK", "ATSA", "TAGH", "SAMBA", "STELA", "FAIS", "EGE", "AVO", "TCAV", "ASAA", "ASPE", "CSAM", "LMJSM", "ULJAPR",
          "JDA", "UMS", "ULM", "USSL", "TSA", "NMA", "FCA", "MMA", "JSA"}
MINUSCULE_APRES_APOSTROPHE = {"P", "T"}               # « P'tit », « T'es pas cap »
CORRECTIONS_NOMS = [("Comte de Foix", "Comté de Foix"), ("La Comte Omnisports", "La Comté Omnisports"), ("Joué-les-Tours", "Joué-lès-Tours"),
                    ("Ch'Tirafes", "Ch'tirafes"), ("Fcgrenoble", "FC Grenoble"), ("CSADN-Se", "CSADN-SE"), ("au Delà", "au-delà"), ("Flo'Ckey", "Flo'ckey")]
COMMUNES_ARTICLE = set()                                # « la baule », « le pouliguen »… (rempli au chargement des communes)


def commune_suit(morceaux, i):
    """Vrai si l'article commence un nom de commune : « Cercle Nautique La Baule », « Club du Havre » non."""
    suivant = next((m for m in morceaux[i + 1:] if re.fullmatch(r"[A-Za-zÀ-ÿ0-9]+", m or "")), "")
    return f"{norm(morceaux[i])} {norm(suivant)}" in COMMUNES_ARTICLE


def voisin(morceaux, i, sens):
    """Morceau non vide juste avant (sens -1) ou juste après (sens 1) le morceau i."""
    j = i + sens
    while 0 <= j < len(morceaux) and morceaux[j] == "":
        j += sens
    return morceaux[j] if 0 <= j < len(morceaux) else ""


def est_sigle(m, mots):
    """Vrai si m (3 à 6 lettres) est formé des initiales de mots qui se suivent dans le nom : « ESMCA » pour
    « Étoile Sportive du Marais Challans Athlétisme »."""
    if not (3 <= len(m) <= 6) or m.lower() in PETITS:
        return False
    for petits in (True, False):
        liste = [sans_accents(x)[0].upper() for x in mots if x != m and not x.isdigit() and (petits or x.lower() not in PETITS)]
        if m.upper() in "".join(liste):
            return True
    return False


def nom_club(titre):
    """« ASSOCIATION SPORTIVE DE L'ILE DE RE (ASIR) » -> « Association Sportive de l'Île de Ré (ASIR) »."""
    t = " ".join(titre.replace("’", "'").replace('"', " ").replace("\n", " ").split())
    t = re.sub(r"\b([DLdl]) '(?=\w)", r"\1'", re.sub(r" -(?=\w)", " - ", t))           # « DE L 'ENTENTE », « CAPS -SAINTE-ANNE »
    t = " ".join(re.sub(r"(?<![A-Za-zÀ-ÿ])'|'(?![A-Za-zÀ-ÿ])", " ", t).split())       # guillemets simples autour d'un mot
    t = re.sub(r"\s*\(\s*", " (", re.sub(r"\s*\)", ")", t)).strip()
    t = re.sub(r"\s*,\s*", ", ", re.sub(r"\b1 ERE\b", "1ERE", re.sub(r"(?<=\w) ' (?=\w)", "'", t)))
    t += ")" * (t.count("(") - t.count(")"))                                          # parenthèse non refermée dans le RNA
    t = re.sub(r"\)(?=[A-Za-zÀ-ÿ])", ") ", re.sub(r"(\w)- (\w)", r"\1-\2", t))       # « (BCPJSN)NIMES », « SAINT- CESAIRE »
    t = re.sub(r"(?<=[A-Za-zÀ-ÿ]{2})\.$", "", t)                                   # point final (pas celui d'un sigle A.S.)
    t = re.sub(r"\b([DL]) (?=[AEIOUYH])", r"\1'", t)               # « D ARCHERS » -> « D'ARCHERS »
    morceaux = re.split(r"(\s+|-|'|/|\(|\)|\.|&|,|!|:|\+)", t)
    mots = [m for m in morceaux if re.fullmatch(r"[A-Za-zÀ-ÿ0-9]+", m or "")]
    dernier = max(i for i, m in enumerate(morceaux) if re.fullmatch(r"[A-Za-zÀ-ÿ0-9]+", m or ""))
    sortie, premier = [], True
    for i, m in enumerate(morceaux):
        if not re.fullmatch(r"[A-Za-zÀ-ÿ0-9]+", m or ""):
            sortie.append(m)
            if (m == "-" and voisin(morceaux, i, -1).isspace()) or (m == ")" and norm(next((x for x in morceaux[i + 1:] if x.strip()), "")) in ("le", "la", "les")):
                premier = True                                  # « Cap 21 - Les Coureurs… », « (A.E.P.H.V.) Les Mirauds Volants »
            continue
        apres, avant = voisin(morceaux, i, 1), voisin(morceaux, i, -1)
        bas = m.lower()
        if avant == "(" and apres == ")" and len(m) >= 3 and m.isupper():
            mot = m                                                 # sigle seul entre parenthèses : (CLEAR)
        elif re.fullmatch(r"\d+(?:ERE|ER|EME|E)", m.upper()):
            mot = re.sub(r"(\d+)(.*)", lambda x: x.group(1) + {"ERE": "ère", "ER": "er"}.get(x.group(2).upper(), "e"), m)
        elif re.search(r"\d", m) or (m.upper() in SIGLES and avant != "'") or (len(m) >= 2 and not (set(bas) & VOYELLES) and bas not in ("st", "ch")):
            mot = m.upper()                                         # sigle : TT, BCS, ASPTT, CN2B…
        elif len(m) == 1 and apres == ".":
            mot = m.upper()                                         # sigle à points : A.S.P.T.T.
        elif m.isupper() and (re.fullmatch(r"X{0,3}(?:IX|IV|V?I{0,3})|X{1,3}V?I{0,3}", m) and len(m) >= 2 or est_sigle(m, mots)):
            mot = m                                                 # chiffres romains (XIII), sigle formé des initiales
        elif bas == "a" and not premier and avant.isspace():
            mot = "à"
        elif len(m) == 1 and apres == "'":
            mot = m.lower() if (bas in "dl" and not premier) else m.upper()
        elif len(m) == 1 and avant == "'" and (i == dernier or apres.isspace()):
            mot = bas                                               # « Brother's », « Va'a »
        elif bas in PETITS and not premier and i != dernier and (avant == "-" or not commune_suit(morceaux, i)):
            mot = bas
        elif bas in ("st", "ste"):
            mot = bas.capitalize()
        else:
            mot = ACCENTS.get(bas, bas)
            mot = mot[:1].upper() + mot[1:]
        if avant == "'" and i >= 2 and morceaux[i - 2].upper() in MINUSCULE_APRES_APOSTROPHE and len(morceaux[i - 2]) == 1:
            mot = mot.lower() if mot != mot.upper() else mot
        sortie.append(mot)
        premier = False
    nom = "".join(sortie)
    for faux, juste in CORRECTIONS_NOMS:
        nom = nom.replace(faux, juste)
    return nom[:1].upper() + nom[1:]


# Extrait de l'objet : la proposition qui parle du handicap, telle que l'association l'a écrite
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def plat(s):
    """Comme norm(), mais chaque caractère reste à sa place (pour retrouver le passage dans le texte d'origine)."""
    return "".join(b if len(b := sans_accents(c).lower()) == 1 else c for c in s).replace("’", "'")


def extrait(objet):
    o = " ".join(objet.split())
    p = plat(o)
    m = PERS.search(p) or FORT.search(p) or HANDI.search(p)
    if not m:
        return ""
    debut = max([p.rfind(sep, 0, m.start()) + len(sep) for sep in (";", ". ", " - ", "•") if p.rfind(sep, 0, m.start()) >= 0] or [0])
    fins = [x for x in (p.find(";", m.end()), p.find(". ", m.end()), p.find(" - ", m.end())) if x >= 0]
    fin = min(fins) if fins else len(o)
    if fin - debut > 240:                                  # proposition trop longue : on garde le passage autour du handicap
        a = max(debut, m.start() - 110)
        b = min(fin, a + 230)
        a = debut if a == debut else o.find(" ", a) + 1
        b = fin if b == fin else o.rfind(" ", a, b)
        morceau = ("…" if a > debut else "") + o[a:b].strip(" ,;") + ("…" if b < fin else "")
    else:
        morceau = o[debut:fin]
    morceau = morceau.strip(" -–•*,.;:\"").replace("«", "“").replace("»", "”")
    morceau += ")" * (morceau.count("(") - morceau.count(")"))
    if sum(c.isupper() for c in o) > 0.6 * sum(c.isalpha() for c in o):     # objet écrit en majuscules
        morceau = re.sub(r"[a-zà-ÿ]+", lambda x: ACCENTS.get(x.group(0), x.group(0)), morceau.lower())
    return morceau[:1].upper() + morceau[1:]


def accessibilite(r, extraits=None):
    a, mois = r["date_decla"][:4], int(r["date_decla"][5:7])
    morceau = (extraits or {}).get(r["id"]) or extrait(r["objet"])           # extrait corrigé à la relecture (nom de personne retiré)
    texte_ = f"Objet déclaré par l'association au Répertoire national des associations (dernière déclaration : {MOIS[mois - 1]} {a})"
    return f"{texte_} : « {morceau} »." if morceau else texte_ + "."


# Commune du siège : nom officiel (geo.api.gouv.fr) à partir du code commune, et son centre pour la carte
ANCIENNES_COMMUNES = {"49149": "49261", "85307": "85001", "85060": "85194", "86146": "86115", "93059": "93066"}   # fusionnées depuis


def telecharger(url, essais=5):
    req = urllib.request.Request(url, headers={"User-Agent": "Paralliance (contact@paralliance.org)"})
    for i in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
                return json.load(r)
        except OSError:
            if i == essais - 1:
                raise


def charger_communes(dossier=None):
    if dossier:
        com = json.load(open(os.path.join(dossier, "communes.json"), encoding="utf-8"))
        arr = json.load(open(os.path.join(dossier, "arrondissements.json"), encoding="utf-8"))
    else:
        com, arr = telecharger(GEO), telecharger(GEO + "&type=arrondissement-municipal")
    for c in com:
        mots = re.sub(r"[-']", " ", norm(c["nom"])).split()
        if len(mots) > 1 and mots[0] in ("le", "la", "les"):
            COMMUNES_ARTICLE.add(" ".join(mots[:2]))
    return {c["code"]: c for c in com}, {c["code"]: c for c in arr}


def lieu(r, com, arr):
    code = ANCIENNES_COMMUNES.get(r["adrs_codeinsee"], r["adrs_codeinsee"])
    c = arr.get(code) or com.get(code)
    if not c:
        return None
    m = re.match(r"(Paris|Marseille|Lyon) (\d+)(?:er|e) Arrondissement", c["nom"])
    ville = c["nom"] if not m else m.group(1) if m.group(1) != "Lyon" else f"Lyon {m.group(2)}{'er' if m.group(2) == '1' else 'e'}"
    cps, cp = c.get("codesPostaux") or [], (r["adrs_codepostal"] or "").strip()
    if cp not in cps:
        cp = cps[0]                                       # boîte postale (Cedex) : code postal principal de la commune
    lon, lat = c["centre"]["coordinates"]
    return ville, cp, lat, lon


def departements():
    """Départements connus du site (liste REGIONS de index.html)."""
    with open(os.path.join(ICI, "..", "index.html"), encoding="utf-8") as f:
        bloc = re.search(r"const REGIONS = \{(.*?)\};", f.read(), re.S).group(1)
    return {d.split(" ", 1)[0] for _, liste in re.findall(r'"([^"]+)": "([^"]+)"', bloc) for d in liste.split("|")}


def dep_site(cp):
    """Même calcul que depOf() dans index.html."""
    if cp.startswith("97"):
        return cp[:3]
    if cp.startswith("20"):
        return "2A" if int(cp[:3]) < 202 else "2B"
    return cp[:2]


# Site déclaré : gardé seulement s'il répond, n'affiche pas un contenu suspect et parle bien du club.
# Les réseaux sociaux et HelloAsso bloquent les robots : impossible à vérifier, donc non repris.
RESEAUX = re.compile(r"facebook\.|fb\.com|fb\.me|instagram\.|linkedin\.|twitter\.|//(?:www\.)?x\.com|tiktok\.|youtube\.|youtu\.be|"
                     r"helloasso\.|^https?://(?:www\.)?wix\.com/?$")
SUSPECT = re.compile(r"\b(casino|slot|gacor|togel|judi|poker|betting|viagra|cialis|porn|escort|forex|bandar|"
                     r"domain (?:is )?for sale|buy this domain|ce domaine est (?:à vendre|en vente)|this domain has expired)\b", re.I)
MOTS_VIDES = {"association", "club", "sport", "sports", "sportive", "sportives", "sportif", "handisport", "adapte", "adaptes", "union",
              "cercle", "amicale", "loisirs", "olympique", "athletique", "jeunesse", "entente", "etoile", "stade", "racing", "team",
              "section", "pays", "saint", "sainte", "france", "grand", "avenir", "ensemble", "pour", "tous", "toutes", "culture",
              "culturelle", "omnisports", "handi", "multisports", "academie"}


def site_declare(u):
    u = (u or "").strip().strip(".,;")
    if not u or " " in u or "@" in u:
        return ""
    u = u if re.match(r"https?://", u, re.I) else "https://" + u
    hote = urllib.parse.urlsplit(u).hostname or ""
    return "" if "." not in hote or RESEAUX.search(u.lower()) else u


def verifier_site(url, nom, ville):
    url = re.sub(r"^http://", "https://", url, flags=re.I)              # on ne publie que des liens sécurisés (https)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Paralliance, verification des liens; contact@paralliance.org)"})
    for essai in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as r:
                page, fin = r.read(400000).decode("utf-8", "replace"), r.geturl()
            break
        except Exception:
            if essai:
                return ""
    texte_page = norm(html_en_texte(page))
    if SUSPECT.search(texte_page[:20000]):
        return ""
    mots = {w for w in re.findall(r"[a-z0-9]{4,}", norm(nom + " " + ville)) if w not in MOTS_VIDES}
    if mots and not any(w in texte_page or w in norm(fin) for w in mots):
        return ""
    return fin if urllib.parse.urlsplit(fin).hostname == urllib.parse.urlsplit(url).hostname else url


def html_en_texte(page):
    import html
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S | re.I)))


def fiche(r, com, arr, sites, corrections=None, extraits=None):
    l = lieu(r, com, arr)
    if not l:
        return None
    ville, cp, lat, lon = l
    hand = handicaps(r)
    sport = (corrections or {}).get(r["id"]) or ", ".join(sports(r))       # sports corrigés à la relecture
    return {"sport": sport, "nom": nom_club(r["titre"]), "code_postal": cp, "ville": ville,
            "handicaps": ", ".join(hand), "pratique": pratique(r, hand), "accessibilite": accessibilite(r, extraits),
            "site": sites.get(r["id"], ""), "latitude": str(lat), "longitude": str(lon), "source": SOURCE}


# ---------- Lecture du fichier RNA et écriture du SQL ----------
def lire_rna(chemin, retenus, relus):
    garde, non_relus = {}, []
    with zipfile.ZipFile(chemin) as z:
        for nom in sorted(z.namelist()):
            with z.open(nom) as f:
                for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";"):
                    if r["id"] in retenus:
                        garde[r["id"]] = r
                    elif r["id"] not in relus and candidat(r):
                        non_relus.append(r["id"])
    return garde, non_relus


def clubs_en_ligne():
    lignes = []
    while True:
        url = f"{SUPABASE}?select=nom,code_postal,ville&order=id.asc&offset={len(lignes)}&limit=1000"
        req = urllib.request.Request(url, headers={"apikey": CLE, "User-Agent": "Paralliance (contact@paralliance.org)"})
        with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
            page = json.load(r)
        lignes += page
        if len(page) < 1000:
            break
    par_dep = {}
    for b in lignes:
        par_dep.setdefault(dep_cp(b["code_postal"]), []).append(b)
    return par_dep


def main():
    chemin, dossier = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    relecture = json.load(open(os.path.join(ICI, "rna_relecture.json"), encoding="utf-8"))
    retenus, ecartes, sites = set(relecture["retenus"]), relecture["ecartes"], relecture.get("sites", {})
    corrections, extraits = relecture.get("sports", {}), relecture.get("extraits", {})
    com, arr = charger_communes(dossier)
    deps, base = departements(), clubs_en_ligne()
    lignes, non_relus = lire_rna(chemin, retenus, retenus | set(ecartes))
    if non_relus:
        print(f"-- {len(non_relus)} candidats pas encore relus (non importés) : {', '.join(non_relus[:20])}", file=sys.stderr)
    fiches = []
    for i in sorted(lignes, key=lambda k: (lignes[k]["adrs_codepostal"], k)):
        r = lignes[i]
        f = fiche(r, com, arr, sites, corrections, extraits)
        if not f or r["adrs_codeinsee"][:3] in COLLECTIVITES or dep_site(f["code_postal"]) not in deps:
            print(f"-- hors départements du site : {r['id']} {r['titre']}", file=sys.stderr)
            continue
        if deja_present(r, base):
            print(f"-- déjà sur Paralliance : {r['id']} {r['titre']}", file=sys.stderr)
            continue
        fiches.append(f)
    for n in range(0, len(fiches), PAR_FICHIER):
        partie = n // PAR_FICHIER + 1
        with open(os.path.join(ICI, f"17_import_rna_{partie}.sql"), "w", encoding="utf-8") as f:
            f.write(requete(fiches[n:n + PAR_FICHIER], f"Répertoire national des associations, partie {partie}"))
    print(f"{len(fiches)} clubs écrits dans {(len(fiches) - 1) // PAR_FICHIER + 1} fichiers 17_import_rna_*.sql")


if __name__ == "__main__":
    main()
