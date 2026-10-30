# QCHAIN-GPU-EXECUTION-01 — Contrat directeur de qualification GPU et d’intégration native

**Édition :** 1.0 · **Date :** 2026-10-10 · **Langue d’autorité :** français
**Programme :** BLOB-NEXT-01 / Q-CHAIN · **Statut documentaire :** `draft`, proposé à ratification par l’opérateur
**Contexte d’exécution :** Arch Linux / Wayland / Hyprland / NVIDIA RTX 3070 8 Go
**Portée de l’autorisation actuelle :** investigation en lecture seule et rédaction/commit local du contrat; le contrat ne constitue pas, à lui seul, une autorisation de fusionner, publier, déployer ou modifier un runtime résident.
**Documents parents :** `QCHAIN-FRAME-01.md`, `QCHAIN-FRAME-02-WAYLAND.md`, `QCHAIN-FRAME-03-GPU-COMPUTE.md`.
**Convention méthodologique :** `/home/tension_atoi/engineering-corpus/METHOD.md` (édition 0.1-draft, instrument méthodologique, non certification).

## 0. Mandat et finalité

**GOAL.** Démontrer, pour cinq scènes canoniques de 512×384 pixels, que des opérateurs de calcul exécutés réellement sur GPU reproduisent, sous des critères explicites et contrôlés, les sorties sémantiques de F2, les champs et pixels de F3, ainsi que le graphe d’effets F4; acheminer ensuite les frames GPU qualifiées par un transport isolé à une fenêtre Wayland native, et faire corroborer chaque état par un oracle indépendant fondé sur les captures du compositeur.

Ce programme convertit une preuve de **présentation GPU de buffers CPU** en une preuve distincte de **calcul GPU + présentation**. Il ne prétend pas établir la photographie physique de l’écran, la généralité du renderer blob.in, l’équivalence CUDA, la conformité multi-fournisseur, la production, ni CP03 HYBRID-60.

**Succès opératoire minimal :** CPU source et références verrouillés; calcul GPU Vulkan/WGSL identifié et effectivement exécuté; F2/F3/F4 contrôlés individuellement; divergences quantifiées; provenance du frame GPU inviolable au niveau du protocole; cinq captures compositées réconciliées; tests adversariaux RED attendus; replay indépendant; verdict borné, auditable et local.

**Succès supérieur distinct :** parité pixel à pixel et sémantique exacte pour les cinq scènes, ou, si mathématiquement non identique, qualification de tolérance prédéclarée sans jamais la renommer « exact ». Une variante CPU-assistée ou hybride est explicitement admise comme sujet d’étude, jamais comme preuve d’autonomie GPU complète.

## 1. Doctrine de preuve et règles d’autorité

1. `Intent != contract != implementation != proof != public claim`. La documentation exprime un objectif; seul un test exécuté, daté, attribué, inspectable établit un fait.
2. Classes du Corpus Méthodologique : E0 intention, E1 statique, E2 exécutable, E3 mesuré, E4 observé, E5 intégré, E6 exploité. **Ce sont des classes descriptives, non une somme ni une échelle automatique**. Ne jamais convertir une capture ponctuelle en exploitation soutenue.
3. La validité est liée à une identité de source, un arbre Git, une version de shader, une scène, un pilote, un appareil physique, un protocole, un oracle et une fenêtre temporelle.
4. Le composant qui produit un résultat ne peut être l’unique autorité décidant de son PASS. L’oracle vérifie des données originales, pas un statut annoncé par le producteur.
5. E2E réussi et parité mathématique sont des affirmations distinctes. `wgpu.present()` ne prouve ni que les photons ont été observés ni que F2–F4 ont été exécutés sur GPU.
6. Les gates négatifs sont exécutés par mutation contrôlée : RED attendu et identifié = succès du contrôle; rouge imprévu = FAIL; absence d’exécution = NOT_RUN; faux vert = FAIL.
7. La promotion est une opération séparée : document `draft` → revue → adoption opérateur → éventuelle intégration; aucun partage, push, release, publication ou service public implicite.
8. En cas d’ambiguïté concernant l’identité GPU, la sémantique des pixels, les données privées, le protocole ou le scope : **HOLD / fail-closed**.

## 2. État de vérité au gel initial

