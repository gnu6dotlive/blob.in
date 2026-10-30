# BLOB-UI-RUNTIME-01C — Qualification et registre de capitalisation

**Baseline** : 62eee74c2fd601e8dadf6a2d8fd638ef6b510b26
**Contrat** : contracts/BLOB-UI-RUNTIME-01C-CONTRAT-20261012.md
**Qualification** : evidence/runs/blob-ui-runtime-01c-20261012/qualification.json
**Rejouer la vérification** : python3 scripts/blob_ui01c_verify.py

## Changements fonctionnels
`blobin-ui-scene` expose `UiTransform2D` (translation et échelle positive strictement finies) ainsi que `transform_and_clip` (intersection de clips ancêtres et transformations de rects/rayons), avec conservation de l'identité `source_node`, `source_ui_revision`, `surface` et `layout_epoch`. Rotation, skew, typographie et clip courbe restent exclus.

Le troisième contrôle réel de la colonne Vue, **Réinitialiser**, utilise `NativeResetHost`, `ControlLayoutHost` G02/G03 et `action_button`. Il partage avec « Distance » et « Contours » la passe wgpu et le buffer GPU déjà résidents. Son action est traitée une seule fois par egui : si la caméra diffère de `Camera::default()`, réinitialisation et invalidation du scheduler; si la caméra est déjà normale, aucun changement de révision. L'ancienne version egui est disponible via `BLOB_UI_01C_LEGACY=1`.

## Observation native
Sous Weston headless privé avec socket `blob-ui-01c-private-*` et namespace utilisateur/réseau indépendant : caméra testée (cx=0.18, cy=-0.12, zoom=1.45) → clic sur Réinitialiser → caméra par défaut. Deuxième clic identique = no-op. Une requête CPU SDF initiale, une requête due au premier reset, **aucune troisième**. Deux clients GPU pixels de 1280×800 enregistrés avant `queue.present` avec PNG et buffers originaux RGBA compressés. Trois surfaces G02 distinctes et neuf commandes dans la passe UI unique. Le bouton est légèrement décalé en X lorsque le libellé zoom raccourcit; l'oracle valide la taille 94×26 et les bounds dynamiques, au lieu de figer sa position.

Les géométries SHA du vrai renderer sont distinctes, car la caméra modifie la projection passée au runtime. L'oracle réfute les traces modifiées et les PNG corrompus. Les banques 01A et 01B sont rejouées sur le nouveau code avec leurs modes legacy appropriés et requalifiées par les anciens oracles.

## Bornes
Les captures sont des pixels de l'application cliente, **pas** des accusés de présentation du compositeur. Le runtime SDF fonctionne en CPU; GPU SDF, métriques p95/60 FPS, accessibilité native, texte/IME et autonomie Gnosix restent ouverts. Le helper de transformation ne donne aucune prise de possession du renderer, de GPUI ni du design system. Aucune source externe n'a été vendored.

**Suite proposée : 01D**, trajectoire vers une liste de rendu plus générique avec composition de transforms, clips profonds et rendu de plusieurs composants sous charge, puis qualification de comportements texte/focus/IME par étapes.
