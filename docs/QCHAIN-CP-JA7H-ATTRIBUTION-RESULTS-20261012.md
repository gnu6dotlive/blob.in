# CP-JA7H — Frame-Time Attribution, résultats bornés

Date: 2026-10-12. Parent: ae728e6ef1a5e342f437295ac2ab40b990579c25.
Verdict: SCOPED PASS pour deux séries instrumentées; 60 FPS NON qualifiés.

| Série | Frames | FPS soumissions | Intervalle p99 | Compute + readback p99 | Upload API p99 |
|---|---:|---:|---:|---:|---:|
| 33 ms | 1200 | 30.210 | 36.296 ms | 15.711 ms | 0.530 ms |
| 16 ms | 1200 | 30.361 | 39.107 ms | 16.490 ms | 1.016 ms |

Chaque série: 2 400 ACK Vulkan typés, 2 400 feedbacks Weston, huit captures conformes.
18 séries de mesures host-clock par frame sur compute+readback, stdout, broker, memfd,
IPC client, vérification, texture, acquisition, encodage, soumission et present.
Les valeurs des appels Vulkan/wgpu ne sont pas des durées d'exécution GPU.
render_next() combine calcul GPU, synchronisation et readback; séparation indisponible.
Température/power nvidia-smi: mesures de carte entière, non attribuables au seul test.
La première tentative 16ms a fait HOLD par un gate héritant de >=33ms.
Une seconde tentative avec les mêmes binaires et consigne, mais gate corrigé, a PASS.
Neuf faux témoins sur neuf rejetés. Trois contrôles synthétiques fail-closed PASS.
31/31 tests blob-frame, Clippy -Dwarnings, compilation héritée CP-JA7G PASS.
Un seul GPU et deux swapchains par essai, Hyprland résident inchangé.

CONCLUSION: réduire la consigne de 33ms à 16ms ne double pas le débit;
cadence réelle encore proche de 30 FPS. Causes à isoler par qualification GPU timestamps
et boucle d'événements vs source, plutôt que prétendre CP03 HYBRID-60 PASS.
Aucun merge, push, déploiement, reset GPU ou promotion production.
