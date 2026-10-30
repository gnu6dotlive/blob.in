
# blob.in — Réconciliation du capital de rendu, autorité et suite d'intégration

**Date :** 12 octobre 2026. **Contrat :** `contracts/BLOB-RENDER-RECONCILE-01-CONTRAT-20261012.md`.
**Baseline :** `blob.in-showcase/main` à `d2903f0a53d648a739f4cabdf03d3842577108e9`.
**Rejouer :** `python3 scripts/blob_render_reconcile01_audit.py`.
**Manifest SHA :** `evidence/runs/blob-render-reconcile-01-20261012/source-reconciliation.json`.
**Verdict :** `SCOPED_PASS_READ_ONLY_SOURCE_RECONCILIATION`, **aucun runtime 3D intégré ni merge réalisé**.

## 1. Résultat de la récupération

Nous avions effectivement plusieurs moteurs de rendu. Ils ne sont pas perdus.

Les six worktrees d'origine F1, F2, F3, F4, F4B et F4C possèdent désormais un fichier `.git` pointant vers une arborescence Git absente; ils ne sont donc pas des branches directement opérationnelles. Cependant, le worktree CP01 encore attaché à Git possède **six copies strictement identiques des sources**, cinq fichiers Rust/WGSL/Cargo par module : 30 fichiers correspondants, SHA-256 identiques. Le registre enregistre leurs SHA individuels, les chemins et les différences (aucune).

Branches propres et vérifiées :
- CP01-HYBRID : `ddd723329b1d0b07d7a827dc8776d8a2535c21b5`.
- CP02-VULKAN : `5d2b5bdc65cbd60109060401a6f655714bd165fa`. Le reçu GPU00 archivé pointe sur le commit antérieur `6bc46ccfa587d6fe71e98010a417097e3c518133`, encore accessible depuis cette branche.
- Produit showcase : `main` privé au commit ci-dessus. Le code F1–F4C n'est pas une dépendance de son client.
- `in.gnu6/main` n'expose pas actuellement F1–F4C sous `experiments/blobin-next-01`. **Le worktree CP01 est le point de récupération concret, pas les liens `.git` cassés.**

## 2. Matrice d'autorité et de réutilisation

| Source | Ce qui existe et est vérifié | Autorité | Décision |
|---|---|---|---|
| **F1** | `FrameIr`, signed field, rendu 2D offscreen et références CPU/GPU | Production de contenu image | Référence d'interface, pas renderer concurrent dans UI |
| **F2** | `Engine`, `Scene`, `TopologyEvent`, `Split/Merge/PunchHole/SealHole`, hit-test des objets | Sémantique/topologie/epoch du **contenu** | **Premier candidat R02** : adaptateur typé de scène et de frames |
| **F3** | Heightfield, heat, normales, quatre matériaux céramique/gel/métal/papier | Matière et relief du **contenu** | Pass optionnel du moteur de contenu; ne possède pas palette UI |
| **F4** | Passes shadow, box blur, bloom, temporal echo | Effets GPU sur contenu | Réutilisation sous même contrat de buffer, espace colorimétrique et durée de vie |
| **F4B** | Repli GPU/CPU et transfert/damage de région | Résilience bornée de laboratoire | Revoir contre device réel résident; ne prouve pas zéro rendu full-frame |
| **F4C** | Graph incrémental GPU pour régions affectées; source F3, upload et readback encore plein cadre | Damage des **effets** | R03 après intégration du flux réel; aucune prétention d'end-to-end zero-idle |
| **CP01** | Maillages triangulés importés, solides signés bornés, BVH, prisme non convexe, CSG mixte CPU | Géométrie 3D et oracle indépendant | R04 distinct pour capacités 3D GPU |
| **CP02** | Probes Vulkan et surface triangulaire; preuve GPU00 historique distincte | Calcul matériel borné | R04 validation de calculs 3D, pas une qualification de rendu 3D final |
| **GPU-05 / QCHAIN** | WSI, compositor et instrumentation de présentation sur d'autres scènes | Oracles et transport/pacing | Réutiliser l'instrumentation, pas les FPS comme verdict CP03 |
| **UI 01A–01I** | G02/G03, scènes natives 2D, vrais contrôles, composition wgpu | Interface produit : input/focus UI, layout, dessin des contrôles | **Conserver** séparément du contenu F2/F3/F4C |

**Conflit à éviter :** F2 possède les identifiants et hit-tests des blobs; G02 possède ceux des composants d'interface. Ne pas les fusionner en un espace d'identité implicite, ni intégrer les crates de calcul dans la bibliothèque renderer-agnostique `blobin-ui-scene`.

## 3. Tests frais exécutés pendant cette tranche

Tests avec `cargo test --offline --locked` et cible externe `/mnt/workbench/build/blobin-reconciliation-01` :

