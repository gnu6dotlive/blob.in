# blob.in — surface native Wayland

> **Version publique.** Ce dépôt est la projection publique, à sens unique, du dépôt privé
> `blob.in-showcase` : un commit par version, l'historique de travail reste privé. Il contient
> la **surface** native — l'application qui affiche les frames BLOB-FRAME-v1 — et son serveur
> de test. **Le moteur qui calcule les vraies frames (le Render Bridge) n'est pas encore
> publié** : sans lui, la surface tourne avec le serveur de test et ses mires de référence.
> Les preuves de `evidence/` sont publiées telles quelles, sceaux sha256 intacts ; les chemins
> locaux qu'on y lit sont ceux de la machine de qualification, et les commandes qui citent
> `/mnt/workbench` ou gnu.in.labs décrivent cette machine-là. Licence MIT (`LICENSE`) ;
> wgpu-hal 30.0.1, dans `vendor/`, garde ses licences (`THIRD_PARTY_NOTICES.md`,
> `docs/LICENCE-DECISION-20261030.md`).


**Point d'entrée canonique pour les agents et contributeurs :** [Integration Spine & Provenance (2026-10-12)](docs/PROGRAM-INTEGRATION-SPINE-20261012.md). État actuel, gates qualifiées/non qualifiées, branche d'intégration `main`, sauvegarde GitHub privée et preuves externes encore à archiver.

Application native **Wayland/Hyprland** (Rust, winit + wgpu + egui) qui affiche les frames
calculées par le runtime blob.in via le contrat **BLOB-FRAME-v1** (Unix `SOCK_SEQPACKET`,
memfd scellé transmis par `SCM_RIGHTS`).

La surface ne calcule aucune géométrie. Chaque pixel du viewport provient d'une frame reçue,
à l'exception des contours de contrôle, que la surface trace à partir de ses propres valeurs
et qu'on peut masquer avec la touche **G**. Le moteur blob.in est un moteur **2D à champ de
distance signée** : le mode *Éclairé* est un ombrage dérivé des normales calculées
(post-traitement 2D), pas un rendu 3D.

```
crates/blob-frame             contrat côté client : types, validation, transport, memfd, session
crates/blob-frame-testserver  serveur de TEST isolé : mires de référence + 19 pannes injectables
crates/showcase               l'application (binaire blobin-showcase)
scripts/e2e_hyprland.py       E2E sur vraie fenêtre Hyprland (redimensionnement, captures, fermeture)
docs/                         audit, notes de contrat, écarts observés
evidence/                     traces, journaux, captures et run.json (sha256)
```

## Prérequis

Session Wayland (Hyprland), GPU Vulkan, Rust ≥ 1.85. Les dépendances sont dans le cache cargo
local (`--offline`). Les binaires vont dans le répertoire cible configuré par cargo ; utiliser
`cargo run` ou `scripts/e2e.sh`, qui le déterminent eux-mêmes.

## Lancer

**Avec le vrai runtime** (Render Bridge, lancé séparément par son propriétaire) :

```sh
# terminal 1 — runtime (worktree du Render Bridge, hors de ce dépôt)
cd /mnt/workbench/workspaces/gnu.in.labs/.worktrees/blobin-showcase-runtime-01/experiments/blobin-next-01/CUDA-05
./scripts/start_render_bridge.sh

# terminal 2 — surface
cd ~/Projects/blob.in-showcase
cargo run --offline --release -p blobin-showcase -- --backend cuda
```

**Avec le serveur de test** (aucun moteur ; une bannière « SERVEUR DE TEST » est affichée en permanence) :

```sh
cargo run --offline --release -p blob-frame-testserver -- --delay-ms 40      # terminal 1
cargo run --offline --release -p blobin-showcase -- --test-server             # terminal 2
# pannes : --fault NAME [--fault-every N]   (liste : blob-frame-testserver --help)
```

