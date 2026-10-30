# BLOB-SHOWCASE-01 — audit initial et choix techniques (lot Surface Native)

## Squelette trouvé (2026-10-10)

`~/Projects/blob.in-showcase` n'était pas un dépôt Git. Il contenait 4 fichiers et 3 répertoires vides :

- `Cargo.toml` dépendait **directement** de `blobin-cuda02-provider` et `blobin-f2-topology`
  par chemin vers le worktree `blobin-cuda05f-integrated`, ce qui contourne CUDA-05F
  (interdit par le mandat, §9).
- `launch.sh` lançait un `server.py` absent ; `README.md` décrivait une page web locale
  (127.0.0.1:8766) absente elle aussi ; `src/`, `web/` et `renders/` étaient vides.

Aucun travail unique à préserver hormis ces fichiers. Ils ont été importés tels quels dans le
premier commit (`ee4c657`) avant leur remplacement. L'historique les conserve.

## Pile disponible (hors ligne, cache cargo vérifié)

| Besoin | Choix | Raison |
|---|---|---|
| Fenêtre Wayland | `winit 0.30.13`, features `wayland` + `wayland-dlopen` uniquement (pas de X11) | client `xdg-shell` standard ; Hyprland gère placement et décorations ; `app_id` = `live.gnu6.blobin-showcase` |
| Présentation GPU | `wgpu 30.0.1`, backend Vulkan seul | RTX 3070 / pilote NVIDIA 615 ; une copie memfd → texture par frame |
| Contrôles natifs | `egui 0.36.2` + `egui-wgpu` + `egui-winit` (sans clipboard, liens ni accesskit) | interface immédiate rendue dans la même surface wgpu ; ni navigateur, ni Electron, ni QML |
| IPC | `rustix 1.1.5` (`SOCK_SEQPACKET`, `SCM_RIGHTS`, `memfd`, scellés, `SO_PEERCRED`) | pas de libc brute ni de `unsafe` hors `mmap`/`munmap` |
| Messages | `serde` / `serde_json`, `deny_unknown_fields` | messages typés, bornés, stricts |

Système visuel : jetons de couleur, rayons et espacements GNU6/Gnosix repris en lecture seule de
`gnosix/crates/gnos-ux-gpui/src/product_design.rs`. Polices : Noto Sans, avec DejaVu Sans en
secours pour les glyphes ∪ ∩ − ✕ (fichiers système locaux), puis police intégrée à egui.

## Moteur (lecture seule, pour aligner le protocole)

CUDA-02 : cercles uniquement, ops 0–3 en pli gauche, premier op = union ; `k` de l'union
lisse fixé à 0,08 ; repère pixel → `((ix + 0,5 − w/2) / min(w, h), …)`, y vers le bas ; limites
16–2048 px et 1 MPix (le Render Bridge annonce 1024 px par côté). Aucun fichier du moteur, du
superviseur ou du Render Bridge n'a été modifié.

## Décisions de protocole

Le lot a commencé avec un brouillon de contrat côté surface. Quand le Render Bridge et son
contrat ont été livrés, la surface s'y est conformée intégralement (le contrat appartient au
runtime). Les écarts et les questions ouvertes sont dans
[`BLOB-FRAME-v1-viewer-notes.md`](BLOB-FRAME-v1-viewer-notes.md).

## Limites connues de la surface

- Copie CPU → GPU de chaque frame (memfd, pas de DMA-BUF), comme le prévoit le contrat v1.
- Au-delà de 1024 px par côté ou de 1 MPix, le rendu est demandé à résolution réduite puis
  agrandi. L'échelle est affichée dans les diagnostics.
- Pan/zoom appliqués par la surface aux primitives (pas de caméra dans v1). Les vues hors
  bornes du contrat ne sont pas envoyées.
- Les interactions souris/clavier (glisser, molette, raccourcis) passent par egui. L'E2E les
  remplace par une séquence d'édition scriptée (`--exercise`) qui passe par les mêmes
  opérations du modèle. Aucune injection d'entrées synthétiques n'est faite dans la session
  graphique.
- Captures : `grim` limité au rectangle de la fenêtre, placée explicitement sur son propre
  moniteur (y compris un moniteur pivoté).
