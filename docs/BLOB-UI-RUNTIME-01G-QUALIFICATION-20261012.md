# BLOB-UI-RUNTIME-01G — Qualification native des chemins fermés convexes

Date : 2026-10-12.
Contrat : contracts/BLOB-UI-RUNTIME-01G-CONTRAT-20261012.md
Vérification : python3 scripts/blob_ui01g_verify.py
Reçu : evidence/runs/blob-ui-runtime-01g-20261012/qualification.json
Image réelle : evidence/runs/blob-ui-runtime-01g-20261012/native/convex-closed-paths.png

## Capital technique
La bibliothèque blobin-ui-scene inclut FillTriangle, fill_convex_path et stroke_closed_convex_path (3–16 sommets strictement convexes, sans auto-intersections, ordre CW ou CCW). Triangulation fan déterministe; vérifications d'identité G02, clip et transform positif G03, plafond partagé 64. Les intersections non adjacentes sont rejetées explicitement. Les contours sont des capsules rondes opaques, pas un stroke SVG universel.

L'adaptateur wgpu actuel a une troisième branche shader, qui dessine les triangles avec signe des arêtes. Le buffer uniforme persistant lie 80 octets par commande sur un stride dynamique 256; un seul pipeline, une passe, aucun nouveau GPU. Les triangles ont un masque binaire sans AA complet. L'ordre est rectangles puis triangles puis traits, et le rendu appartient à la vraie fenêtre showcase.

## Acquisition et pixels
Weston headless privé, son propre seat et le vrai blobin_renderd CPU. Les vrais contrôles restent interactifs. Le banc limité à la socket privée dessine un carré rempli bleu avec bord orange et un triangle rempli magenta avec bord orange. Traces : 26 rectangles (dont 9 de vrais contrôles), 3 triangles, 35 segments (7 fermés et 28 Bézier), quatre couches, 64 commandes. Deux clics Reset et deux frames SDF CPU [3,4]; pas d'autre rerender.

Capture vraie du framebuffer client 1280 × 800 avant queue.present et archivage sans perte PNG + RGBA gzip. Oracle indépendant : pixels des deux intérieurs, contour, coins et diagonale de fan sans couture, arrière-plan noir, 17 centres rouges, 66 positions Bernstein de 01F et deux témoins de contrôles. Rejet de traces ou PNG falsifiés. Les six anciennes familles 01A–01F sont rejouées depuis le nouveau binaire dans leurs Weston privés.

## Limites
Aucun chemin concave, auto-intersecté ou troué n'est accepté. Aucun remplissage Bézier, winding SVG, joints miter/bevel, transparence de contour, AA complet triangle, saisie IME ou compatibilité universelle GPUI. La sortie COPYSRC du client ne qualifie ni photons/compositeur ni FPS. CPU SDF uniquement; CUDA, CP03 HYBRID-60 et runtime global restent ouverts. G04B/H hors intervention.
