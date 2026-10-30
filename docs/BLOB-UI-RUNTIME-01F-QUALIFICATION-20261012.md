# BLOB-UI-RUNTIME-01F — Qualification Bézier CPU → segments → wgpu

**Date :** 2026-10-12.
**Contrat :** \`contracts/BLOB-UI-RUNTIME-01F-CONTRAT-20261012.md\`.
**Vérification intégrale :** \`python3 scripts/blob_ui01f_verify.py\`.
**Reçu :** \`evidence/runs/blob-ui-runtime-01f-20261012/qualification.json\`.
**Pixels natifs :** \`evidence/runs/blob-ui-runtime-01f-20261012/native/bezier-curves.png\`.

## Code effectivement acquis

Dans \`crates/blobin-ui-scene/src/bezier.rs\`, \`BezierCurve::Quadratic/Cubic\` et \`stroke_bezier\` convertissent une courbe de centre de contour en segments droits en utilisant De Casteljau (t=1/2) et un critère de platitude sur la distance des points de contrôle au segment droit. L'algorithme est déterministe, borné à 12 niveaux et 64 segments, et refuse les valeurs non finies, capacités, courbes dégénérées ou tolérances non valides.

La display-list, le compositeur G02/G03 et le renderer wgpu ne changent pas de propriétaire. Les segments résultants sont de **vrais traits** dessinés par le shader de capsule de 01E, non une image ou une approximation par rectangles. Aucune dépendance supplémentaire n'est importée dans le core.

## Mesure du témoin natif

Le vrai \`blobin-showcase\` et \`blobin_renderd\` CPU s'exécutent dans une session Weston isolée. La fixture opt-in crée une Bézier quadratique et une cubique (tolérance = 0,75 pixel logique), produisant ensemble **28 segments**. Le calque de laboratoire ajoute 27 rectangles, auxquels s'ajoutent 9 commandes des trois vrais contrôles : total **36 rectangles + 28 segments = 64 commandes**, quatre couches.

Deux clics de la souris virtuelle Weston sur Réinitialiser génèrent une seule transition effective de caméra, avec seulement deux révisions et frames SDF CPU [3,4]. Le framebuffer client 1280×800 est copié dans un buffer réel wgpu avant \`queue.present\` et conservé sans perte en PNG et en RGBA gzip. L'oracle fait les comparaisons **indépendamment du code Rust du moteur** : 33 positions Bernstein par courbe (66 points de couleur exacte), 27 centres de rectangles, plusieurs échantillons vides et les deux contrôles historiques. Des fichiers et traces modifiés doivent être rejetés.

Les oracles 01A–01E sont ensuite exécutés avec leurs propres sièges Weston isolés sur le nouveau binaire, en plus de la vérification des archives historiques. Le vérificateur enregistre les commandes, journaux, SHA des sources et preuves et vérifie la conservation byte-à-byte des travaux G04B/H non intégrés.

## Frontières de qualification

Le centre de courbe est subdivisé en segments CPU. La largeur est rendue comme des capsules arrondies par wgpu; la qualité des joints et des extrémités à chaque subdivision n'est pas équivalente à une stroking engine SVG. La tolérance s'applique avant transformations, en pixels logiques. Aucun Bézier analytique GPU, remplissage de path, rendu texte/IME autonome, accessibilité native ou métrique de présentation par le compositeur n'est revendiqué.

**01F ne démontre pas** 60 FPS, CP03 HYBRID-60, GPU SDF, AMD/Intel, un renderer UI autonome complet ou la migration de Gnosix/GPUI. Le programme parent BLOB-UI-RUNTIME-01 reste OPEN.

**Prochaine option après réception seulement :** caractériser la qualité des joints, supports de paths multi-segments et fills à winding explicite, séparément des questions de texte/IME et mesure de présentation.
