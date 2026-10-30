# CP-JA7J-C — Qualification F4 six GPU compute passes

Date 2026-10-12; parent Git ea8ffc63717f1690bd2b8e2c77ee1244ce32cef6.
Verdict: **SCOPED PASS**, timestamp queries GPU authentiques sur F4; CP03 HYBRID-60 OPEN.

Sources originales dans le snapshot historique Git 5132cf59b3842e27dcacf89bfe7060e807706e90.
Le clone privé F1/F2/F3/F4 a été instrumenté sans modification des sources historiques.
wgpu ComputePassTimestampWrites écrit 12 timestamps réels par frame pour six passes.
1200 frames sources F4 originales (contrôle canonique RGBA), 7200 dispatchs compute,
1200 soumissions GPU, device persistant unique, 3 pipelines et 5 buffers réutilisés.
14400 timestamps GPU source relus dans 115200 octets; résolution GPU 1ns/tick.
2400 ACK Vulkan, 2400 feedbacks Weston presented, 8 captures Wayland indépendantes.

| GPU compute pass | Durée médiane | p99 |
|---|---:|---:|
| F2 | 17,66 µs | 20,70 µs |
| F3 | 77,15 µs | 103,62 µs |
| Shadow | 14,91 µs | 45,63 µs |
| Blur | 122,64 µs | 149,02 µs |
| Bloom | 290,46 µs | 348,80 µs |
| Echo | 12,48 µs | 17,25 µs |

Thermal guard: 44 relevés NVIDIA, température GPU max 50°C, puissance carte max 55,84W.
Valeurs GPU carte entière, non attribuées au test exclusivement.
L'oracle indépendant recalcule les écarts de chaque paire de ticks et confronte
les logs kernel par numéro de frame et la finalisation du moteur.
Huit sur huit falsifications sont rejetées sans altérer les sources positives.
