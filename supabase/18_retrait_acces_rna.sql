-- Lot 3 (Répertoire national des associations) : vide la rubrique « Accès » des clubs importés.
-- Le texte « Objet déclaré par l'association… » ne disait rien de l'accès aux lieux (fauteuil, vestiaires, parking).
-- Seules les fiches dont le texte n'a pas été modifié depuis l'import sont touchées.
update public.clubs
set accessibilite = null
where source = 'Répertoire national des associations (ministère de l''Intérieur), octobre 2026, Licence Ouverte'
  and accessibilite like 'Objet déclaré par l''association au Répertoire national des associations%';