| Capacité | Autorité observable au 2026-10-10 | Statut maximal acquis |
|---|---|---|
| Source CPU F2→F3→F4, 5 états, 512×384 | Exemple `F4/examples/qchain_cpu.rs` au commit `493374355172df79b52b8292598ebbdf79a18960` | Exécution CPU bornée PASS |
| Scènes canoniques, masques F2, RGBA F3/F4 | `/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw/` | Témoins immuables par empreintes |
| Socket Unix SEQPACKET, même UID, memfd scellé, SHA | `blob-frame/src/qchain.rs` et tests | Transport CPU PASS |
| Cinq frames CPU transférées par wgpu/Vulkan et capturées | `qchain-wayland-20261010-b` | E2E logiciel Wayland PASS avec masque |
| Capture 512×384 complète non masquée | 344 pixels différents aux coins pour chaque scène dans le replay | NOT PASS |
| Réduction GPU de comptage des octets non nuls | `scripts/qchain_cuda_preflight.cu`; 15/15 buffers | Préflight CUDA PASS, aucun calcul F2–F4 |
| GPU F2 projection / F3 calcul et champs / F4 effets | Modules `F2/src/gpu.rs`, `F3/src/gpu.rs`, `F4/src/gpu.rs` et shaders WGSL présents | Implémentation statique identifiée; Q-CHAIN GPU non exécuté |
| F4 GPU, propriété de la topologie | Chemin `F4/src/gpu.rs` lit `cpu_mask(scene)` et transmet le masque | **Chemin hybride observé dans le code**, pas autonome GPU |
| CP03 60 FPS, autres GPU, photons, photoréalisme | Aucune preuve dans la présente quête | OPEN / NOT_RUN |

**Note de couverture critique :** les cinq scènes possèdent cinq `scene_sha256` et cinq digests sémantiques distincts, mais seulement **trois masques F2, trois frames F3 et trois frames F4 binaires distincts** : les couples d’états 0/4 et 1/3 ont des pixels identiques. Le test doit vérifier les cinq identités et la succession des révisions, jamais déduire l’identité d’une scène de son SHA de pixels.

**Correctif explicite à un constat précédent.** La source canonique CPU n’est pas manquante : elle réside dans un autre worktree, retrouvé et inspecté. Le checkout `~/Projects/in.gnu6` n’est pas l’autorité du commit cité dans le témoin CPU.

### 2.1 Sources et chemins autorisés

- **Source canonique en lecture seule :** `/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpu-20261010`, branche `feat/blobin-qchain-cpu-witness-20261010`, HEAD `493374355172df79b52b8292598ebbdf79a18960`, état propre observé.
- **Laboratoires source :** `experiments/blobin-next-01/{F1,F2,F3,F4,F4B,F4C}` sous cette racine. Examiner F4B/F4C en donateurs de mécanismes, pas en remplacement présumé.
- **Intégration Q-CHAIN en écriture bornée :** `/home/tension_atoi/Projects/.worktrees/blobin-showcase-qchain-20261010`, branche `feat/qchain-scene-frame-protocol-20261010`, HEAD avant ce document `4e9678f34ec17e62312420ebf8d517381ce146f1`.
- **Témoins originaux :** `/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw/` et `qchain-reconciliation.json`.
- **Wayland CPU-source :** `/mnt/workbench/evidence/runs/qchain-wayland-20261010-b/`; `compositor-visual-reconciliation.json`; 5/5 captures exactes hors coins.
- **Préflight CUDA :** `/mnt/workbench/evidence/runs/qchain-gpu-preflight-20261010/`; simple réduction témoin.
- **Nouvelle preuve :** `/mnt/workbench/evidence/runs/qchain-gpu-execution-01/<RUN_ID>/`; jamais modifier les preuves précédentes.

L’intégrateur doit recalculer les SHA-256, vérifier l’identité Git source et rejeter tout état modifié ou fixture substitué avant le calcul. Le gel est fait sur des bytes, non sur les noms de fichiers.

## 3. Contrat architectural et sémantique

```text
Scene F2 canonique (IDs, layout, epoch, digest, dimensions) [AUTORITÉ]
  ├─ CPU oracle F2/F3/F4 ------------------------------┐
  └─ GPU F2 projection + GPU F3 + GPU F4 (à qualifier) ├─ comparateur indépendant
                                                      └─ statut exact/tolérance/FAIL
GPU frame qualifié → protocole GPU distinct → memfd scellé → viewer Vulkan blit → Wayland
                                                           └─ capture Hyprland → oracle pixels
```

