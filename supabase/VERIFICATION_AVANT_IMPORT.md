# Vérification avant chaque import de clubs

Règle : aucun import tant que cette fiche n'est pas remplie pour la source. En cas de doute, on demande l'autorisation.

## 1. Qui publie ?

| Éditeur | Règle par défaut |
|---|---|
| Administration : État, préfecture, région, département, mairie, établissement public | Réutilisation libre en citant la source et la date (code des relations entre le public et l'administration, art. L321-1 et L322-1), sauf mention contraire |
| Association : CDOS, comité handisport ou sport adapté, ligue, fédération | Accord écrit nécessaire, sauf licence ouverte affichée |
| Entreprise ou particulier | Accord écrit nécessaire |

## 2. Ce qu'on regarde sur la source

1. Les mentions légales, les conditions d'utilisation ou la page « licence » du site.
2. Le document lui-même : une licence (Licence Ouverte / Etalab, ODbL, Creative Commons), « reproduction interdite », « tous droits réservés », « diffusion libre ».
3. S'il existe une version en données ouvertes (data.gouv.fr ou portail open data de la collectivité) : on la préfère, elle a une licence claire.

## 3. Décision

- Licence ouverte, ou administration sans interdiction : on importe, on cite la source en bas de page.
- « Reproduction interdite », « tous droits réservés » ou « sauf autorisation » : on n'importe pas sans accord écrit.
- Association ou entreprise sans aucune mention : on n'importe pas (pas de demande d'accord par mail).
- Document de plus de 3 ans : on n'importe pas, même si c'est autorisé.

## 4. Dans tous les cas

- Pas de nom de personne, pas de mail personnel.
- La source est citée en bas de page (rubrique « Sources »).
- On garde une capture des mentions légales ou de l'accord écrit, avec la date.

## Registre des sources

| Source | Éditeur | Ce qui autorise la réutilisation | Vérifié le |
|---|---|---|---|
| Doubs (plateforme Oz) | Département | Licence ODbL | avant cette règle |
| Côtes-d'Armor (guide 2019-2021) | Département | Administration (CRPA) | avant cette règle |
| Bouches-du-Rhône (clubs labellisés) | Département | Administration (CRPA) | avant cette règle |
| Eure (clubs labellisés, février 2025) | CDOS 27 (association), liste relayée par la préfecture | Gardé (décision d'octobre 2026), retrait immédiat sur demande | avant cette règle |
| Haute-Garonne (annuaire 2025-2026) | Comité handisport 31 (association) | Aucune mention : gardé (décision d'octobre 2026), retrait immédiat sur demande | avant cette règle |
| Calvados (annuaire 2025) | CDOS 14 (association) | Aucune mention : gardé (décision d'octobre 2026), retrait immédiat sur demande | avant cette règle |
| Savoie (livret 2025-2026) | CDOS 73 (association) | Aucune mention et pas de demande d'accord : non importé (retiré, voir 11_retrait_savoie.sql) | octobre 2026 |
| Nouvelle-Aquitaine (plateforme régionale) | CROS Nouvelle-Aquitaine (association) | « Reproduction interdite sauf autorisation » : refusé sans accord | octobre 2026 |
| Lyon (réseau Sport-Santé Adapté Handicap) | Métropole de Lyon (administration) | Licence Ouverte 2.0 sur data.gouv.fr / data.grandlyon.com, fiches de 2025 | octobre 2026 |
| Côtes-d'Armor (données ouvertes datarmor) | Département | Licence Ouverte 2.0, mais saison 2016/2017 : trop ancien, non importé | octobre 2026 |
| Bordeaux Métropole (lieux de pratique des APA) | Bordeaux Métropole | Licence Ouverte, mais surtout résidences seniors et sport-santé, sans type de handicap : non importé | octobre 2026 |
| Paris (réseau des clubs paraccueillants) | Ville de Paris | CGU paris.fr : « toute reproduction est conditionnée à l'accord de la Ville » : non importé | octobre 2026 |
| Annuaires d'associations de Nantes, Orléans, Angers | Métropoles (administrations) | Licence Ouverte 2.0 (Nantes, Orléans), ODbL (Angers) ; seules les associations qui décrivent elles-mêmes une pratique pour les personnes handicapées ; Nantes : fiches mises à jour depuis moins de 3 ans | octobre 2026 |
| Annuaires d'associations de Lorient, Meudon, Issy-les-Moulineaux | Villes (administrations) | Licence Ouverte ; fiches 2024-2026 ; seules les associations qui décrivent elles-mêmes une pratique pour les personnes handicapées | octobre 2026 |
| Répertoire SIRENE (recherche-entreprises.api.gouv.fr) | INSEE / État | Licence Ouverte : sert seulement à découvrir des noms de clubs ; chaque fiche est remplie depuis la page officielle du club (clubs_verifies.py). Essai Paris (2 clubs) : non importé, décision d'octobre 2026 | octobre 2026 |
| Répertoire national des associations (RNA, fichier du 1er octobre 2026) | Ministère de l'Intérieur (administration) | Licence Ouverte (fr-lo) sur data.gouv.fr : réutilisation libre en citant la source et la date. Seules les associations actives, dont le dernier dossier en préfecture date de moins de 3 ans et dont l'objet déclaré annonce une pratique pour les personnes handicapées ; chaque fiche relue une par une (rna_relecture.json, avec la raison de chaque refus). Ni adresse, ni dirigeant : seulement la commune du siège. Collectivités d'outre-mer mises de côté (le site ne gère que les départements) | novembre 2026 |

## Méthode « club par club » (sans liste d'un tiers)

On peut ajouter un club trouvé par nous-mêmes si ses informations viennent de son propre site ou de sa page officielle,
et seulement s'il y dit lui-même accueillir des personnes en situation de handicap. On ne suit jamais la liste d'un tiers
ligne par ligne (cela revient à copier sa base de données). Google Maps peut aider à découvrir un club, jamais servir de source.
