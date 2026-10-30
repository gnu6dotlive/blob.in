# BLOB-UI-RUNTIME-01E — Contrat de tracés natifs bornés

**Mandat :** GO après 01D. Dépôt privé tension-atoi/blob.in-showcase, main, baseline 848a2acc6f90cad1062e4153aed14b94d5b77348.

## Résultat attendu
Livrer dans blobin-ui-scene un type StrokeSegment attribuable à G02, une polyline ordonnée de segments droits avec épaisseur et capsules arrondies, et la validation de clips/transformations bornées. Dessiner les segments par un vrai shader wgpu dans la fenêtre de production, sans émuler les lignes par des rectangles. Conserver les trois vrais contrôles et le renderer SDF CPU inchangés.

## Gates
- G01 SHA local/origin, isolation des quatre chemins sales G04B/H.
- G02 dépendance core uniquement, validation de segments dégénérés, NaN, clips vides et limite 64.
- G03 composition et clipping des segments, provenance G02, ordre des commandes, budget rects+strokes.
- G04 wgpu : un shader SDF de capsule et quatre vrais segments dans le même pass/buffer GPU, budget 60 rectangles + 4 strokes (dont 9 rectangles produits).
- G05 vrai Weston privé + renderer CPU : caméra test seule, deux frames réelles, aucun crash; pixels exacts sur quatre points de ligne et témoins hors ligne.
- G06 tests négatifs d'altération de trace et PNG rejetés; capture GPU client originale gzip et PNG SHA.
- G07 rejouer sur le nouveau binaire 01A, 01B, 01C et 01D avec leurs oracles d'origine.
- G08 tests offline workspace, Clippy strict, rustfmt des fichiers possédés et binaire.
- G09 contrat, preuves, Integration Spine; aucune revendication de bézier, join avancé ou accessibilité native.
- G10 commit ciblé main privé, push GitHub et comparaison SHA, G04B/H intacts.

## Anti-contextes
N'introduire aucun vendor GPUI, GPL, ArtCraft, bibliothèque de dessin externe ou thème dans le moteur. Ne pas changer le propriétaire du renderer SDF, l'input egui, le système de fenêtres ni la GPU Queue. Le premier trait est un segment de polyline droit à bout rond : pas de chemins remplis, Bézier, joins paramétrables ou rotation arbitraire. Ne pas prétendre valider FPS 60, présentation par le compositeur, texte/IME/AT-SPI, kernel SDF GPU ou CP03 HYBRID-60.