**F2 — topologie.** IDs gauche/droite, agencement Split/Merged, epoch et digest proviennent de la scène autorisée; un shader ne crée ni ne réécrit une identité. `cpu_mask` et `measure_mask` peuvent servir d’oracle indépendant; utiliser `cpu_mask` comme donnée alimentant le rendu est un calcul hybride qui doit être déclaré. Examiner le shader `F2/shaders/f2.wgsl` avant de décider s’il peut produire directement la projection demandée.

**F3 — matériaux et champs.** Réutiliser d’abord `blobin_f3_material_height::gpu::render`, qui expose RGBA, masque, hauteur, chaleur et normale Z. Vérifier séparément identité des masques, divergence numérique (float32, NaN/Inf, arrondis, ordre des opérations), et pixels issus du GPU. Le simple hash identique de quelques images ne remplace pas les champs numériques.

**F4 — graphe de post-effets.** Respecter l’ordre explicite `shadow → blur → bloom → echo`, le mode `reduced_motion=true` et la sémantique des historiques. `blobin_f4_effects::gpu::process` invoque aujourd’hui F3 GPU mais lit aussi le masque CPU avant les passes Vulkan. Distinguer : (a) F4 GPU calculé avec masque CPU validé, (b) F4 100 % issu d’une projection GPU validée. Ne jamais annoncer (b) sur preuve de (a).

**Chaîne de rendu.** Les pixels d’origine ne changent pas de sémantique en traversant IPC, memfd et texture. Dimensions fixes `512×384`; stride `2048`; RGBA8 `786432` octets; alpha opaque; scene_revision et request_id monotones pour la session. Toute conversion couleur, interpolation, scaling, timing ou coin du compositeur doit être explicitement observé.

**Protocole.** `QCHAIN-FRAME-v1` actuel déclare `SOURCE=qchain-f2-f3-f4-cpu-archive`, `QUALIFICATION=F2_F3_F4_CPU_WITNESS_NOT_WAYLAND`, `gpu_qualified=false`. Ne **jamais** falsifier ces champs. Concevoir un protocole opt-in GPU distinct/versionné et des métadonnées de provenance GPU, avec validations symétriques et tests négatifs; ne pas modifier silencieusement BLOB-FRAME-v1 ou prétendre que le protocole CPU atteste du GPU.

**Isolation.** Aucune interaction avec le démon `blobin_renderd` résident, le socket de production, les services Gnosix, le compositing global, les autres fenêtres ou un déploiement public. Socket dédié en répertoire privé, permissions contrôlées, limites de taille, un frame/source autorisé par requête.

## 4. Politique reuse / adapt / extract / replace

| Capital technique existant | Décision initiale | Motif / test pour changer |
|---|---|---|
| `F2/src/lib.rs` scènes, invariants, qualification_trace | **REUSE** en lecture | Identité canonique et topology oracle |
| `F2/src/gpu.rs` / `f2.wgsl` | **REUSE puis ADAPT** si besoin | Calcul Vulkan déjà présent; prouver sa sortie sur cinq scènes |
| `F3/src/gpu.rs` / `f3.wgsl` | **REUSE** prioritaire | RGBA et champs de comparaison déjà accessibles |
| `F4/src/gpu.rs` / `f4.wgsl` | **REUSE puis ADAPT** | GPU effectif, mais dépendance actuelle à `cpu_mask` |
| `F4B/F4C` gestion résidente / ROI | **EXTRACT seulement après preuve** | Optimisation ultérieure, pas prérequis à la parité |
| `qchain_cpu.rs` et les cinq fixtures | **KEEP IMMUTABLE** | Oracle de référence; ne pas les « corriger » pour passer |
| `QCHAIN-FRAME-v1` CPU et viewer | **KEEP / EXTEND VIA NEW VERSION** | Séparation des métadonnées et des autorités |
| CUDA spécifique | **DEFER** | Ne pas dédoubler WGSL avant mesure d’une incompatibilité ou justification explicite |

Le remplacement est une exception formalisée : incompatibilité démontrée, mesure, risques de régression, comportement à conserver, autorisation de migration et test comparatif. Aucun rewrite total « plus propre » sans nécessité expérimentale.

## 5. Gates de qualification et dépendances

