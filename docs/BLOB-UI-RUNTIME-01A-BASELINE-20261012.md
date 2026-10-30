# BLOB-UI-RUNTIME-01A — État initial/P0 classifié

**Base observée avant exécution :** 2026-10-12, main = origin/main = 798796dc8f7f78ca34234e5c8901242b2834d1ce.
Dépôt privé : tension-atoi/blob.in-showcase. Machine Arch/CachyOS + NVIDIA RTX 3070, Rust 1.97.0, cargo 1.97.0.
35 worktrees Git constatés; ils ne sont pas à supprimer, rebaser ou fusionner par défaut.
Fichiers G04B/H préexistants et préservés :
- M crates/showcase/src/bin/blobin_ui_g04b_wayland.rs
- ?? docs/BLOB-UI-G04B-HYPRLAND-COMPOSITOR-INPUT-E2E-20261012.md
- ?? evidence/runs/blob-ui-g04b-hyprland-20261012/
- ?? scripts/blobin_ui_g04b_hyprland_oracle.py

**Propriétaires existants :**
- UI-G02/G03/G04 : crates/blobin-ui-core. Aucune implémentation modifiée.
- Scène SDF de produit : showcase/SceneState et Scheduler, contrat BLOB-FRAME-v1.
- Pixels SDF calculés : blobin_renderd et ses workers externes.
- Input production courant : egui-winit/egui Response, capture et focus.
- Surface de présentation : showcase Gfx wgpu et sa fenêtre Wayland.
- Palette produit : showcase/theme.rs; Gnosix/gnos.ux et design system hors portée.
- Nouvelle display-list : crates/blobin-ui-scene, première primitive fonctionnelle uniquement.

**AC-05 ajouté à la baseline :** SCOPED PASS CPU SDF E2E capturé et qualifié, mais replay automatisé nouveau HOLD, aucune réception CP03.
**Mode legacy de régression :** BLOB_UI_01A_LEGACY=1 pour remettre le widget egui historique.
**Limite de P0 :** G04B/H non commités et les worktrees non nettoyés restent volontairement hors de ce jalon.