Options de la surface : `--socket PATH`, `--test-server`, `--backend cpu|cuda|vulkan`,
`--lab 1..6`, `--size WxH`, `--trace FILE.jsonl`, `--exercise`.

## Utiliser

| Action | Geste |
|---|---|
| Changer de lab (Primitive, CSG, Smooth, Field, Normal, Material) | boutons ou **1**…**6** |
| Déplacer un cercle / changer son rayon | glisser / molette sur le cercle (ou **Tab** puis flèches, **+** **−**) |
| Changer l'opération (union, soustraction, intersection, union lisse) | liste déroulante ou **O** |
| Ajouter / supprimer un cercle | boutons **+**, **✕**, ou **Suppr** |
| Pan / zoom | glisser le fond / molette (Ctrl+molette au-dessus d'un cercle) ; **R** pour réinitialiser |
| Backend / visualisation | boutons ou **B** / **V** |
| Aide | **F1** |

Le panneau *Diagnostics* affiche les données réelles de la session et de la frame à l'écran :
serveur, backends annoncés, `backend_actual`, `qualification` (verbatim), génération,
dimensions/stride/format, échelle de rendu, aller-retour mesuré par la surface, digest
géométrique, révisions, compteurs. Aucune métrique n'est inventée : un champ non mesuré
n'est pas affiché.

## Arrêter

Fermer la fenêtre (Hyprland), ou **Ctrl+Q**. La session IPC est fermée, les threads sont
joints, les descripteurs et la texture sont libérés. Le serveur de test s'arrête avec
`Ctrl-C` ; son fichier socket reste alors en place et sera remplacé au lancement suivant
(un socket encore actif n'est jamais écrasé).

## Tester

```sh
cargo test --offline --workspace                 # 45 tests : protocole, transport, pannes, fuites, scheduler, tempête de resize
cargo clippy --offline --workspace --all-targets # 0 avertissement
scripts/e2e.sh test-server                       # vraie fenêtre Hyprland + serveur de test
scripts/e2e.sh runtime cuda                      # vraie fenêtre + vrai Render Bridge (cuda|vulkan|cpu)
scripts/e2e.sh runtime cuda --exercise           # séquence d'édition scriptée vérifiée frame par frame
cargo run --offline -p blob-frame --example probe  # sonde : 3 backends × 4 modes sur le runtime
```

L'E2E place et redimensionne **uniquement sa propre fenêtre** via `hyprctl dispatch`, sans
modifier la configuration Hyprland. Il capture avec `grim` le seul rectangle de la fenêtre,
puis écrit `run.json` (vérifications, sha256 des artefacts) dans `evidence/runs/`.

## Limites

Voir [`docs/AUDIT.md`](docs/AUDIT.md) et
[`docs/BLOB-FRAME-v1-viewer-notes.md`](docs/BLOB-FRAME-v1-viewer-notes.md). Points principaux :
pas de caméra dans le contrat v1 (pan/zoom appliqués par la surface aux primitives) ; 1024 px
par côté au maximum (au-delà, rendu réduit puis agrandi) ; latence GPU de 0,3 à 0,9 s par frame
(gate + worker jetable par requête) ; le runtime sert un seul client à la fois.

## Q-CHAIN — Contrat de qualification GPU (expérimental)

Le contrat directeur est [QCHAIN-GPU-EXECUTION-01](docs/QCHAIN-GPU-EXECUTION-01.md).
Le dispatch versionné se trouve dans `contracts/qchain-gpu-execution-01/dispatch.json`.
La validation locale est `python3 scripts/validate_qchain_contract.py`, avec
`python3 -m unittest discover -s scripts -p 'test_qchain_contract.py' -v`
pour les falsifications contrôlées du contrat. Statut : **draft / GPU F2–F4 NOT_RUN**.
Les buffers CPU d'origine et les captures Wayland demeurent privés.

Code privé : ne pas publier ce dépôt ni les sources blob.in sans revue de licence et de visibilité.