| Gate | Condition exécutable | Preuve exigée | Résultat initial |
|---|---|---|---|
| G00 — identité | Deux HEAD Git, working trees propres, SHA originaux, environnement GPU/driver enregistrés | `inventory.json` et `hashes.sha256` | NOT_RUN dans le nouveau lot |
| G01 — oracle | Rejouer les 5 scènes CPU dans un répertoire vide et comparer chaque sortie binaire au témoin gelé | `cpu-replay.json`, zéro drift | NOT_RUN |
| G02 — F2 GPU | Exécuter le shader F2 et comparer masque/topologie/digest aux témoins indépendants | `f2-gpu.json`, discordances localisées | NOT_RUN |
| G03 — F3 GPU | Calcul F3 réel, champs numériques et RGBA comparés CPU | `f3-gpu.json`, stats et hashes | NOT_RUN |
| G04 — F4 GPU | Quatre passes ordonnées et comportement temporel contrôlés; déclarer toute aide CPU | `f4-gpu.json`, lineage des buffers | NOT_RUN |
| G05 — provenance | Attester où chaque sortie a été calculée, sans fallback CPU silencieux | `compute-lineage.json`, traces dispatch/readback | NOT_RUN |
| G06 — adversarial | Sabotages d’identité, stage, hash, dimensions, GPU, masque de capture | `negative-tests.json` avec refus exact | NOT_RUN |
| G07 — transport | Nouveau contrat opt-in GPU et memfd scellé, bornes/UID/identité vérifiés | `ipc-gpu.json`, tests d’intégrité | NOT_RUN |
| G08 — Wayland | 5 captures GPU-sourcées, géométrie 512×384 et pixels réconciliés | `compositor-gpu.json` et captures privées | NOT_RUN |
| G09 — indépendance | Reconstruction/replay depuis source, vérificateur hors producteur, arbres propres | `replay.json`, logs et verificateur | NOT_RUN |
| G10 — décision | Classement honnête, défauts ouverts, verdict et frontières explicites | `qualification.json` et revue signée localement | NOT_RUN |

**Dépendances :** G00 → G01 → (G02 et G03 après inspection source) → G04 → G05 → G06 → G07 → G08 → G09 → G10. Les lots d’oracle et de tests négatifs peuvent être préparés en parallèle, mais aucun résultat ne peut dépendre d’un succès qui n’existe pas encore.

**Critère d’invalidation transverse :** toute mutation du CPU original, divergence d’identité entre composants, retrait d’un test, défaut de trace, backend inattendu ou oracle auto-validant suspend les PASS dépendants.

## 6. Définition opérationnelle de « parité »

Pour chaque étape i ∈ {0,…,4}, stocker en annexe CPU et GPU : `scene_sha256`, `semantic_digest`, `epoch`, dimensions, format, identités topologiques, champs numériques, SHA de chaque frame, provenance de chaque étape de calcul.

- **Exacte** : égalité des valeurs discrètes (IDs/layout/epoch/components/holes/masque) et égalité intégrale des bytes pour les sorties explicitement déclarées comme exactes; aucune tolérance implicite. Si les flottants font partie du contrat exact, comparer leur représentation binaire en plus de leurs propriétés.
- **Numériquement bornée** : écarts annoncés a priori par champ (absolute/relative/ULP, max et moyenne, distribution, valeurs non finies et coordonnées extrêmes). Un budget non prédéclaré rend le verdict `INCONCLUSIVE`, pas `PASS`.
- **Visuelle** : SHA/RGBA du rendu GPU avant compositeur, puis capture brute séparée; seule l’exclusion documentée des quatre carrés de 18×18 de Hyprland est applicable au témoin actuel. Le masque ne peut pas s’élargir à la volée.
- **Topologique** : un score perceptuel ou une similarité élevée ne peut pas remplacer l’égalité des composantes connexes, cavités et identités de F2.
- **Chaîne GPU** : rapporter explicitement les dépendances au CPU (construction de scènes acceptée, oracle indépendant accepté; `cpu_mask` injecté dans le rendu = hybride). Ne jamais confondre l’exécution WGSL avec CUDA.

**Interdiction absolue :** arranger les images GPU, modifier les références CPU, ignorer les pixels discordants hors masque approuvé ou recalibrer les seuils après observation en réécrivant l’hypothèse originale.

## 7. Décomposition des workers et isolation

