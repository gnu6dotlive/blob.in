# QCHAIN-CP-C — Oracle indépendant et graphe F4 Vulkan

**Date :** 2026-10-10 · **Branche :** `feat/qchain-scene-frame-protocol-20261010` · **Contrat :** QCHAIN-GPU-EXECUTION-01.

**Verdict borné :** `QCHAIN_F2_F3_F4_VULKAN_BOUNDED_ARTIFACT_PARITY_PASS_HYBRID_F4`.
**Absence de revendication :** aucun PASS d'autonomie GPU F2→F3→F4, aucun nouveau E2E Wayland GPU-source, aucun CP03 HYBRID-60.

## 1. Références et séparation des autorités

- Source canonique inchangée : `/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpu-20261010` @ `493374355172df79b52b8292598ebbdf79a18960`.
- Témoins CPU : `/mnt/workbench/evidence/runs/qchain-cpu-20261010/raw/`; réception canonique `qchain-reconciliation.json`.
- Exécutions F2/F3 réutilisées : `/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpa-cpb-01/`.
- Nouvelle exécution F4 et champs F3 : `/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpc-01/`.
- Comparateurs indépendants : `scripts/qchain_independent_oracle.py` et `scripts/qchain_f3_fields_oracle.py`; aucune importation de code Rust producteur dans ces oracles.
- Sonde de champs GPU : `tools/qchain-f3-probe`; dépend du code F2/F3 canonique en lecture seule et fournit des readbacks machine-readable.

## 2. Matrice observée

| Composant | Couverture | Preuve | Résultat |
|---|---|---|---|
| Canonical CPU | 5 scènes, 21 fichiers | Replay et SHA-256 | EXACT PASS |
| F2 — projection | 5 états Vulkan | Comparaison CPU/GPU PNG + géométrie + identité | BOUNDED PASS : max 1/255 |
| F2 — masque du rendu | 5 états | Seuillage indépendant CPU/GPU | EXACT MATCH entre les deux projections |
| F2 — masque signé vs projection AA | 5 états | Comptage indépendant | 209, 153, 166, 153, 209 pixels distincts **sur les deux backends** |
| F3 — RGBA canonique Ceramic | 5 états | CPU exact vs témoin, GPU vs archive | Différences de 7, 6, 6, 6, 7 octets; max 1/255 |
| F3 — 4 matériaux | 20 cas | Oracle indépendant des PNG et des ledgers | BOUNDED PASS (20/20) |
| F3 — masque de champ | 5 états | Readback GPU binaire vs F2 signé original | EXACT MATCH, 0 pixel divergent |
| F3 — hauteur/chaleur/normal Z | 5 scènes Ceramic | Readback f32, oracles CPU/GPU et budget | BOUNDED PASS, maximum 0.000016272068 |
| F4 — effets | 40 frames, reduced-motion | 4 dispatchs Vulkan par frame, audit des ledgers et PNG | BOUNDED PASS, max 2/255 |
| F4 — canoniques Ceramic frame0 | 5 états | CPU identique à l'archive, GPU vs archive | 7, 11, 11, 11, 7 octets divergents |
| F4 — autonomie entière | Code `F4/src/gpu.rs` | `cpu_mask(scene)` utilisé puis injecté dans les passes | **NOT PASS — HYBRID** |

**Interprétation du masque F2 :** le masque binaire signé de `cpu_mask(scene)` n'est pas le même objet que le masque issu du seuillage d'un rendu anticrénelé. Les divergences comptées ci-dessus sont présentes en CPU et en GPU, ne sont pas une régression spécifique au GPU et ne sont pas masquées par un changement opportuniste de seuil.

## 3. Contrôles négatifs réellement exécutés

`scripts/test_qchain_gpu_oracles.py` : **5/5 PASS**, comprenant contrôle positif d'archive F3 puis refus d'un bit modifié du masque GPU, d'un octet RGBA falsifié, d'un champ numérique NaN et de la substitution du digest de la scène 4 par celui de la scène 0, malgré des contenus visuels identiques.

**Limite :** il s'agit de quatre contre-exemples distincts plus un test positif; les lois N01–N17 du contrat complet ne sont pas toutes exécutées. `G06` ne peut pas être clos.

## 4. Gates et frontières

- `G01` : PASS exact (replay antérieur).
- `G02` : projection topologiquement conforme et parité RGBA bornée; la preuve d'un producteur F2 de **masque signé exact autonome** reste ouverte car F2 GPU produit actuellement la projection AA, non le masque binaire.
- `G03` : F3 Ceramic, masque exact, RGBA et champs f32 bornés indépendamment sur 5 scènes; 20 cas multi-matériaux en comparaison RGB. Des readbacks analytiques par matériau seraient nécessaires pour étendre le claim f32 à 20/20.
- `G04` : graphe existant qualifié en parité bornée sur 40 frames, mais **non autonome** à cause du masque CPU injecté.
- `G05` : provenance calcul GPU observée par logs/adapters/readbacks; classification `HYBRID`. Attestation complète, ownership GPU end-to-end et protocole source restent ouverts.
- `G06` : PARTIAL; `G07–G10` : NOT_RUN.
- Aucun changement au protocole CPU `QCHAIN-FRAME-v1`, à `BLOB-FRAME-v1`, à Hyprland global ou au daemon de production.

## 5. Prochaine séquence autorisée par ce résultat

**CP-D :** isoler le masque signé F2 comme sortie calculée sur GPU, sans reconstruire ni altérer les identités; retirer sa dépendance dans F4 en conservant l'oracle CPU en dehors du chemin de rendu. Définir un vrai lineage de buffers GPU par passe; étendre les tests adversariaux; ensuite seulement envisager le protocole GPU-source et le viewer Wayland.


**Aucune conversion de verdict par analogie :** F4 GPU hybride et présentation CPU-source Wayland déjà qualifiés ne démontrent pas encore la jonction calcul GPU F2→F4→Wayland.
