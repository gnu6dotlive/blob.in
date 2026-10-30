# BLOB-UI-RUNTIME-01H — Concavité et trou rectangulaire borné

Date 2026-10-12. Mandat opérateur : « Go » après 01G.
Baseline dépôt privé tension-atoi/blob.in-showcase/main : 9633e8820ab90aa968a599d2d1e88102ab575a08.

## Mandat
Étendre de façon vérifiable la géométrie native de blob.in aux polygones simples concaves, avec triangulation ear clipping déterministe, et aux trous rectangulaires strictement intérieurs à un contour rectangulaire. Rejeter les cas que la qualification ne couvre pas. Conserver l'ownership egui pour l'entrée et le texte, wgpu pour le pipeline UI existant et blobin_renderd pour le renderer SDF. Aucune substitution de GPUI/Gnosix.

## Capacité autorisée
- fill_simple_polygon : 3 à 16 sommets simples, CW/CCW, non collinéaires; détection des intersections non adjacentes, ear clipping ordonné et atomique, n−2 triangles.
- fill_rectangular_frame : un rectangle extérieur et un rectangle intérieur strictement inclus; 4 bandes disjointes formant 8 triangles. Centre du trou **non peint**, pas masqué par une couleur artificielle.
- FillTriangle de 01G réutilisé, source NodeId, surface G02, transforms et clips G03; compte dans les mêmes 64 commandes GPU.
- Banc réel Wayland Weston privé avec 3 contrôles interactifs historiques, 5 rectangles de laboratoire, 28 segments courbes et 12 triangles : **54 commandes**, sous limite.
- Scanner les pixels réellement lus du swapchain client : dedans/hors du L concave, cadre rose et trou non rempli, témoins antérieurs, traces SDF CPU; rejeter deux corruptions de preuve.

## Gates
G01 main = origin et empreintes G04B/H inchangées.
G02 core tests géométriques, concave CW/CCW, auto-intersectés, dégénérés, contraintes de trou.
G03 intégration des triangles dans composition existante, refus de dépasser 64 commandes, garantie fail-closed.
G04 Weston artificiel dans namespace privé, vraie app wgpu et vrai blobin_renderd CPU.
G05 oracle GPU indépendant du shader, géométrie du L et cadre creux + 66 points Bézier et contrôles.
G06 PNG et source RGBA gzip originaux, SHA, rejets de trace/PNG altérés.
G07 requalification native des huit jalons 01A–01H sur binaire reconstruit.
G08 rustfmt, Clippy strict, tests offline workspace, build, registre des preuves.
G09 commit ciblé sur main privé, push, contrôle SHA distant, G04B/H préservés.

## Exclusions et vérité
Pas de trous généraux dans des polygones arbitraires, pas de plusieurs trous, pas de winding even-odd/nonzero, pas de formes étoilées, pas de self-intersections, pas de SVG paths complets. L'AA des bords triangles et des coutures **reste non qualifié**, malgré le shader actuel. Aucun renderer SDF modifié; GPU SDF, HID physique, retour wp_presentation, 60FPS et CP03 HYBRID-60 sont OPEN. Cette tranche ne termine pas P1 et ne rend pas GPUI obsolète.

Un problème dans l'une de ces preuves impose HOLD et interdit un claim PASS. En cas de succès, seulement SCOPED_PASS_SIMPLE_CONCAVE_AND_RECT_FRAME_HOLE.