| Worker | Autorité limitée et mission | Livraison obligatoire | Dépend de |
|---|---|---|---|
| W00 — Archiviste | Inventaire, HEAD, identité CPU/GPU, SHA, matrice d’accès; lecture seule sur archives | `inventory.json` + registre source | — |
| W01 — Oracle CPU | Rejouer témoin original et garantir indépendance des comparaisons | `cpu-replay.json` + oracle | W00 |
| W02 — Projection F2 | Réutiliser WGSL F2; qualification masque/topologie; aucune autorité de changer IDs | `f2-gpu.json` + tests | W01 |
| W03 — F3 matériel | Réutiliser GPU F3, champs analytiques, pixel-diffs, cas de précision | `f3-gpu.json` + tests | W01 |
| W04 — F4 effets | Réutiliser GPU F4, isoler masques CPU, quatre passes, temporalité | `f4-gpu.json` + trace GPU/CPU | W02,W03 |
| W05 — Protocole | Proposer/implémenter canal GPU distinct, attestation côté producteur/client | `ipc-gpu.json` + tests négatifs | W04 |
| W06 — Surface native | Chaîne viewer → Wayland → capture, sans changement global Hyprland | `compositor-gpu.json` + captures privées | W05 |
| W07 — Auditeur adversarial | Contre-exemples, recomputation indépendante, refus et preuve des failures | `negative-tests.json` + rapport | W01–W06 |
| W08 — Intégrateur | Arbitrage, contrôle des scopes, replay propre, verdict final; aucune fabrication de PASS | `qualification.json` + rapport | Tous |

Une implémentation séquentielle par un seul agent est autorisée uniquement si chaque rôle produit **un artefact distinct, une frontière d’écriture et un oracle distinct**. Ne pas faire du test du producteur le seul observateur du producteur. La parallélisation utilise des worktrees isolés et des répertoires de preuve non partagés en écriture. Le rôle W08 ne corrige pas silencieusement les travaux W02–W07 pendant leur audit.

## 8. Matrice adversariale minimale

| Test | Injection ou situation | Refus requis |
|---|---|---|
| N01 | SHA source changé d’un bit | `SOURCE_IDENTITY_MISMATCH` |
| N02 | Scène substituée mais revision inchangée | `SCENE_BINDING_MISMATCH` |
| N03 | Epoch/revision régressif ou rejoué | `NON_MONOTONIC_SCENE` |
| N04 | ID topologique fabriqué côté GPU | `TOPOLOGY_AUTHORITY_VIOLATION` |
| N05 | Composantes/cavités discordantes | `TOPOLOGY_MISMATCH` |
| N06 | Masque CPU utilisé tout en déclarant `gpu_full_chain=true` | `CPU_ASSIST_MISLABELED` |
| N07 | F3 NaN/Inf ou dépassement de budget annoncé | `F3_NUMERIC_MISMATCH` |
| N08 | Passe F4 absente ou inversée | `EFFECT_GRAPH_MISMATCH` |
| N09 | Temporalité activée malgré `reduced_motion=true` | `TEMPORAL_SEMANTICS_MISMATCH` |
| N10 | GPU indisponible, sélection d’un fallback CPU silencieux | `UNDECLARED_BACKEND_FALLBACK` |
| N11 | Pixel F4 altéré avant IPC, mauvais stride ou alpha | `FRAME_INTEGRITY_FAILED` |
| N12 | FD surnuméraire, non scellé ou peer UID invalide | `MEMFD_OR_PEER_INVALID` |
| N13 | Pixel central altéré dans une capture Wayland | `COMPOSITOR_PIXEL_MISMATCH` |
| N14 | Masque compositeur > quatre carrés 18×18 | `COMPOSITOR_MASK_EXPANSION` |
| N15 | Oracle, fixture ou captures modifiés après signature | `EVIDENCE_TAMPERING` |
| N16 | Aucun retour de GPU, uniquement blit texture | `GPU_COMPUTE_PROVENANCE_MISSING` |
| N17 | Réutiliser les pixels de 0 pour usurper la scène 4 ou de 1 pour usurper 3 | `SEMANTIC_IDENTITY_NOT_PIXEL_IDENTITY` |

Chaque ligne a un test nommé, une mutation, un exit code non nul attendu, un diagnostic reconnu et un statut `INTENTIONAL_RED_PASS` seulement si la mutation est réellement rejetée. L’absence de test interdit le PASS global. Les libellés d’erreur sont contractuels : le code peut les mapper explicitement sans prétendre qu’ils existent déjà.

## 9. Registre d’exécution et exigences d’audit