| Module | Résultat | Qualification limitée |
|---|---|---|
| CP01-HYBRID | **56 tests PASS** | Géométrie 3D, import, BVH, CSG référentiel CPU; pas de nouvelle présentation GPU |
| F2 | **7 tests PASS** | Scène topologique et invariants, sans adoption de l'UI |
| F4C | **5 tests PASS** | Invalidation d'effets et oracle CPU; pas de gain global de cadence |
| CP02-VULKAN | **Cargo test/build PASS, 0 tests exécutés** | Compilation actuelle uniquement, **pas de nouvel essai Vulkan physique** |

Les logs du run sont archivés **dans le dépôt privé** sous `evidence/runs/blob-render-reconcile-01-20261012/logs/` (ainsi que sous `/mnt/workbench/evidence/runs/blob-render-reconcile-01-20261012/`), avec SHA-256 dans le manifeste. Les sources donneuses restent externes et privées. Les preuves GPU antérieures sont historiques et n'ont pas été réexécutées. Les tests natifs UI 01A–01I ne sont pas réexécutés dans cet audit read-only.

## 4. Architecture cible R02 (proposée, NON implémentée)

**Ne pas faire un merge brut de F1–F4C dans `blobin-ui-scene`.** La chaîne a des modèles et propriétés de buffers distincts. Le client actuel a déjà BLOB-FRAME-v1 et une surface winit/wgpu, tandis que F3/F4 restent largement offscreen.

L'adaptation proposée a deux contrats de données, sans deuxième propriétaire de surface :

- `SemanticSceneRef` (proposé) : ID de scène de **contenu**, topology_epoch, digest de contenu, viewport en pixels physiques, DPR, provenance source, événements F2. **Aucun ID de contenu ne se confond avec un NodeId G02.**
- `ContentFrameRef` (proposé) : frame_id, epoch source, digest sémantique, étendue, format RGBA et alpha, convention linéaire/sRGB, damage rect, auteur GPU/CPU et lien avec les accusés BLOB-FRAME-v1 existants. Le serveur de contenu possède la génération, le showcase possède la fenêtre/device/present; UI G02/G03 conserve l'entrée/paint des contrôles.
- Matériaux F3 et effets F4/F4C restent opt-in derrière le contenu, avec epochs et espaces colorimétriques explicités. Aucune allocation d'un device GPU par frame de produit.
- **E2E R02 :** exercer une vraie transaction F2 `PunchHole` puis `SealHole`, vérifier IDs/topologie et hit-test indépendants, transporter un frame réel vers l'unique fenêtre native, faire le matching scène→frame→pixel→input et rejeter traces falsifiées. Les passes F3/F4 sont une étape optionnelle **après** preuve du flux F2.
- **R03 :** qualification résidente GPU et incrémentalité de bout en bout, avec sources/upload/damage/readback, p95 et fallback réel.
- **R04 :** CP01/CP02 3D comme programme distinct; mesh clos/ouvert, vrais booléens hybrides, rendu 1280×720, oracle et feedback; aucun raccourci vers CP03.

Ce découpage évite de refaire les primitives déjà qualifiées et traite enfin le problème de **faire consommer le capital moteur par une interface produit réelle**.

## 5. Licence et séparation public/privé

Le `Cargo.toml` du showcase déclare **`LicenseRef-Proprietary`**. Les manifestes F1–F4C trouvés possèdent `publish=false`, mais **pas de champ `license`**. Leur historique clean-room, même original, n'équivaut pas à une autorisation de redistribution MIT. L'ancien donneur blob.in est aussi décrit dans le préflight CP03 comme GPL/AGPL-ambigu.

Aucune licence n'est changée par cet audit. **Avant R02**, il faut confirmer la propriété et les licences des fichiers donneurs, l'autorisation de copie dans un autre dépôt et le statut public ou privé. Si cette autorisation manque, construire un nouvel adaptateur à partir des concepts et comportements déjà qualifiés, sans vendorer les fichiers.

## 6. Firewall CP03

Le programme CP03 reste **NOT_QUALIFIED** : sa scène normative `HYBRID-HERO-60@1` doit montrer simultanément SDF/CSG GPU, maillages triangulés fermé et ouvert, booléen 3D mixte, transforms, input, rendu Vulkan/Wayland **1280×720**, feedback de présentation et cadence réelle soutenue sur 120 s. Les preuves CP01, CP02, F2–F4C et GPU-05 concernent des scènes différentes. Leur regroupement administratif **ne constitue pas** une réussite CP03.

**Décision opérationnelle :** sources récupérées et contrôlées, aucun autre renderer à réinventer immédiatement. Démarrer **R02**, l'adaptateur sémantique privé F2→flux BLOB-FRAME en contexte réel, une fois l'autorité de source/licence levée.
