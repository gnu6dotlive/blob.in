# QCHAIN CP-F — Persistent GPU Session

**Date :** 10 octobre 2026. **Contrat :** QCHAIN-GPU-EXECUTION-01.
**Branche source :** `feat/blobin-qchain-persistent-session-20261010`.
**Parent :** CP-E `2e72b6c`.

## GOAL

Une même session Vulkan conserve un device, trois compute pipelines
et cinq buffers de stockage GPU entre les frames, tout en exécutant
F2→F3→F4 dans un seul graphe par frame.

## Qualifications

- **40/40** frames sur RTX 3070 via une seule `PersistentSession`.
- **51/51** artefacts de référence CP-E binaires-identiques.
- **5/5** masques GPU F2 et buffers analytiques F3 inchangés.
- Six dispatchs et une soumission par frame; aucun transfert CPU intermédiaire.
- Validation stricte des epochs, digests et géométries de session.

## Preuves et oracles

Dossier privé :
`/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/`.

- `compute.log` : cinq étapes, compteurs de session 1, 9, 17, 25, 33.
- `raw/` : 52 fichiers, incluant `session-stats.tsv`.
- `independent-reconciliation.json` : oracle Python exact (51/51).
- `adversarial.log` : cinq falsifications rejetées, un positif.
- `no-gpu.log` : refus de démarrage sans Vulkan, aucun fallback.
- `rust-tests.log` / `clippy.log` : contrôles de code.
- Programme oracle : `scripts/qchain_cpf_oracle.py`.
- Tests adversariaux : `scripts/test_qchain_cpf_oracle.py`.

## Frontières de preuve

Le device et les buffers principaux persistent réellement entre les frames;
les uniforms, bind groups et buffers de readback diagnostique sont
encore alloués par frame. Les compteurs de création représentent
le graphe construit par le code, **pas une mesure d'allocations du pilote**.

La qualification n'est ni un renderer Wayland continu, ni du
zéro-copie entre GPU et compositeur. Aucun benchmark FPS/p99,
GPU timestamp, durée de vie production, validation multi-vendeur ou
CP03 HYBRID-60. `G07–G10` demeurent ouverts.

**Verdict borné :**
`QCHAIN_CPF_PERSISTENT_DEVICE_40_FRAMES_GPU_EXACT_PARITY_PASS`.

**Next :** préparer la version GPU-source du transport IPC et vérifier
la présentation Wayland réelle sans élargir rétroactivement ce PASS.
