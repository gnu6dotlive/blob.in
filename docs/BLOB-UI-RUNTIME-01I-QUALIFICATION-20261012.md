# BLOB-UI-RUNTIME-01I — Qualification AA et deux trous rectangulaires

Date : 2026-10-12.
Contrat : contracts/BLOB-UI-RUNTIME-01I-CONTRAT-20261012.md.
Reproduction : python3 scripts/blob_ui01i_verify.py.
Registre : evidence/runs/blob-ui-runtime-01i-20261012/qualification.json.
Capture Wayland originale : evidence/runs/blob-ui-runtime-01i-20261012/native/two-holes-aa.png.

## Ce qui est effectivement acquis
Le core blobin-ui-scene ajoute fill_rectangular_even_odd, une grille déterministe de cellules entre les frontières d'un contour rectangulaire et d'au plus deux trous rectangulaires disjoints. L'intérieur de ces trous n'est **jamais triangulé**, de sorte que le framebuffer sous-jacent est préservé. Les mêmes FillTriangle et mêmes identités G02/G03 continuent à être consommés par le pipeline existant.

Dans la seule configuration Weston privée 01I, le renderer wgpu traite les arêtes externes par une couverture analytique smoothstep, utilise une garde d'un pixel logique et **omet les arêtes partagées** entre triangles (comparaison par points/couleurs/source). Les versions 01A–01H conservent leur chemin shader historique; le mode est désactivé en production et ne prétend pas constituer un antialiasing universel.

## Résultat du banc
La capture 1280×800 sur vrai swapchain client montre deux ouvertures non peintes à l'intérieur d'un cadre coloré. Composition : 42 triangles, plus neuf commandes des trois vrais contrôles, soit 51 commandes; quatre couches G02 sur le même appareil GPU. Le vrai blobin_renderd CPU sert deux frames aux révisions [3,4]. Les événements egress et les captures du compositor n'ont pas été utilisés pour fabriquer les pixels.

L'oracle indépendant vérifie des points de remplissage, de transparence, cinq pixels de couverture partielle sur les bords extérieurs et les bords des trous, ainsi que plusieurs points sur des diagonales internes qui conservent le plein. Les deux types de falsifications de source (trace et PNG) doivent échouer. Le PNG est reconstruit à partir du vrai buffer RGBA gzip et lié à son SHA.

## Limitations
Seuls deux trous rectangulaires disjoints, strictement intérieurs, sont pris en charge. Le shader analytique couvre une sélection de bords droits, avec une propriété de continuité vérifiée à certains points; pas de garantie de qualité générale aux transforms, DPR différents, courbes, jointures complexes ou régions auto-intersectées. Ce n'est pas la règle EvenOdd SVG pour des chemins arbitraires. Le rendu SDF demeure CPU, le GPU ne fait que le dessin des composants UI. Aucune preuve de wp_presentation, FPS/p95, performance physique, IME/texte autonome ou CP03 HYBRID-60. BLOB-UI-RUNTIME-01 et Gnosix restent OPEN.

Les travaux parallèles G04B/H non intégrés sont protégés.
