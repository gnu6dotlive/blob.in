# BLOB-UI-RUNTIME-01G — Chemins fermés convexes et remplissage borné

Date : 2026-10-12. Autorisation : « go » après 01F.
Dépôt privé : tension-atoi/blob.in-showcase ; branche main.
Baseline : 2e898ca52f07a19249c13e9ea12cbdddd929fdf7.
Programme : BLOB-UI-RUNTIME-01, capital 01A–01F conservé.

## Mandat
Passer des segments ouverts à deux familles de primitives graphiques complémentaires : remplissages de polygones **strictement convexes et simples**, et contours fermés à coins arrondis. Le dessin est fait dans le véritable shader wgpu du showcase, non dans une fenêtre artificielle ou un framebuffer logiciel fabriqué.

## Autorités et capacité
- Le core first-party blobin-ui-scene ne dépend que de blobin-ui-core. Aucun nouveau moteur, device, worker SDF, gestionnaire de thème ou route GPU.
- Points ordonnés CW/CCW, 3–16 sommets, convexité stricte, sans trous; vérification des intersections non adjacentes et rejets des étoiles, concavités, NaN, figures dégénérées.
- Un fan déterministe de n−2 commandes FillTriangle pour chaque forme. Gestion des transforms positives et clips G03, provenance NodeId et SurfaceId conservée.
- Un contour fermé à n capsules arrondies; couleur opaque seulement pour éviter le double mélange non qualifié aux joints.
- Shader existant avec branche triangle, classification binaire du fragment; pas d'antialiasing de triangles complets.
- Ordre par couche : rectangles, triangles, traits. Buffer uniforme élargi à 80 octets, stride GPU 256 maintenu, même ressource persistante et même passe.
- Capacité globale 64 commandes. Scène 01G isolée au Weston privé : 9 rectangles des trois vrais contrôles + 17 rectangles laboratoires + 3 triangles de remplissage + 28 segments Bézier hérités + 7 segments de contours = 64.

## Qualification / gates
G01 : HEAD main/origin privé; quatre chemins G04B/H hors staging et inchangés.
G02 : tests core de convexité, winding, intersections, rejet concave/autocroisée, clipping, identités et transformations.
G03 : budget partagé rectangles/triangles/traits : 64 acceptées et 65 rejetées, atomiquement.
G04 : vraie surface Wayland wgpu, triangle pixel shader, même uniform/bind group, aucun panic.
G05 : Weston 15 isolé, deux clics Reset; vrai blobin_renderd CPU réponses SDF [3,4], aucune troisième requête.
G06 : capture GPU client réelle COPY_SRC avant queue.present; oracle des intérieurs et bordures de deux polygones, diagonale interne sans couture, fond noir, 17 formes rouges, 66 échantillons Bézier, témoins 01A/01B. PNG + RGBA gzip et SHA.
G07 : falsifications trace de triangle et PNG rejetées.
G08 : rejouer à neuf les 7 scénarios natifs 01A–01G, sans écraser leurs reçus historiques.
G09 : tests workspace offline, rustfmt ciblé, Clippy strict, dépendance core-only et build.
G10 : documentation et preuves attribuables sur main, commit ciblé, push vérifié local/distant.

## Anti-contextes
Pas de concave, trou, winding SVG, even-odd/non-zero, tessellation de courbes pleines, booleans vectoriels, joints bevel/miter, AA triangle complet, strokes translucides, skew/rotation, texte/IME/AT-SPI natif, remplacement d'egui ou migration GPUI/Gnosix. Ne pas importer de dépendance ou code externe sans licence. Aucune qualification SDF GPU, 60 FPS, feedback compositor ni CP03 HYBRID-60. Le banc artificiel ne doit jamais utiliser l'entrée/capture du bureau Hyprland.

Réception : SCOPED_PASS_CONVEX_CLOSED_PATHS_AND_GPU_FILL uniquement si toutes les gates PASS. Programme parent toujours ouvert.
