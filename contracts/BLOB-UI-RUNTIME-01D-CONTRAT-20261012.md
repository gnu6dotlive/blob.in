# BLOB-UI-RUNTIME-01D — Contrat de travail borné

**Date : 12 octobre 2026. Mandat opérateur :** « next », suite directe de 01C.
**Repository canonique :** tension-atoi/blob.in-showcase, branche main, privé.
**Baseline :** \`9e324b3ec5a9b6e16dbdbd60e035dd7056d6946f\`.
**Parent normatif :** BLOB-UI-RUNTIME-01 et avenant ratifié de 01A.
**Recevable :** première composition multi-couches du runtime UI, pas P1 complet ni livraison Gnosix.

## Pourquoi 01D

01A–01C qualifient trois contrôles natifs dessinés par \`blobin-ui-scene\` avec identités/layout G02/G03, actions egui propriétaires, et même surface wgpu que la vraie application. Leur liste de peinture restait concaténée à la main, sans contrat indépendant pour composer des couches transformées et clippées, détecter les collisions d'identité, ou refuser une scène dépassant le budget de l'adaptateur (64 commandes).

## Délimitation exécutoire

1. Créer un composeur pur dans \`blobin-ui-scene\` : \`LayerStep\`, \`SceneLayer\`, \`ComposedScene\`, \`compose\`. L'ordre documenté est **inner→outer**, transformation vers parent puis intersection du clip exprimé en coordonnées du parent.
2. Composer **les trois vrais DisplayLists** dans le \`app.rs\` de production, en préservant ordre, G02 \`(SurfaceId,NodeId)\`, révisions, G03 clipping et epoch. Une scène non valide ne doit pas être partiellement soumise au GPU. L'encodeur wgpu reste propriétaire d'une passe et d'un buffer/bind group persistants.
3. Fournir une primitive axis-aligned \`solid_rectangle\` fond plein, coin de rayon zéro, qui refuse clips/géométries invalides et invisible.
4. Qualifier les **12 ancêtres** transformés/clippés sous tests, la collision d'identité, l'ordre et **64 acceptées / 65 rejetées**. La borne 64 est égale à la capacité de l'arène de l'adaptateur; elle n'est pas une politique universelle ni une promesse d'échelle arbitraire.
5. Ajouter un **témoin de charge uniquement de laboratoire** à 55 rectangles, opt-in quand \`BLOB_UI_01D_CAPTURE_DIR\` désigne un dossier existant, \`BLOB_UI_01D_STRESS=1\` et \`WAYLAND_DISPLAY\` commence exactement par \`blob-ui-01d-private-\`. La scène de laboratoire est 3 contrôles produits réels (9 commandes) + 55 commandes de stress = **64** et quatre couches G02 distinctes, rendues par le même swapchain.
6. Capturer les vrais pixels client via \`COPY_SRC\` avant \`queue.present\`, conserver SHA, PNG et gzip sans perte, vérifier 55 centres et points témoins du produit. Weston de test dispose seul des entrées sous user/net namespace privé; jamais l'input Hyprland de l'opérateur.
7. Rerun natif 01A, 01B, 01C depuis le **nouveau binaire**; leurs modes legacy de test doivent empêcher les fixtures antérieures de produire de fausses régressions de layout.
8. Retour direct sur main privé avec commit qualifié et push SHA vérifié. Ne pas nettoyer les worktrees. Préserver les quatre chemins G04B/H préexistants dont le tracked \`blobin_ui_g04b_wayland.rs\` déjà modifié.

## Autorités et anti-contextes

- \`blobin-ui-scene\` ne dépend que de \`blobin-ui-core\`; sans egui, wgpu, GPUI, gnos.ux, thème ou daemon. Aucune copie de sources ArtCraft/GPUI/externe sans accord de licence.
- egui possède encore clavier, focus, pointer et texte du vrai éditeur. Aucun second \`InputRouter\`.
- \`blobin_renderd\` possède les pixels SDF CPU et les workers F4; la nouvelle scène n'exécute pas d'évaluation SDF et ne modifie pas le protocole.
- Le GPU local peint les contrôles et la fixture, **pas** la scène SDF en CUDA. Le renderer réel reste inchangé.
- Rotation arbitraire, skew, arcs Bézier, décorations CSS, SVG, IME/texte autonome, AT-SPI, feedback \`wp_presentation\`, FPS p95/60, cross-vendor, CP03 HYBRID-60, et déploiement de Gnosix sont exclus.
- Une fixture de 55 formes ne prouve **ni** 64 contrôles fonctionnels, **ni** 64 FPS. Seuls trois vrais contrôles sont intégrés.

## Gates de réception

- **G01** HEAD main/origin et preservation G04B/H.
- **G02** dépendances seules \`blobin-ui-core\`, scènes valides/invalides, 12 niveaux d'ancêtres, 64/65 budget.
- **G03** vraie application: trois composants composés via API et attributs G02/G03 préservés.
- **G04** GPU réel : scène 4 couches, 64 draw commands, pas de création de surface/device en doublon; pas de panic validation.
- **G05** Weston privé et vrai \`blobin_renderd\`, deux clics reset idempotent, deux frames SDF CPU uniquement.
- **G06** oracle indépendant 55 pixels centraux + témoins hors fixture, preuves brutes et PNG/sha, négatifs corruption de trace/PNG.
- **G07** anciens bancs 01A/01B/01C rejoués sur nouveau binaire et oracles originaux PASS.
- **G08** rustfmt ciblé, Clippy -D warnings, tests offline workspace et build binaire.
- **G09** rapport, manifeste et intégration spine sans claim P1 complet.
- **G10** commit ciblé + push main privé, vérification SHA identique; fichiers G04B/H hors staging.

**Clôture :** uniquement \`SCOPED_PASS_COMPOSED_NATIVE_UI_AND_64_GPU_COMMANDS\` si toutes les gates PASS. Toute régression ou incertitude donne HOLD avec preuve et sans promotion.
