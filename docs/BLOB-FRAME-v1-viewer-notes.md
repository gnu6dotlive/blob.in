# BLOB-FRAME-v1 — notes côté surface (viewer)

**Autorité du contrat :** le runtime (`CUDA-05/contracts/BLOB-FRAME-v1.md`, statut
`01A-runtime-implementation`, implémentation `blobin_renderd` au commit `823fdbd`). Ce document
ne modifie pas le contrat. Il décrit comment la surface l'implémente et liste les écarts
observés et les décisions à figer conjointement.

## Conformité de la surface

| Point du contrat | Implémentation surface (`crates/blob-frame`) |
|---|---|
| `AF_UNIX` + `SOCK_SEQPACKET`, `$XDG_RUNTIME_DIR/blobin-showcase/render.sock` | `transport.rs` ; le répertoire doit être un vrai répertoire (pas de symlink), propriété de l'UID courant, sans droits groupe/autres ; `SO_PEERCRED` exige le même UID |
| 1 JSON par paquet, 16 384 octets max | refus à l'envoi et à la réception (`MSG_TRUNC` → rejet) |
| `version: "BLOB-FRAME-v1"` sur chaque message, champs inconnus rejetés | `deny_unknown_fields` dans les deux sens ; version vérifiée sur chaque message serveur |
| HELLO puis CAPABILITIES (requête/réponse) | poignée de main avec délai de 5 s |
| Une requête de rendu à la fois, traitement séquentiel sans réordonnancement | au plus 1 requête en vol ; chaque réponse est appariée au plus ancien message sans réponse (FIFO) ; toute réponse hors séquence = violation → session réinitialisée |
| 16–1024 px par côté, ≤ 1 048 576 px, 1–64 primitives, centres dans [-2, 2], rayon dans (0, 2], `op` 0–3, premier `op` = 0 | validé localement avant envoi (`RenderRequest::validate`) |
| FRAME_READY + exactement un memfd scellé | 0 ou ≥ 2 descripteurs → frame rejetée ; scellés `WRITE|GROW|SHRINK|SEAL` exigés avant `mmap` (pas de SIGBUS, pas de modification après coup) |
| Longueur = `stride_bytes * height_px`, stride = largeur × 4 | vérifié ; un stride avec padding est rejeté |
| Pas de repli silencieux | `backend_actual ≠ backend_requested` → frame rejetée, jamais affichée |
| RENDER_ERROR `{request_id, scene_revision, reason}` | attribué à la requête en cours ; `reason` affiché tel quel |

## Écarts observés entre le document et `blobin_renderd` (823fdbd)

1. **`frame_sequence`** est envoyé dans FRAME_READY mais absent du document, qui dit
   « fields are exact ». La surface l'accepte en champ optionnel et l'affiche ; elle ne le
   requiert pas. → *À ajouter au contrat ou à retirer du serveur.*
2. **`generation`** vaut `0` pour le CPU et la génération du gate pour CUDA/Vulkan. Ce n'est
   donc pas un identifiant de session runtime. La surface l'affiche sans s'en servir pour
   valider. → *À préciser : sémantique et portée (par backend ? par processus ?).*
3. **`request_id: 0` / `scene_revision: 0`** désignent une erreur non liée à une requête
   (`INVALID_CONTROL_MESSAGE`), alors que le contrat autorise `request_id = 0`. La surface
   numérote ses requêtes à partir de 1 et refuse localement l'id 0. → *Réserver 0 dans le contrat.*
4. **Codes `reason`** observés : `INVALID_CONTROL_MESSAGE`, `RENDER_FAILED`, `WORKER_TIMEOUT`.
   Ils ne sont pas énumérés dans le document. → *Les énumérer (la surface les affiche tels quels).*
5. **Codage couleur** : `RGBA8_UNORM_OPAQUE` ne précise pas l'espace de couleur. La
   colorisation écrit `round(c × 255)` sans courbe, et la sonde Python enregistre ces octets
   en PNG, donc lus comme sRGB. La surface les traite comme des valeurs d'affichage (texture
   `Rgba8UnormSrgb`, restitution à l'identique). → *Préciser « sRGB-encoded, display-referred ».*
6. **CAPABILITIES** ne donne ni le nombre maximal de primitives (64), ni les bornes des
   coordonnées, ni le `k` de l'union lisse (0,08, fixé dans CUDA-02). La surface reprend les
   valeurs du document et du code moteur. → *Les annoncer dans CAPABILITIES.*

## Décisions prises côté surface (dans les limites du contrat)

- **Caméra** : v1 n'en transporte pas. Le pan/zoom est appliqué par la surface aux primitives
  (`engine = (monde − centre) × zoom`, rayon × zoom). Conséquences : en mode distance, les
  valeurs sont en unités de vue ; une vue qui ferait sortir un centre de [-2, 2] n'est pas
  envoyée et l'interface l'indique.
- **Résolution** : taille physique du viewport réduite uniformément pour respecter les
  limites annoncées (ex. viewport 1252×900 → requête 1024×736). L'échelle est affichée.
- **Frames obsolètes** : une frame n'est affichée que si sa révision dépasse celle à l'écran.
- **Délai** : sans réponse après 20 s (le worker GPU s'arrête à 15 s), la requête échoue et la
  session est réinitialisée, car une réponse tardive désynchroniserait l'appariement FIFO.
- **Mono-client** : le runtime sert une connexion à la fois. Tant que la surface est
  connectée, `interop_probe.py` attend.

## Mesures sur ce poste (RTX 3070, 2026-10-10)

Sonde `cargo run -p blob-frame --example probe` (320×224, 4 primitives dont une soustraction,
12 frames, toutes validées : scellées, opaques, backend conforme) :

| Backend | Aller-retour mesuré par le client | Écart max par canal vs CPU | Pixels différents |
|---|---|---|---|
| CPU | 14–15 ms | — | — |
| CUDA | 450–870 ms | ≤ 1 LSB (normals, lit) | 12 / 71 680 (normals), 1 (lit) |
| Vulkan | 280–300 ms | ≤ 1 LSB (normals) | 26 / 71 680 (normals) |

`distance` et `coverage` sont identiques à l'octet près entre les trois backends sur cette
scène. La parité RGBA stricte annoncée côté runtime vaut donc pour sa scène de test, pas pour
toutes les scènes : l'écart de 1 LSB vient de l'arrondi des normales par différences finies.
Journal : `evidence/logs/real-bridge-probe-20261010.jsonl`.

La latence GPU (gate CUDA-05F + worker jetable à chaque requête) donne environ 1 à 3 images/s
en interaction. La surface reste fluide (frame précédente affichée, contours de contrôle
immédiats), mais le rendu suit avec ce délai.
