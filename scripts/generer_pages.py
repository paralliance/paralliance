"""Fabrique les pages que Google peut lire : une page par club, une page par département, la liste de tous les
clubs et le sitemap.xml.

Le site principal (index.html) charge les clubs avec JavaScript : Google n'y voit qu'une seule page. Ces pages
statiques reprennent les mêmes informations en HTML simple, pour que chaque club puisse apparaître dans les
résultats de recherche (« judo handicap Lannion »…). Chaque page renvoie vers la fiche du club sur la carte.

Lancé chaque nuit par GitHub (.github/workflows/pages-clubs.yml) : un club validé dans Supabase a sa page le
lendemain, un club retiré perd la sienne. Aucune action à faire à la main.

Utilisation : python scripts/generer_pages.py                 (lit les clubs publiés dans Supabase)
              python scripts/generer_pages.py clubs.json      (test : lit les clubs dans un fichier)
"""
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.request
from urllib.parse import quote

SITE = "https://paralliance.org"
SUPABASE_URL = "https://aogcjrfrfdasxesntlpk.supabase.co"
SUPABASE_KEY = "sb_publishable_ZNohzowK1cNBG_-qukzemQ_KAG9EX-Z"   # clé publique (lecture des clubs publiés seulement)
COLONNES = ("id,sport,nom,adresse,code_postal,ville,handicaps,pratique,creneaux,accessibilite,telephone,email,site,"
            "label,para_sportifs,encadrant_forme,verifie_le,essai,latitude,longitude,source")
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRATIQUES = {"handisport": "Handisport", "sport adapte": "Sport adapté", "les deux": "Handisport et sport adapté"}
HANDICAPS = {"visuel": "visuel", "auditif": "auditif", "moteur": "moteur", "mental": "mental", "psychique": "psychique",
             "autisme": "autisme", "polyhandicap": "polyhandicap"}


# ===== Données =====
def lire_clubs(fichier=None):
    if fichier:
        with open(fichier, encoding="utf-8") as f:
            return json.load(f)
    lignes = []
    while True:
        url = f"{SUPABASE_URL}/rest/v1/clubs?select={COLONNES}&order=id.asc&offset={len(lignes)}&limit=1000"
        req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY})
        with urllib.request.urlopen(req, timeout=30) as r:
            page = json.load(r)
        lignes += page
        if len(page) < 1000:
            return lignes


def departements():
    """Codes et noms des départements, lus dans index.html pour n'avoir qu'une seule liste à tenir à jour."""
    with open(os.path.join(RACINE, "index.html"), encoding="utf-8") as f:
        bloc = re.search(r"const REGIONS = \{(.*?)\};", f.read(), re.S).group(1)
    deps = {}
    for region, liste in re.findall(r'"([^"]+)": "([^"]+)"', bloc):
        for d in liste.split("|"):
            code, nom = d.split(" ", 1)
            deps[code] = (nom, region)
    return deps


def dep_of(cp, deps):
    cp = (cp or "").strip().upper()
    if cp in deps:                         # certaines sources ne donnent que le département (ex. « 22 »)
        return cp
    if not re.fullmatch(r"\d{5}", cp):
        return ""
    if cp.startswith("97"):
        return cp[:3]
    if cp.startswith("20"):
        return "2A" if int(cp[:3]) < 202 else "2B"
    return cp[:2]


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")[:70].strip("-")


def cap(s):
    return s[:1].upper() + s[1:] if s else s


def texte(r, k):
    return "" if r.get(k) is None else str(r[k]).strip()


def club(r, deps):
    cp = texte(r, "code_postal")
    site = texte(r, "site")
    if site and not re.match(r"^https?://", site, re.I):
        site = "https://" + site
    dep = dep_of(cp, deps)
    return {
        "id": r["id"], "nom": texte(r, "nom"), "adresse": texte(r, "adresse"), "cp": cp,
        "ville": texte(r, "ville") or (deps[dep][0] if dep in deps else ""),   # source sans commune : le département
        "dep": dep_of(cp, deps),
        "sports": list(dict.fromkeys(s.strip().lower() for s in re.split(r"[,;]", texte(r, "sport")) if s.strip())),
        "handicaps": [h for h in (norm(x) for x in re.split(r"[,;]", texte(r, "handicaps"))) if h],
        "pratique": PRATIQUES.get(norm(texte(r, "pratique")), ""),
        "creneaux": [s.strip() for s in texte(r, "creneaux").split(";") if s.strip()],
        "acces": texte(r, "accessibilite"), "tel": texte(r, "telephone"), "email": texte(r, "email"),
        "site": site if re.fullmatch(r"https?://[^\s\"'<>]+", site) else "",
        "label": texte(r, "label"), "essai": texte(r, "essai"),
        "lat": r.get("latitude"), "lon": r.get("longitude"), "source": texte(r, "source"),
    }


