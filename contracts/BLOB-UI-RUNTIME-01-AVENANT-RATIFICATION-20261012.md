# BLOB-UI-RUNTIME-01 — Avenant de ratification et autorisation bornée 01A

**12 octobre 2026 — RATIFIÉ PAR L'OPÉRATEUR — EXECUTION 01A UNIQUEMENT**

Parent normatif préservé mot pour mot : BLOB-UI-RUNTIME-01_Contrat_de_travail_2026-10-12.md, dans le présent dossier contracts.
Il reste marqué PROPOSITION parce qu'il restitue le texte original. **Cet avenant matérialise la ratification**, sans réécriture rétrospective.

**Baseline de lancement :** tension-atoi/blob.in-showcase, main privé, commit 798796dc8f7f78ca34234e5c8901242b2834d1ce. AC-05 est déjà intégré : le parent pré-AC05 à f364c69 doit être considéré comme historique.
AC-05 conserve SCOPED PASS pour l'exécution CPU SDF capturée, et HOLD pour le nouvel orchestrateur de replay.

## Autorisation 01A

Migrer dans le vrai éditeur la représentation graphique du toggle **Contours de contrôle (G)** : état canonique réel Model.overlay: bool, G02 snapshot persistant, G03 layout et clip, nouvelle display-list neutre indépendante d'egui, même surface wgpu existante.
Le fond, le contour et le pouce deviennent dessinés par blob.in; **l'entrée/focus et le texte demeurent egui-owned**, sans routeur concurrent.
Une action native doit changer le state et les pixels du toggle sans demander de nouvelle frame SDF.
Retour arrière explicite BLOB_UI_01A_LEGACY=1 vers le checkbox egui d'origine. Palette fournie par l'application cliente et non codée dans le core.

## Invariants et exclusions

1. Pas de donneur GPL importé, pas de sources ArtCraft ou Gnosix/GPUI copiées, pas de changement de licence implicitement autorisé.
2. Aucun changement de propriété du renderer SDF, de ses shaders/threads, du scheduler F4 ou de BLOB-FRAME.
3. Réutiliser l'existant UI-G02/G03/G04 et AC01–05; ne pas reconstruire ni doubler les responsables.
4. Une seule surface GPU, une seule fenêtre, le même swapchain; le pass UI peut utiliser Load après egui, avec clip attribué.
5. Pas de capture du bureau personnel. Readback autorisé uniquement sur le socket Weston blob-ui-01a-private-* dans un namespace isolé, à la demande.
6. Conserver intacts les quatre chemins G04B/H locaux non intégrés. Aucun nettoyage de worktree.
7. P1/P2/P3, runtime UI autonome, texte/IME, AT-SPI, 60 FPS, GPU SDF et CP03 HYBRID-60 non ratifiés ni acceptés par 01A.
8. Intégrer seulement les fichiers possédés par 01A sur main privé avec un commit ciblé et push GitHub vérifié.

## Gates de réception 01A

- G01 : SHA local/distant, origine privée, inventaire des chemins sales, provenance, droits.
- G02 : scène UI indépendante d'egui/wgpu, identité G02 stable, layout/clip/DPR/epoch G03, tests.
- G03 : composant réel, une seule action, bonne sémantique état/visuel, repli egui.
- G04 : commandes réellement soumises en pass wgpu sur la surface native déjà propriétaire.
- G05 : Weston privé et vrai blobin_renderd CPU, clic réellement livré, révision UI 1→2, une seule requête/frame SDF.
- G06 : oracle réel de pixels client avant/après, points témoins inchangés, rejets de traces falsifiées.
- G07 : rustfmt ciblé, Clippy strict, tests core/crate/ensemble, binaire compilé offline.
- G08 : preuves, integration spine, commit et push privés, SHA remote identique.

**Clôture éventuelle :** SCOPED PASS du contrôle uniquement. Le programme BLOB-UI-RUNTIME-01 reste OPEN jusqu'aux autres phases requises.
