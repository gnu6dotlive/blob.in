# BLOB-UI-RUNTIME-01I — EvenOdd rectangulaire et couverture AA bornée

Date : 2026-10-12. Autorisation : « go » après 01H.
Dépôt privé tension-atoi/blob.in-showcase. Baseline main : 23fb6755d5f315991ae1af87b33dcbd735c5410a.

## Objectif
Qualifier un ensemble explicite de deux trous rectangulaires disjoints dans un contour extérieur rectangulaire, avec une règle de membership de type EvenOdd pour cet ensemble restreint, et un antialiasing par couverture des **seules arêtes externes** des triangles. Préserver intégralement le rendu historique (01A–01H) en conservant le nouveau mode de shader opt-in et exclusivement autorisé dans le Weston privé.

## Approche et invariants
- Une primitive first-party fill_rectangular_even_odd(source,outer,holes,clip,color). Au plus deux trous, non chevauchants et strictement inclus; tri par X/Y des frontières, tuiles rectangulaires et deux triangles par cellule non située dans un trou.
- Toute superposition de trous, dépassement du contour, dimension non finie ou capacité de 64 triangles dépassée donne un refus atomique, et aucun pixel de cache n'est projeté.
- Cette règle *EvenOdd* est **restreinte aux contours rectangulaires sans intersection**. Elle ne généralise pas les contours SVG, l'orientation arbitraire, les courbes, les formes auto-intersectées ou plusieurs niveaux de trous.
- AA : dans le shader WGSL existant, comparer les arêtes de chaque triangle aux arêtes des triangles d'une même liste/provenance/couleur. Désactiver la couverture sur les arêtes partagées; utiliser une fonction de couverture analytique sur les autres, avec une bande de garde d'un pixel logique sur le quadrilatère couvrant chaque triangle.
- Ne jamais créer de nouvelle fenêtre, device, pipeline, BindGroup, système d'entrée, daemon SDF, shader kernel GPU SDF. Même limite totale 64 commandes wgpu. Egui demeure propriétaire du texte et des clics.
- **Le chemin AA n'est activé que par BLOB_UI_01I_CAPTURE_DIR + BLOB_UI_01I_AA=1 + la socket privée blob-ui-01i-private-*.** En mode normal, 01A–01H gardent le shader binaire antérieur et leurs tests de pixel exacts.

## Gates de réception
G01 main/origin synchrones; G04B/H préservés sans staging.
G02 tests core-only EvenOdd rectangulaire 0/1/2 trous avec ordre déterministe, rejets des trous superposés, extérieurs ou invalides.
G03 capacité partagée et maintien G02/G03, coût borné; 42 triangles dans le banc et 9 commandes des trois vrais contrôles = 51.
G04 vrai wgpu sur Wayland isolé, aucune erreur shader/validation. Shader AA spécifique aux bords externes, 1 pass et ressources persistantes.
G05 oracle indépendant du buffer GPU (COPY_SRC avant present) validant points de remplissage, centres vides des 2 trous, pixels de couverture **fractionnaire** de frontières internes/externes et absence de coutures sur diagonales internes.
G06 vrai renderer SDF CPU avec exactement deux requêtes/réponses [3,4] pendant deux clics Weston, dont le second idempotent.
G07 deux falsifications (trace de triangles, PNG) rejetées.
G08 tests complets Rust workspace, rustfmt ciblé, Clippy -D warnings, build offline; dépendances core-only.
G09 rejouer **neuf scénarios Wayland natifs 01A–01I**, nouveaux sièges Weston et oracles originaux, sans modifier les reçus historiques.
G10 intégrer contrat, qualification, preuves PNG/rgba gzip SHA, registre de reproductibilité et mise à jour de la spine.
G11 commit ciblé, push GitHub privé et SHA local=origin/main ; G04B/H inchangés.

## Hors périmètre et anti-contexte
AA analytique testé sur des arêtes de polygones rectilignes dans des conditions bornées. La couture GPU du triangulateur est qualifiée seulement aux points de preuve, pas pour la totalité des résolutions/échelles. Ni GPU MSAA complet, ni chemins Bézier remplis, trous non rectangulaires, spirales auto-intersectées, winding rule SVG complète, stencil path engine, gradient, texture, texte/IME, accessibilité native, présentation wgpu->compositeur validée, FPS 60 ou CP03 HYBRID-60. N'importer aucune dépendance externe. Ne pas modifier les sources ou preuves du chantier parallèle G04B/H.

Le programme BLOB-UI-RUNTIME-01 demeure OPEN. Un résultat 01I ne promeut ni Gnosix, ni GPUI ni la promesse d'un renderer UI complet.
