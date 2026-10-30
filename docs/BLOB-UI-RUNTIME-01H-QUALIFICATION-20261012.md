# BLOB-UI-RUNTIME-01H — Qualification de géométrie concave et cadre troué

Contrat : contracts/BLOB-UI-RUNTIME-01H-CONTRAT-20261012.md
Vérifier : python3 scripts/blob_ui01h_verify.py
Reçu : evidence/runs/blob-ui-runtime-01h-20261012/qualification.json
Image native originale : evidence/runs/blob-ui-runtime-01h-20261012/native/concave-hole.png

Le noyau neutre blobin-ui-scene ajoute la triangulation ear clipping de polygones simples concaves (au plus 16 sommets, CW/CCW) et une construction dédiée au **rectangle contenant un seul trou rectangulaire strictement inclus**. Les triangles conservent le même type G02/G03/wgpu que 01G : pas de texture artificielle, pas de rectangle noir ajouté pour masquer un trou.

Le banc vrai Wayland Weston isolé dessine un L bleu et un cadre rose avec son trou noir. L'éditeur comprend toujours trois contrôles fonctionnels. Le nombre de commandes composées est 54 (14 rectangles dont 9 production, 12 triangles, 28 strokes Bézier), inférieur au plafond 64. La vraie capture du framebuffer client est faite par COPY_SRC avant queue.present. Le vrai blobin_renderd CPU sert les deux révisions [3,4] avec un reset idempotent.

L'oracle vérifie le plein du L, sa découpe vide, les quatre bandes du cadre, son trou resté transparent, l'arrière-plan, les 66 échantillons Bézier, les cinq rectangles laboratoire et les témoins des contrôles 01A/01B. Deux falsifications de trace et PNG sont rejetées. Les bancs natifs 01A–01G sont rejoués frais en plus du banc 01H et les anciens reçus demeurent.

LIMITES : aucun trou dans un polygone concave arbitraire, aucun winding SVG, aucune forme multi-trou ou auto-intersectée; antialiasing complet des bords de triangles **OPEN**. Pas de latence/FPS, GPU SDF, compositor presentation, texte/IME natifs, ni CP03 HYBRID-60 qualifié. Travail G04B/H non committé préservé.
