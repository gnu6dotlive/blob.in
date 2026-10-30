# BLOB-AC-01 — Gestes transactionnels, qualification du sous-système UI
Date : 2026-10-12
Périmètre : blob.in / blobin-ui-core, headless et renderer-independent
Contrat : [BLOB-AC-01-TRANSACTIONAL-GESTURES-20261012](../contracts/BLOB-AC-01-TRANSACTIONAL-GESTURES-20261012.md)
Source d'inspiration : VectorCraft POC02, analyse comportementale, **aucune copie ni import de code ArtCraft**.

## Résultat
SCOPED PASS pour le **contrat headless**, seulement si le vérificateur python3 scripts/blob_ac01_verify.py termine avec code 0 et que son reçu affiche SCOPED_PASS.
Aucun claim de widget visible, de cadence GPU, de driver Wayland testé par l'utilisateur, de BLOBIN-UI-60, de G04/B FULL ni de CP03 HYBRID-60.

## Architecture
- crates/blobin-ui-core/src/gestures.rs : GestureCoordinator, GestureAction (Begin, Preview, Commit, Cancel), Translation et CancelReason.
- InputRouter / InputReceipt : l'hôte obtient d'abord une validation G04/A avec un événement hôte horodaté, stampé et monotone.
- LayoutSnapshot / LayoutStamp / Viewport : une interaction est liée à sa géométrie initiale; tout changement d'epoch/style/surface annule avant commit.
- UiTree::transact : propriété de la mutation canonique inchangée; le module de gestes **n'écrit rien** dans l'arbre.
- Un PointerDown primaire capturé démarre une interaction; les mouvements produisent un delta **absolu** depuis le début. Un PointerUp sur la même capture termine en Commit si le delta est non nul.
- Les clics sans déplacement deviennent Cancel(NoTravel). Le consommateur peut conserver l'activation de G04/A pour un clic, mais doit supprimer la double action clic+drag lorsqu'une opération a été committée.
- Le rendu éventuel des overlays temporaires est réservé à un futur consommateur; GestureAction::Preview n'est pas une commande GPU.

## Confiance, sécurité et transactions
GestureCoordinator::observe accepte seulement un InputEvent et un InputReceipt correspondants pour le même surface et serial, et exige que le layout et les événements soient courants.
**Frontière de confiance :** cela reste une API entre modules locaux. Les receipts publics ne sont pas des jetons cryptographiques; les hôtes ne doivent pas les accepter comme attestation depuis un agent ou un processus distant. Le bon appel est InputRouter::dispatch suivi immédiatement de observe avec le même événement et le reçu retourné.
Le coordinateur rejette la répétition de serial, les coordonnées non finies et les epochs périmées. Escape, focus perdu, cancel et fermeture invalident sans écrire de document.
Sur un resize en plein drag, l'hôte peut appeler cancel_surface immédiatement; sans appel proactif, l'annulation intervient au prochain événement routé sur la nouvelle géométrie. Ne pas utiliser le dernier preview comme état canonique.
Les mutations du renderer SDF, F4, Unix socket, Wayland surface, memfd/SCM_RIGHTS et flux GPU ne sont pas touchées.

## Tests et preuves
Commande canonique : python3 scripts/blob_ac01_verify.py

Le vérificateur exécute, avec journal stdout/stderr et SHA-256 par étape :
1. Rustfmt du crate
2. cargo test --offline -p blobin-ui-core --all-targets
3. cargo clippy --offline -p blobin-ui-core --all-targets -- -D warnings
4. cargo tree --offline -p blobin-ui-core — une seule ligne (std only)
5. cargo run --offline -p blobin-ui-core --example gesture_workbench
6. cargo test --offline --workspace --lib

Exemple : BLOB_AC01_HEADLESS_OK previews=2 commits=1 undo=1.
La suite tests/gestures.rs couvre 10 scénarios : preview absolu, commit unique + undo consommateur, clic sans mutation, capture hors fenêtre, pixels physiques et DPR, doublons/replay, isolations multi-pointeur/multi-surface, focus/Escape, resize, stale receipt et close surface. La suite existante G02/G03/G04/A est conservée.
Les 75 tests directs et 51 tests --workspace --lib réussissent dans la preuve initiale; aucune assertion n'établit une performance de rendu.

Reçu : evidence/runs/blob-ac01-20261012/qualification.json. Garder tous les stdout/stderr et leurs hachages; source hash avant commit, commit SHA et origine GitHub vérifiés séparément après push.

## Limites / prochaines gates
- Source seule : aucune scène native indépendante reliée à ce coordinateur, aucune capture GPU, aucun clic Wayland physique indépendant.
- Absence de matrice de glisser redimensionnement, rotation, multi-touch, pressions et inertie; elles demandent des contrats propres et un moteur de scène.
- Le label d'exemple représente seulement une mutation de démonstration. Le déplacement réel d'un objet visuel réclame un état de scène et une présentation bornée, **sans** détourner le renderer blob.in.
- Le G04/B natif existant demeure une piste distincte et ses fichiers non committés ont été préservés.
- Aucun code tiers vendored. Vérifier les licences avant toute extraction future.
- Prochaine étape possible : adapter un consommateur natif sur la ligne G04/B *après résolution de son HOLD indépendant*, avec tests d'exactement-un sur traces compositor et rendu observable.
