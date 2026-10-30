# BLOB-UI-RUNTIME-01C — Contrat borné, 12 octobre 2026

**Mandat :** « go » après 01B intégré. Dépôt canonique privé tension-atoi/blob.in-showcase, baseline main `62eee74c2fd601e8dadf6a2d8fd638ef6b510b26`.

## Objectif vérifiable
Étendre la scène 2D native neutre de blob.in à la translation et la mise à l'échelle strictement positive, avec clipping multi-ancêtres; brancher un troisième contrôle de production `Réinitialiser` dans la section Vue; prouver qu'une caméra non standard revient à son état par défaut avec une invalidation SDF unique et que le second clic est idempotent. Réutiliser sans refaire UI-G02/G03 et la passe wgpu mutualisée de 01B.

## Propriété et exclusions
L'état caméra, les gestes et le renderer SDF appartiennent toujours au showcase et au runtime BLOB-FRAME. egui conserve l'entrée, le focus, le texte. Palette fournie par `theme.rs`. Le nouveau `UiTransform2D` ne couvre que sx/sy positifs et tx/ty finis; rotation, skew, courbes Bézier et pipeline texte sont hors scope. Pas d'import ArtCraft/GPL, aucun vendor externe. Ni nouveau GPU device ni fenêtre; six à neuf commandes peintes par le même adaptateur. Aucun accès à l'entrée Hyprland personnelle, l'instrumentation Weston reste isolée. Les quatre chemins G04B/H sales préexistants demeurent hors commit.

## Plan
- G01 : SHA main et origine privée, inventaire des changements concurrents;
- G02 : transformations bornées et clipping hiérarchique, rejects NaN/Inf/échelle inversée et invisibilité; tests sur identité G02 et état G03;
- G03 : troisième hôte de contrôle sur surface G02 0x010C, display list via l'adaptateur partagé, rollback `BLOB_UI_01C_LEGACY`;
- G04 : test par vrais callbacks egui : reset effectif, une seule invalidation, reclic sans modification, 01A/01B indépendants;
- G05 : vrai binaire Wayland avec wgpu, trois listes/nœuds neuf commandes, aucun changement de propriétaire SDF;
- G06 : Weston privé user+network namespace, deux clics Réinitialiser, deux frames CPU SDF seulement (initiale et première action), témoin camera state;
- G07 : pixels originaux GPU de la surface client avant/après reset et oracle indépendant; conserver PNG et RGBA gzip sans perte, SHA et traces;
- G08 : refus vérifié des captures ou traces falsifiées;
- G09 : rejouer réellement 01A et 01B sous leurs modes compatibilité avec oracles d'origine;
- G10 : tests workspace, rustfmt ciblé, Clippy strict, build offline et registre attribuable;
- G11 : intégration dans la spine, contrat et preuves; staging ciblé;
- G12 : commit puis push vers `main` privé, contrôle SHA distant et conservation des modifications G04B/H.

## Clauses de vérité
Le helper `transform_and_clip` intervient sur une display-list déjà construite et retourne une autre liste avec bounds, clipping et rayons ajustés; il ne constitue **pas** un moteur d'affine complet. Le rendu natif montre la vraie surface wgpu et le renderer CPU, **pas** la confirmation `wp_presentation` du compositeur ni une qualification GPU SDF, 60 FPS ou CP03 HYBRID-60. 01C constitue une incrémentation utile de P1, **pas** la clôture du programme BLOB-UI-RUNTIME-01.

Un état caméra non standard peut être injecté **uniquement** pendant le banc Weston privé via `BLOB_UI_01C_CAPTURE_DIR` et le nom de socket `blob-ui-01c-private-*`; jamais dans la session utilisateur.
