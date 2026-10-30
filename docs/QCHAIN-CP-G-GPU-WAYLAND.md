# QCHAIN CP-G — GPU-source IPC → Wayland

**10 octobre 2026.** Branche `feat/qchain-gpu-ipc-wayland-20261010`, dérivée de `749cb8a`.
**Contrat :** QCHAIN-GPU-EXECUTION-01. Qualification bornée privée, aucune promotion production.

## Exécution réelle

1. Nouvelle exécution de `PersistentSession` Vulkan sur RTX 3070 : 40 frames, un device, trois pipelines, cinq buffers GPU réutilisés; source `5132cf5`.
2. `build_qchain_gpu_manifest.py` fige cinq buffers GPU Ceramic-frame0, identités de scènes canoniques et SHA du journal compute. Trois images binaires distinctes mais cinq identités sémantiques.
3. Protocole **opt-in `QCHAIN-GPU-FRAME-v1`**, différent de la version CPU inchangée : socket Unix SEQPACKET, même UID, un memfd scellé, vérification dimensions, identités, empreintes et provenance. `gpu_qualified=false` et `compositor_observed=false` jusqu'à qualification indépendante.
4. Viewer Vulkan natif opt-in `qchain_gpu_viewer`, fenêtre Hyprland isolée 512×384, cinq soumissions, captures `grim` réelles.

## Éléments matériels

- Compute : `/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-01/compute/`.
- Première capture : `.../qchain-gpu-ipc-wayland-20261010-01/wayland/`. Stage 0 comporte 188 pixels divergents hors masque (rectangle x77–86 / y64–85). **Ce run ne satisfait pas le gate pixel**, et demeure archivé sans effacement ni élargissement du masque.
- Seconde capture : `/mnt/workbench/evidence/runs/qchain-gpu-ipc-wayland-20261010-02/wayland/`. Avec délai de stabilisation plus long : cinq PNG et cinq frames Vulkan réellement présentées. Chacun des cinq états a **zéro pixel différent hors des quatre carrés 18×18 autorisés**. 344 pixels de coins diffèrent dans chaque capture.
- Oracle indépendant : `scripts/qchain_gpu_compositor_gate.py`, verdict `QCHAIN_GPU_SOURCE_IPC_WAYLAND_E2E_PASS_CORNER_MASKED`; contrôle du journal GPU, SHA manifeste, identités, source IPC, reçus viewer et captures recomputées.
- Contrôles adversariaux complémentaires : 5 tests Python PASS, dont run initial imparfait rejeté, manifeste GPU-version CPU rejeté, substitution d'identité rejetée et expansion du masque refusée. Tests Rust du transport : 20/20 PASS.

## Frontières

Ce chemin est **GPU compute → readback CPU → memfd scellé → réupload texture GPU de présentation**. Il n'est PAS zéro-copie, n'atteste pas un GPU matériel cryptographiquement, ni des photons. La comparaison avec les pixels CPU n'est pas une équivalence binaire universelle. G06 17/17, G09 replay indépendant, CP03 HYBRID-60 et critères multi-vendeurs demeurent ouverts. Aucun merge, push, release ni changement des services résidents.