Chaque exécution crée un nouveau répertoire privé `RUN_ID` non réutilisé, contenant :
- `manifest.json` : identifiant, date, host, device PCI/vendor/device ID si disponible, GPU, driver, Vulkan adapter, versions Rust/wgpu/nvcc le cas échéant, deux HEAD et TREE Git, dirty flags.
- `source-lock.json` : chemins, SHA-256 des cinq fichiers scène et des trois buffers par scène, shaders WGSL et exécutables, identité du CPU oracle.
- `observations/*.json` : sorties machine-readable de G01…G09, provenance, stdout/stderr, codes de retour, exactitude et tolérances distinctes.
- `negative/*.json` : mutations, oracle exécuté, refus, exactitude des attentes et artefacts adversariaux non publiés.
- `private-captures/` : frames PNG originales du compositeur, aucun redessin/retouche; SHA des PNG et RGBA décodés.
- `qualification.json` : résultat de chaque gate (`PASS/FAIL/HOLD/NOT_RUN/INCONCLUSIVE`), preuves liées, limite d’autorité, défauts bloquants et classes E0–E6 justifiées.
- `replay.sh` ou équivalent versionné : commandes reproductibles sur source gelée, sans cacher les préconditions.

**Attribution minimale** de chaque artefact : `producer`, `verifier`, `source_commit`, `run_id`, `sha256`, `input_sha256`, `command`, `exit_code`, `timestamp_utc`, `qualification_scope`. Aucune annotation d’agent ne remplace un log d’exécution.

Ne jamais versionner les captures privées, les gros buffers, les secrets, les sockets ou les fichiers de build. Le manifeste et les schémas expurgés peuvent être commités; leur publication reste une autre décision. Empêcher le partage non intentionnel via `git status` et `git diff --cached`.

## 10. Séquence d’application et points de décision

**CP-A — Provenance / baseline :** W00 et W01 récupèrent toutes les identités, rejouent les cinq frames CPU, consignent les hashes et vérifient que la source et le dépôt intégrateur sont propres. Un arbre producteur sale impose HOLD avant changement.

**CP-B — Reuse audit :** établir un inventaire fonctionnel précis des API GPU F2/F3/F4, signatures, shaders, formats, précision, historique, dépendances CPU et commandes de test. Choisir `REUSE/ADAPT/EXTRACT/REPLACE` par capacité avec justification causale.

**CP-C — Compute séparé :** W02 et W03 exécutent les chemins Vulkan existants sur les cinq scènes; enregistrer l’adapter et le readback. W04 exécute F4, collecte l’ascendance des buffers et vérifie la nature hybride ou autonome du chemin. Les sorties CPU ne deviennent jamais des substituts au kernel.

**CP-D — Oracle / sabotage :** W07 compare toutes les étapes, localise les divergences et exécute les N01–N16 applicables; toute dispense doit être explicitée et le verdict restreint.

**CP-E — Transport :** W05 introduit uniquement le contrat GPU opt-in conforme à son identité de calcul; aucune surcharge du protocole CPU. Tester session, UID, FD, quota, fermeture et sabotage.

**CP-F — Wayland :** W06 capture les cinq frames GPU avec un seul viewer privé; aucune modification de configuration globale; observer capture, géométrie, rendu et écarts hors coins. Préserver les images brutes.

**CP-G — Replay / clôture :** W08 réalise la reconstruction indépendante, consolide ledger et arbre des changements; clôture seulement les gates réellement verts. L’opérateur décide ensuite s’il autorise merge/push, une intégration au showcase usuel ou un nouveau programme CP03.

L’intégrateur peut stopper au premier blocage causal et livrer un diagnostic utilisable. Il ne peut pas annoncer une clôture totale par compensation d’un gate manquant avec un autre gate vert.

## 11. Politique de publication, sécurité et promotion

- **Autorisé ici :** inventaire, travaux isolés dans worktree de quête explicitement autorisé, tests locaux bornés, production de manifests/rapports privés et commits locaux de documents/code du scope.
- **Interdit sans autorisation additionnelle :** merge vers `main`, push GitHub, publication de screenshots, release, installation système, écriture sur le worktree source canonique, changement de services persistants, redémarrage GPU/compositeur, exposition réseau ou élargissement des droits MCP.
- **Confiance :** même UID et memfd scellé sont des propriétés démontrables d’un protocole local, mais ne constituent pas une attestation cryptographique d’un calcul GPU. La provenance dépend aussi du producteur, du code et des traces réellement vérifiées.
- **Distribution/licences :** `blob.in-showcase` a une licence de workspace `LicenseRef-Proprietary`; ne pas déplacer du code F2–F4 vers un autre dépôt/public sans vérifier les droits/licences exacts. Ne pas confondre les orientations OSS d’autres projets avec cette licence.
- **Vie privée :** captures et traces Wayland privées; journaliser sans credentials ni informations de session; aucune intégration involontaire aux surfaces publiques.
- **Promotion :** gate de distribution et d’exploitation séparé de ce contrat; exigera version figée, attribution, revues, décision d’owner, éventuel rollback, observation runtime et conditions de support.