# ===== Gabarit commun =====
STYLE = """
:root{--bg:#F6F8F7;--panel:#fff;--text:#16211F;--muted:#55635F;--line:#DCE3E0;--accent:#2F6F6A;--gold:#F5B841}
@media (prefers-color-scheme:dark){:root{--bg:#0F1614;--panel:#17211E;--text:#E8EFEC;--muted:#A2B1AC;--line:#26332F;--accent:#6CC1B8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}main,header,footer{max-width:820px;margin:0 auto;padding:0 16px}
header{display:flex;align-items:center;gap:.6rem;padding-top:1rem;padding-bottom:1rem}
header a{display:flex;align-items:center;gap:.5rem;text-decoration:none;color:var(--text);font-weight:800;font-size:1.15rem}
header img{width:36px;height:36px;border-radius:9px}.para{color:var(--accent)}
nav.fil{font-size:.9rem;color:var(--muted);margin:.5rem 0 1rem}nav.fil a{color:var(--muted)}
h1{font-size:1.7rem;line-height:1.25;margin:.2rem 0 .4rem}.lieu{color:var(--muted);margin:0 0 1rem}
.carte{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:1.2rem 1.3rem;margin:0 0 1rem}
.carte h2{font-size:1.05rem;margin:0 0 .5rem}.carte p,.carte ul{margin:0}.carte ul{padding-left:1.2rem}
.tags{display:flex;flex-wrap:wrap;gap:.4rem}.tag{background:color-mix(in srgb,var(--accent) 12%,var(--panel));color:var(--text);border-radius:999px;padding:.2rem .7rem;font-size:.9rem;text-decoration:none}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;padding:.7rem 1.2rem;border-radius:999px;margin:.3rem .4rem .3rem 0}
.btn.sec{background:transparent;color:var(--accent);border:1.5px solid var(--accent)}
ul.liste{list-style:none;padding:0;margin:0}ul.liste li{padding:.55rem 0;border-bottom:1px solid var(--line)}ul.liste li:last-child{border:0}
ul.liste small{display:block;color:var(--muted)}.cols{columns:2 240px;gap:1.5rem}.cols li{break-inside:avoid}
footer{color:var(--muted);font-size:.9rem;padding-top:1.5rem;padding-bottom:2rem}
"""


