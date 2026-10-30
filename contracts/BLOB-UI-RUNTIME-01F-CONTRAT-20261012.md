# BLOB-UI-RUNTIME-01F — Bézier quadratiques et cubiques bornées

**Date : 2026-10-12 · Autorisation opérateur : « continue » après 01E.**
**Dépôt canonique privé :** tension-atoi/blob.in-showcase, branche main.
**Baseline contrôlée :** f7be3d17d6e25fd41d991536b878e7eaeee4f1e6.
**Parent normatif :** BLOB-UI-RUNTIME-01 et les tranches 01A–01E déjà intégrées.

## Mission exécutoire

Introduire dans la scène UI first-party une API de tracé **quadratique et cubique** avec une subdivision déterministe en segments existants. Conserver la provenance G02 de chaque segment, le clipping G03 et le budget global de 64 commandes. Qualifier ses pixels réels dans la fenêtre Wayland existante, sans créer un moteur SDF concurrent ni recopier de bibliothèques tierces.

Les courbes sont approximées **sur CPU en coordonnées logiques**, puis les segments sont réellement dessinés par le shader natif de capsule de 01E sur la même surface wgpu. Il s'agit d'un centre de contour avec bouts arrondis; pas d'un path fill, d'un Bézier GPU analytique ou d'une jonction vectorielle complète.

## Politique de tessellation

- Algorithme **De Casteljau à t=1/2**, récursif, ordre gauche puis droite, subdivisions reproductibles en f32.
- Critère d'arrêt : tous les points de contrôle sont à au plus \`tolerance\` du segment droit, conformément à la propriété de l'enveloppe convexe.
- Tolérance entre 0,125 et 8 pixels **logiques avant transformations**, valeur de démonstration 0,75.
- Profondeur maximale 12; capacité maximale 64 segments par courbe, et plafond de composition 64 commandes **rectangles et segments cumulés**.
- Entrées non finies, segments dégénérés, échelles invalides, profondeur/capacité/tolérance dépassées : refus sans sortie partielle. Les segments restent attribuables au même \`NodeId\`.
- La tolérance logique n'est pas une borne indépendante du DPR ou des transforms d'échelle non uniforme; la géométrie n'implique pas une couverture analytique exacte des joints.

## Qualificatifs de sortie

G01 — HEAD/origin/main privé et inventaire des quatre chemins G04B/H non intégrés, conservés byte-identiques.

G02 — Tests purement Rust \`blobin-ui-scene\` : quadratique/cubique, collinéar, sources et order, borne de distance par référence Bernstein indépendante (257 samples par courbe), données invalides, capacité et subdivision.

G03 — Les courbes deviennent de vrais \`StrokeSegment\` réutilisant \`DisplayList.strokes\`, \`composition::compose\`, les clips et le même shader de segments 01E; pas de code externe.

G04 — Banc Wayland isolé uniquement sur la socket \`blob-ui-01f-private-*\`, répertoire de capture existant et opt-in \`BLOB_UI_01F_STRESS=1\`. Le produit conserve ses trois contrôles réels (9 commandes); le laboratoire ajoute 27 rectangles de charge et 28 segments de deux courbes = 64 commandes, quatre couches G02 distinctes.

G05 — Vrai \`blobin_renderd\` CPU, caméra non standard injectée **uniquement dans le banc privé**, deux clics Reset avec un seul changement effectif; exactement deux requêtes et deux frames SDF CPU, sans nouvelle requête au second clic.

G06 — Capture vraie de pixels du framebuffer wgpu client (COPY_SRC avant queue.present) et oracle indépendant : 66 samples des équations Bernstein (33 par courbe), 27 centres de rectangles, témoins noirs et témoins 01A/01B, archives PNG et RGBA gzip byte-identiques et SHA attribuables.

G07 — Deux falsifications distinctes (nombre de segments altéré dans les traces et PNG altéré) systématiquement rejetées.

G08 — Replay **natif frais des six scénarios 01A/01B/01C/01D/01E/01F** avec les oracles correspondants; préservation des reçus historiques.

G09 — Tests workspace offline, rustfmt ciblé, clippy -D warnings, construction du binaire réel, barrière de dépendances core-only pour la scène.

G10 — Contrat, qualification, index de programme, source et preuves dans un commit ciblé sur \`main\` privé; push et comparaison de SHA local/remote; G04B/H restent hors staging.

## Frontières et exclusions

- Pas de remplissage de courbes, gestion complète de joints/caps, auto-intersections, path booleans, winding rules, rotation/skew génériques, cache de tessellation, texte/IME/AT-SPI natif ou substitution d'egui.
- Pas d'import GPUI, ArtCraft, code GPL ni bibliothèque de path externe; code first-party, palette/transforms fournis par les consommateurs.
- Aucun shader SDF CPU/CUDA, scheduler, BLOB-FRAME ou protocole modifié; l'UI utilise son pipeline séparé sur la surface de production déjà existante.
- Les pixels capturés **ne prouvent pas** la présentation du compositeur ni les FPS physiques, les p95, les performances AMD/Intel, la résidence GPU SDF ni CP03 HYBRID-60.
- La fixture 01F n'apparaît jamais dans la session Hyprland réelle; aucun pointeur du bureau opérateur n'est injecté.
- P1/BLOB-UI-RUNTIME-01 global demeure ouvert après 01F, même si toutes les gates 01F passent.

**Statut exécutoire :** 01F seulement; aucun autre chantier autorisé implicitement.
