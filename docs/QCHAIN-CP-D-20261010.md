# QCHAIN CP-D — GPU topology independence · qualification bornée

**Date :** 2026-10-10 · **Contrat :** QCHAIN-GPU-EXECUTION-01
**État :** `QCHAIN_CPD_GPU_SIGNED_MASK_EXACT_F4_GPU_HYBRID_HOST_BRIDGE_PASS`
**Intégration de surface :** non exécutée. **Production et CP03 :** ouvertes.

## Autorités Git isolées

- Source d'origine immuable : `in-gnu6-qchain-cpu-20261010`, `493374355172df79b52b8292598ebbdf79a18960`; aucun changement au checkout.
- Nouvelle branche d'implémentation isolée : `feat/blobin-qchain-gpu-topology-20261010` @ **`c270ca32790597049b59ccba77d1694fa4a439f7`**.
- Branche d'oracle indépendante : `feat/qchain-scene-frame-protocol-20261010` (repo blob.in-showcase), source CPU inchangée.
- Preuves privées : `/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpd-gpu-mask-01/`.

## Travaux apportés

1. F2 fournit `gpu::render_signed_mask(scene)` avec un point d'entrée WGSL distinct `mask_main`, calculant directement le masque binaire du champ signé (0/1). La projection RGBA antialiasée existante n'est pas requalifiée comme masque signé.
2. F4 n'importe et n'appelle plus `cpu_mask(scene)` dans son chemin GPU. Il reçoit le masque F2 GPU, le vérifie contre le masque calculé sur GPU par F3, vérifie la topologie sur l'hôte et transfère ces bytes GPU-derived dans son graphe Vulkan.
3. Les métadonnées expérimentales F4 déclarent `F2_GPU_SIGNED_MASK_VULKAN_READBACK_REUPLOAD`. Aucune revendication zéro-copie ou résidence intégrale GPU; le protocole externe CPU `QCHAIN-FRAME-v1` reste inchangé.
4. Une sonde de F2 produit cinq masques GPU et un registre des identités; un oracle Python séparé confronte les fichiers d'origine, les masques F3 GPU et les 40 images F4 GPU à leur baseline.

## Mesures et contrôles

| Contrôle | Résultat réellement exécuté |
|---|---|
| F2 masque signé WGSL | 5/5 EXACT, **0 bit divergent** vs F2 CPU |
| F2/F3 GPU mask | 5/5 binaires identiques |
| F4 calcul Vulkan | 40/40 frames; 4 dispatchs de post-effets chacune |
| Rendu GPU après suppression du masque CPU | **40/40 sorties binaires-identiques** à la baseline GPU antérieure |
| F4 CPU/GPU | Parité bornée; max canal RGB 2/255 |
| Reduced motion | Temporal reset CPU/GPU aligné sur 40/40 frames |
| Audit indépendant | `QCHAIN_CPD_GPU_SIGNED_MASK_EXACT_F4_GPU_HYBRID_HOST_BRIDGE_PASS` |
| Tests négatifs ciblés | 5 mutations adversariales rejetées + contrôle positif, 6/6 tests PASS |
| GPU Vulkan indisponible via ICD invalide | Refus non nul, aucune sortie faussement qualifiée |
| Rust F2/F4 | `cargo test --offline` PASS |
| Clippy F2/F4 | `--all-targets -- -D warnings` PASS |

## Sources de preuve

- `f2-mask-run.log`, `f2-mask/gpu-f2-mask-ledger.tsv`, `f2-mask/scene-XX.gpu-f2-mask.bin`.
- `f4-run.log`, `f4/ledger-dpr2-reducedtrue.tsv`, images GPU privées.
- `independent-cpd.json`, `cpd-adversarial.log`, `fault-no-gpu.log`.
- `f2-rust-tests.log`, `f4-rust-tests.log`, `f2-clippy.log`, `f4-clippy.log`.
- Code de vérification : `scripts/qchain_cpd_oracle.py`, `scripts/test_qchain_cpd_oracle.py`.

## Classification et frontières d'autorité

- **PASS strict :** GPU F2 est effectivement auteur du masque binaire utilisé dans F4, conforme pixel à pixel à F2 CPU; disparition de la dépendance de rasterisation CPU du chemin F4 GPU.
- **PASS borné :** F4 conserve sa sortie GPU antérieure sur 40/40 cas et satisfait le budget numérique de la comparaison CPU.
- **Non acquis :** GPU-resident zero-copy; GPU-only topological verification; canal GPU-source versionné et scellé; E2E GPU-source → Wayland; 17/17 lois adversariales; CP03 HYBRID-60; qualification cross-vendor et photonique.
- **Détail causal :** F2 et F3 calculent leurs données sur GPU; le host lit leurs buffers, vérifie l'identité/topologie et réexpédie les buffers à F4, qui a son propre device Vulkan. Le CPU reste contrôleur d'identité et d'intégrité, non fournisseur du masque.
- Aucun push, merge, déploiement, changement résident ou publication d'images.

## Next

**CP-E** : réduire les transferts inter-devices et readbacks par le partage d'un contexte GPU F2/F3/F4; maintenir des oracles CPU séparés; étendre la falsification, puis ouvrir une version expérimentale du canal GPU-source Wayland.
