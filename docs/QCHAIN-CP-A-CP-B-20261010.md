# QCHAIN CP-A / CP-B — Qualification exécutée sur RTX 3070

**Date :** 2026-10-10. **Contrat :** QCHAIN-GPU-EXECUTION-01. **Nature :** baseline locale bornée, non publication.

## Provenance
- Source originale read-only : `/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpu-20261010` @ `493374355172df79b52b8292598ebbdf79a18960`.
- Intégrateur : `feat/qchain-scene-frame-protocol-20261010`, contrat initial `2ec0ab69b35ee7eaaf7af53745fecc81497f064b`.
- GPU : NVIDIA RTX 3070 8 GiB, pilote 615.78.08, wgpu 30.0.1 / Vulkan / WGSL.
- Dossier de preuves privé : `/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpa-cpb-01/`.
- Les deux worktrees étaient propres au préflight; la source canonique n'a pas été modifiée.

## CP-A — CPU replay
- Rebuild de l'exemple original `F4/examples/qchain_cpu.rs` sur le commit canonique.
- Résultat : 21/21 fichiers reconstruits identiques par SHA-256 au dossier source gelé; cinq scènes, masques F2, frames F3/F4 et ledger.
- **G01 : PASS (replay exact de la fixture)**. G00 : provenance essentielle vérifiée, inventaire machine-readable complet non encore clos.

## CP-B — Vulkan
- Exécution réelle de `F2/src/main.rs` avec `--backend compare --dpr 2` sur cinq états. Backend reporté : NVIDIA / Vulkan / DiscreteGpu. Topologie et transitions conformes. Maximum d'écart de canal : **1/255**; maximum de moyenne absolue mesurée par état : **0.000003**. **Parité bornée PASS selon les seuils préexistants du laboratoire**, et non égalité binaire.
- Exécution réelle de `F3/src/main.rs` avec `--backend compare --dpr 2 --heat 0.62` sur cinq états et quatre matériaux (20 cas). Backend `gpu` sans fallback dans le ledger. Maximum de différence RGBA : **1/255**; maximum absolu parmi hauteur/chaleur/normale Z : **0.0000163**. Masques/topologies conformes. **Parité bornée PASS selon les seuils préexistants du laboratoire**, et non égalité binaire.
- Limite importante : le chemin existant exécute sa propre séquence `qualification_trace`; les paramètres coïncident avec ceux du témoin Q-CHAIN, mais un oracle indépendant dédié de chaque buffer GPU contre les fixtures archivées reste à implémenter pour fermer strictement G02/G03 au titre du contrat directeur.
- F4 GPU non exécuté dans cette campagne. Protocole GPU, sabotage N01–N17, captures GPU-sourcées, replay tiers et CP03 : NOT_RUN / OPEN.

## Commandes de reproduction
```sh
S=/mnt/workbench/workspaces/gnu.in.labs/.worktrees/in-gnu6-qchain-cpu-20261010/experiments/blobin-next-01
R=/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpa-cpb-01
CARGO_TARGET_DIR=/mnt/workbench/build/blobin-f1-target cargo run --offline --manifest-path "$S/F4/Cargo.toml" --example qchain_cpu -- "$R/cpu-replay"
CARGO_TARGET_DIR=/mnt/workbench/build/blobin-f1-target cargo run --offline --manifest-path "$S/F2/Cargo.toml" -- --backend compare --dpr 2 --out "$R/f2"
CARGO_TARGET_DIR=/mnt/workbench/build/blobin-f1-target cargo run --offline --manifest-path "$S/F3/Cargo.toml" -- --backend compare --dpr 2 --heat 0.62 --out "$R/f3"
```
Pour un replay ultérieur, utiliser un **nouveau dossier vide** : ne pas écraser les preuves ci-dessus.

## Décision
**CP-A CPU witness replay : PASS. CP-B F2/F3 Vulkan laboratory bounded parity : PASS.**

**G02 et G03 du contrat directeur : INCOMPLETE** tant qu'un oracle indépendant liant chaque sortie GPU à son identité canonique et ses buffers Q-CHAIN d'origine n'est pas produit. Ne pas promouvoir vers la chaîne complète, ni vers `QCHAIN_GPU_COMPUTE_EXACT_PARITY_PASS`.