## 12. Classification de sortie

| Verdict possible | Conditions |
|---|---|
| `QCHAIN_GPU_PREFLIGHT_PASS` | Hardware/driver + calcul de contrôle GPU; **ne vaut pas** parité du renderer |
| `QCHAIN_VULKAN_F2_F3_F4_HYBRID_COMPUTE_PASS` | GPU effectivement utilisé, dépendance CPU déclarée, oracle et gates correspondants réussis |
| `QCHAIN_GPU_COMPUTE_EXACT_PARITY_PASS` | Parité exacte F2/F3/F4 sur sorties désignées, source/provenance GPU démontrée |
| `QCHAIN_GPU_COMPUTE_BOUNDED_TOLERANCE_PASS` | Tolérances préalables justifiées, écarts détaillés, aucune revendication d’exactitude |
| `QCHAIN_GPU_WAYLAND_E2E_PASS_CORNER_MASKED` | G07–G09 réussis avec 5/5 scènes GPU-sourcées et masque de capture inchangé |
| `QCHAIN_GPU_FULL_CHAIN_PASS` | Toutes conditions strictes satisfaites, **aucune injection de résultat CPU de rendu sur le chemin GPU** |
| `QCHAIN_HOLD_<REASON>` | Gate incomplet, échec non expliqué, preuve inadéquate ou autorité insuffisante |

Les verdicts sont cumulables uniquement si leurs préconditions indépendantes sont vraies. Un PASS Wayland CPU-source antérieur reste valable, mais il ne peut pas être converti rétroactivement en E2E GPU-source. **CP03 HYBRID-60 reste OPEN**, même si toutes les étapes de ce contrat réussissent : il exige son propre test de performance soutenue et sa propre géométrie de référence.

## 13. Critères d’arrêt et reprise sans perte

**STOP immédiat** si : hash de référence modifié; tree source sale; fuite d’un screenshot; opération demandant accès production; GPU fallback non déclaré; shader incompatible sans preuve; faux vert d’un sabotage; crash driver ou compositor; ressources dépassant l’enveloppe de la quête; confusion entre métadonnées CPU et GPU.

Un STOP produit `blocker.json` (cause, commande, effets, artefacts, portée, rollback nécessaire et prochain test minimal), garde les témoins originaux et ne transforme jamais un FAIL en réussite éditoriale.

**Reprise déterministe :** charger ce contrat et `dispatch.json`; vérifier HEAD/TREE, recalculer les manifests SHA, lire le dernier `qualification.json`; reprendre au premier gate `NOT_RUN/HOLD` dont les dépendances sont vertes. Ne pas requalifier un gate dont les entrées ont changé sans le réexécuter.

## 14. Definition of Done et handoff

Le lot est clôturable si : (1) source et oracles inchangés, (2) périmètre de chaque calcul attesté, (3) cinq scènes testées sans substitution, (4) mesures et exactitudes classées, (5) tous les négatifs applicables rejettent leurs falsifications, (6) captures brutes reliées aux frames GPU, (7) reconstruction reproductible, (8) aucun défaut bloquant caché, (9) preuves privées préservées, (10) décision opérateur explicite avant toute promotion.

**Livrables finaux :** manifeste versionné, ledger de claims, code borné, tests, logs, empreintes, rapport causal, état Git, carte `REUSE/ADAPT/EXTRACT/REPLACE`, dérogations approuvées, plan de rollback et synthèse intelligible des capacités réellement acquises.

**Premier ordre d’exécution du prochain worker :** G00 (inventaire des deux worktrees + hashes), G01 (replay CPU de 5 scènes), puis revue de `F2/F3/F4/src/gpu.rs` et shaders. Ne commencer aucun kernel CUDA nouveau avant d’avoir mesuré les chemins Vulkan existants.