def page(titre, description, chemin, corps, jsonld=None, indexer=True):
    e = html.escape
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{SITE}/{chemin}">{"" if indexer else chr(10) + '<meta name="robots" content="noindex, follow">'}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Paralliance">
<meta property="og:title" content="{e(titre)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{SITE}/{chemin}">
<meta property="og:image" content="{SITE}/icon-512.png">
<link rel="icon" href="/icon-192.png" sizes="192x192" type="image/png">
<meta name="theme-color" content="#2F6F6A">
<style>{STYLE}</style>
{ld}
</head>
<body>
<header><a href="/"><img src="/icon-192.png" alt="" width="36" height="36"><span><span class="para">Para</span>lliance</span></a></header>
<main>
{corps}
</main>
<footer>Paralliance, l'annuaire des clubs de sport qui accueillent les personnes en situation de handicap, partout en France.
<br><a href="/">Rechercher sur la carte</a> · <a href="/clubs/">Tous les clubs</a> · <a href="/#propose">Inscrire un club</a></footer>
</body>
</html>
"""


# ===== Pages =====
def fiche_mince(c):
    """Fiche sans aucune information pratique (ni site, ni téléphone, ni e-mail, ni créneaux, ni accès).
    Elle reste sur le site et sur la carte, mais Google ne l'indexe pas et elle n'est pas dans le sitemap :
    Google juge le site sur l'ensemble de ses pages, et ces fiches n'apportent que le nom et la commune."""
    return not (c["site"] or c["tel"] or c["email"] or c["creneaux"] or c["acces"])


def nom_dep(code, deps):
    return f"{deps[code][0]} ({code})" if code in deps else ""


def page_club(c, chemin, deps, voisins):
    e = html.escape
    sports = ", ".join(cap(s) for s in c["sports"])
    dep = nom_dep(c["dep"], deps)
    lieu = c["ville"] + (f" · {dep}" if dep else "")
    hand = [HANDICAPS.get(h, h) for h in c["handicaps"]]
    mot = (c["pratique"] or "accueil handicap").lower()
    titre = f"{c['nom']} – {', '.join(cap(s) for s in c['sports'][:3])} à {c['ville']}, {mot} | Paralliance"
    desc = f"{c['nom']} à {c['ville']}" + (f" ({dep})" if dep else "") + f" : {sports.lower()}"
    if hand:
        desc += f", accueil des personnes en situation de handicap {', '.join(hand)}"
    # La description n'annonce que ce que la fiche contient vraiment
    infos = [mot for mot, present in (("créneaux", c["creneaux"]), ("accessibilité", c["acces"]),
                                      ("contact", c["tel"] or c["email"] or c["site"])) if present]
    desc += f". {cap(liste_fr(infos))} sur Paralliance." if infos else ". Carte et itinéraire sur Paralliance."

    adresse = " ".join(x for x in (c["adresse"], c["cp"] if len(c["cp"]) == 5 else "", c["ville"]) if x)
    blocs = [f'<div class="carte"><h2>Sports proposés</h2><div class="tags">{"".join(f"<span class=tag>{e(cap(s))}</span>" for s in c["sports"])}</div></div>']
    accueil = ([f"<span class=tag>{e(c['pratique'])}</span>"] if c["pratique"] else []) + [f"<span class=tag>Handicap {e(h)}</span>" for h in hand]
    if accueil:
        blocs.append(f'<div class="carte"><h2>Accueil</h2><div class="tags">{"".join(accueil)}</div></div>')
    if c["creneaux"]:
        blocs.append('<div class="carte"><h2>Créneaux</h2><ul>' + "".join(f"<li>{e(s)}</li>" for s in c["creneaux"]) + "</ul></div>")
    if c["essai"]:
        blocs.append(f'<div class="carte"><h2>Séance d\'essai</h2><p>{e(c["essai"])}</p></div>')
    blocs.append(f'<div class="carte"><h2>Adresse</h2><p>{e(adresse) or "Adresse non communiquée"}</p></div>')
    if c["acces"]:
        blocs.append(f'<div class="carte"><h2>Accès</h2><p>{e(c["acces"])}</p></div>')
    contact = []
    if c["tel"]:
        contact.append(f'Téléphone : <a href="tel:{e(re.sub(r"[^0-9+]", "", c["tel"]))}">{e(c["tel"])}</a>')
    if c["email"]:
        contact.append(f'E-mail : <a href="mailto:{e(c["email"])}">{e(c["email"])}</a>')
    if c["site"]:
        contact.append(f'Site : <a href="{e(c["site"])}" rel="nofollow noopener" target="_blank">{e(c["site"])}</a>')
    if contact:
        blocs.append('<div class="carte"><h2>Contact</h2><p>' + "<br>".join(contact) + "</p></div>")
    if c["source"]:
        blocs.append(f'<p class="lieu">Source : {e(c["source"])}</p>')
    blocs.append(f'<p class="lieu">Une info est fausse ? <a href="mailto:contact@paralliance.org?subject={e(quote("Correction : " + c["nom"]))}">Signaler une correction</a></p>')
    if voisins:
        blocs.append(f'<div class="carte"><h2>Autres clubs – {e(dep)}</h2><ul class="liste">'
                     + "".join(f'<li><a href="/{v["chemin"]}">{e(v["nom"])}</a><small>{e(", ".join(cap(s) for s in v["sports"][:3]))} · {e(v["ville"])}</small></li>' for v in voisins)
                     + f'</ul><p style="margin-top:.6rem"><a href="/departements/{deps_slug(c["dep"], deps)}.html">Tous les clubs du département</a></p></div>')

    fil = f'<nav class="fil"><a href="/">Accueil</a> › <a href="/clubs/">Clubs</a>'
    if dep:
        fil += f' › <a href="/departements/{deps_slug(c["dep"], deps)}.html">{e(dep)}</a>'
    fil += "</nav>"
    corps = (f'{fil}<h1>{e(c["nom"])}</h1><p class="lieu">{e(sports)} · {e(lieu)}</p><p>{e(presentation(c, dep, hand))}</p>'
             f'<p><a class="btn" href="/#club-{c["id"]}">Ouvrir la fiche sur Paralliance</a>'
             f'<a class="btn sec" href="https://www.google.com/maps/dir/?api=1&amp;destination={e(quote(adresse or c["nom"] + " " + c["ville"]))}" target="_blank" rel="noopener">Itinéraire</a></p>'
             + "".join(blocs))

    org = {"@context": "https://schema.org", "@type": "SportsOrganization", "name": c["nom"], "url": f"{SITE}/{chemin}",
           "sport": [cap(s) for s in c["sports"]],
           "address": {"@type": "PostalAddress", "addressLocality": c["ville"], "addressCountry": "FR",
                       **({"streetAddress": c["adresse"]} if c["adresse"] else {}),
                       **({"postalCode": c["cp"]} if len(c["cp"]) == 5 else {})}}
    if c["tel"]:
        org["telephone"] = c["tel"]
    if c["email"]:
        org["email"] = c["email"]
    if c["site"]:
        org["sameAs"] = c["site"]
    if c["lat"] is not None and c["lon"] is not None:
        org["geo"] = {"@type": "GeoCoordinates", "latitude": c["lat"], "longitude": c["lon"]}
    fil_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE}/"},
        {"@type": "ListItem", "position": 2, "name": "Clubs", "item": f"{SITE}/clubs/"},
        {"@type": "ListItem", "position": 3, "name": c["nom"], "item": f"{SITE}/{chemin}"}]}
    return page(titre, desc, chemin, corps, [org, fil_ld], indexer=not fiche_mince(c))


def liste_fr(mots):
    return mots[0] if len(mots) == 1 else ", ".join(mots[:-1]) + " et " + mots[-1]


def presentation(c, dep, hand):
    """Une phrase rédigée à partir des seules données du club (rien n'est ajouté)."""
    lieu = c["ville"] + (f" ({dep.rsplit(' (', 1)[0]})" if dep and not dep.startswith(c["ville"]) else "")
    phrase = f"{c['nom']}, à {lieu}, propose {liste_fr(c['sports'])}"
    if hand:
        phrase += f" et accueille les personnes en situation de handicap {liste_fr(hand)}"
    phrase += "."
    if c["pratique"]:
        phrase += f" Pratique : {c['pratique'].lower()}."
    if c["label"]:
        phrase += f" {c['label']}."
    if c["essai"]:
        phrase += " Séance d'essai possible."
    return phrase


def deps_slug(code, deps):
    return f"{code.lower()}-{slug(deps[code][0])}" if code in deps else "autres"


def ligne_club(c):
    e = html.escape
    return f'<li><a href="/{c["chemin"]}">{e(c["nom"])}</a><small>{e(", ".join(cap(s) for s in c["sports"][:4]))} · {e(c["ville"])}</small></li>'


def presentation_dep(nom, liste, villes):
    compte = {}
    for c in liste:
        for s in c["sports"]:
            compte[s] = compte.get(s, 0) + 1
    principaux = [s for s, _ in sorted(compte.items(), key=lambda x: (-x[1], x[0]))[:5]]
    n = len(liste)
    phrase = (f"{nom} : Paralliance recense {n} club{'s' if n > 1 else ''} de sport qui accueille{'nt' if n > 1 else ''} "
              f"les personnes en situation de handicap")
    if len(villes) > 1:
        phrase += f", dans {len(villes)} communes"
    return phrase + f". Sports les plus proposés : {liste_fr(principaux)}."


def page_departement(code, liste, deps):
    e = html.escape
    nom = nom_dep(code, deps) if code in deps else "Autres départements"
    sports = sorted({s for c in liste for s in c["sports"]})
    villes = sorted({c["ville"] for c in liste if c["ville"]})
    titre = f"Clubs handisport et sport adapté – {nom} | Paralliance"
    desc = (f"{len(liste)} club{'s' if len(liste) > 1 else ''} qui accueillent les personnes en situation de handicap en {nom} : "
            + ", ".join(sports[:6]) + (" et plus" if len(sports) > 6 else "") + ". Liste, carte et fiche de chaque club.")
    corps = (f'<nav class="fil"><a href="/">Accueil</a> › <a href="/clubs/">Clubs</a> › {e(nom)}</nav>'
             f'<h1>Clubs handisport et sport adapté – {e(nom)}</h1>'
             f'<p class="lieu">{len(liste)} club{"s" if len(liste) > 1 else ""} · {e(", ".join(villes[:8]))}{" …" if len(villes) > 8 else ""}</p>'
             f'<p>{e(presentation_dep(nom, liste, villes))}</p>'
             f'<p><a class="btn" href="/#clubs">Rechercher sur la carte</a></p>'
             + blocs_departement(liste))
    return page(titre, desc, f"departements/{deps_slug(code, deps)}.html", corps)


def pluriel(n, mot):
    return f"{n} {mot}{'s' if n > 1 else ''}"


def blocs_departement(liste):
    """Accueil (handisport, sport adapté, handicaps) puis les clubs rangés par sport principal (le premier de la fiche).
    Tout est compté à partir des fiches : rien n'est ajouté."""
    e = html.escape
    blocs = []
    pratiques = {}
    handicaps = {}
    for c in liste:
        if c["pratique"]:
            pratiques[c["pratique"]] = pratiques.get(c["pratique"], 0) + 1
        for h in c["handicaps"]:
            h = HANDICAPS.get(h, h)
            handicaps[h] = handicaps.get(h, 0) + 1
    lignes = []
    if pratiques:
        lignes.append(" · ".join(f"{e(p)} : {pluriel(n, 'club')}" for p, n in sorted(pratiques.items(), key=lambda x: (-x[1], x[0]))))
    if handicaps:
        lignes.append("Handicaps accueillis : " + ", ".join(f"{e(h)} ({pluriel(n, 'club')})" for h, n in sorted(handicaps.items(), key=lambda x: (-x[1], x[0]))))
    if lignes:
        blocs.append('<div class="carte"><h2>Accueil</h2><p>' + "<br>".join(lignes) + "</p></div>")

    if len(liste) < 8:   # peu de clubs : une seule liste
        return "".join(blocs) + f'<div class="carte"><h2>Les clubs</h2><ul class="liste">{"".join(ligne_club(c) for c in liste)}</ul></div>'
    groupes = {}
    for c in liste:
        groupes.setdefault(c["sports"][0] if c["sports"] else "autres sports", []).append(c)
    ordre = sorted(groupes, key=lambda s: (-len(groupes[s]), norm(s)))
    blocs.append('<div class="carte"><h2>Sports proposés</h2><div class="tags">'
                 + "".join(f'<a class="tag" href="#sport-{slug(s)}">{e(cap(s))} ({len(groupes[s])})</a>' for s in ordre) + "</div></div>")
    for s in ordre:
        blocs.append(f'<div class="carte" id="sport-{slug(s)}"><h2>{e(cap(s))} · {pluriel(len(groupes[s]), "club")}</h2>'
                     f'<ul class="liste">{"".join(ligne_club(c) for c in groupes[s])}</ul></div>')
    return "".join(blocs)


def page_index(par_dep, deps, total):
    e = html.escape
    def cle(code):
        return (deps[code][1], deps[code][0]) if code in deps else ("~", "~")
    blocs = []
    for code in sorted(par_dep, key=cle):
        nom = nom_dep(code, deps) if code in deps else "Autres départements"
        liste = par_dep[code]
        blocs.append(f'<div class="carte"><h2><a href="/departements/{deps_slug(code, deps)}.html">{e(nom)}</a> · {len(liste)} club{"s" if len(liste) > 1 else ""}</h2>'
                     f'<ul class="liste cols">{"".join(ligne_club(c) for c in liste)}</ul></div>')
    corps = (f'<nav class="fil"><a href="/">Accueil</a> › Clubs</nav><h1>Tous les clubs parasport en France</h1>'
             f'<p class="lieu">{total} clubs qui accueillent les personnes en situation de handicap, par département.</p>'
             f'<p><a class="btn" href="/#clubs">Rechercher sur la carte</a></p>' + "".join(blocs))
    return page("Tous les clubs handisport et sport adapté en France | Paralliance",
                f"Liste des {total} clubs de sport qui accueillent les personnes en situation de handicap, classés par département : handisport et sport adapté.",
                "clubs/", corps)


def liens_departements(par_dep, deps):
    """Met à jour la liste « Clubs par département » en bas de la page d'accueil (entre deux repères)."""
    chemin = os.path.join(RACINE, "index.html")
    with open(chemin, encoding="utf-8") as f:
        accueil = f.read()
    codes = sorted((k for k in par_dep if k in deps), key=lambda k: norm(deps[k][0]))
    liste = "".join(f'<li><a href="departements/{deps_slug(k, deps)}.html">{html.escape(deps[k][0])}</a></li>' for k in codes)
    nouveau = re.sub(r"(<!-- departements:debut -->).*?(<!-- departements:fin -->)", lambda m: m.group(1) + liste + m.group(2), accueil, flags=re.S)
    if nouveau != accueil:
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(nouveau)


# ===== Écriture =====
def ecrire(chemin, contenu):
    complet = os.path.join(RACINE, chemin)
    os.makedirs(os.path.dirname(complet), exist_ok=True)
    with open(complet, "w", encoding="utf-8") as f:
        f.write(contenu)


def main(fichier=None):
    deps = departements()
    clubs = sorted((club(r, deps) for r in lire_clubs(fichier) if texte(r, "nom")), key=lambda c: (norm(c["nom"]), c["id"]))
    if not clubs:
        sys.exit("Aucun club lu : rien n'est modifié.")   # protège le site si Supabase répond vide par erreur

    # Adresse de chaque page : nom-ville, et l'identifiant si deux clubs ont le même nom dans la même ville
    vus = {}
    for c in clubs:
        base = slug(f'{c["nom"]} {c["ville"]}') or f'club-{c["id"]}'
        c["chemin"] = f"clubs/{base}.html" if base not in vus else f'clubs/{base}-{c["id"]}.html'
        vus[base] = True
    par_dep = {}
    for c in clubs:
        par_dep.setdefault(c["dep"] if c["dep"] in deps else "", []).append(c)

    # On repart de zéro : un club retiré de la base perd sa page
    for dossier in ("clubs", "departements"):
        shutil.rmtree(os.path.join(RACINE, dossier), ignore_errors=True)
    for c in clubs:
        voisins = [v for v in par_dep[c["dep"] if c["dep"] in deps else ""] if v is not c][:8] if c["dep"] in deps else []
        ecrire(c["chemin"], page_club(c, c["chemin"], deps, voisins))
    for code, liste in par_dep.items():
        ecrire(f"departements/{deps_slug(code, deps)}.html", page_departement(code, liste, deps))
    ecrire("clubs/index.html", page_index(par_dep, deps, len(clubs)))

    liens_departements(par_dep, deps)

    # Date de mise à jour de chaque page : celle du dernier vrai changement (empreinte du contenu), pas la date du jour
    aujourdhui = datetime.date.today().isoformat()
    fichier_dates = os.path.join(RACINE, "scripts", "dates_pages.json")
    try:
        anciennes = json.load(open(fichier_dates, encoding="utf-8"))
    except (OSError, ValueError):
        anciennes = {}
    urls = [("", "1.0"), ("clubs/", "0.8")] + [(f"departements/{deps_slug(k, deps)}.html", "0.7") for k in par_dep] + [(c["chemin"], "0.6") for c in clubs if not fiche_mince(c)]
    dates = {}
    for u, _ in urls:
        source = os.path.join(RACINE, u or "index.html", "index.html" if u.endswith("/") else "")
        with open(source.rstrip(os.sep), "rb") as f:
            empreinte = hashlib.sha1(f.read()).hexdigest()
        ancien = anciennes.get(u)
        dates[u] = ancien if ancien and ancien[0] == empreinte else [empreinte, aujourdhui]
    with open(fichier_dates, "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(f"{json.dumps(u)}: {json.dumps(dates[u])}" for u in sorted(dates)) + "\n}\n")
    ecrire("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "".join(f"  <url><loc>{SITE}/{u}</loc><lastmod>{dates[u][1]}</lastmod><priority>{p}</priority></url>\n" for u, p in urls)
           + "</urlset>\n")
    print(f"{len(clubs)} pages clubs, {len(par_dep)} pages départements, sitemap de {len(urls)} adresses.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
