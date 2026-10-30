# CP-L — Préparation read-only des 17 lois adversariales

**Date :** 2026-10-10. **Autorité :** contrat `QCHAIN-GPU-EXECUTION-01`,
section 8, et `contracts/qchain-gpu-execution-01/dispatch.json`.

**État :** inventaire statique seulement. **Aucun PASS G06 revendiqué.**
Aucune mutation exécutée au titre de CP-L, et aucune modification
des sources GPU, du CPU canonique, des services ou des archives de preuve.

Le registre machine-readable `inventory/cpl-static-inventory.json`
réconcilie les **17 identifiants N01–N17**, leurs injections contractuelles,
les erreurs de refus attendues et les tests candidats antérieurs.

| Sous-ensemble | Couverture candidate | Qualification CP-L |
|---|---|---|
| N02, N06, N07, N08, N10, N13, N14, N17 | Tests proches identifiés | NOT_RUN |
| N01, N03, N05, N09, N11, N12, N15, N16 | Indices partiels identifiés | NOT_RUN |
| N04 | Injection directe non retrouvée | GAP |

## Principaux risques à fermer

- **N04** : créer un contrôle falsifiant *les identités topologiques*,
  pas seulement les pixels d'un masque.
- **N05/N07/N09** : démontrer les refus de topologie, valeurs numériques
  et temporalité à la frontière où ces états entrent dans le moteur.
- **N11/N12** : vérifier ensemble un mauvais stride et l'injection d'un
  processus possédant un UID différent; les FD surnuméraires, non scellés
  et les tailles non exactes disposent déjà de témoins séparés.
- **N15** : les SHA permettent de constater l'altération de bytes,
  mais aucun processus de signature externe ne rend encore une
  modification d'évidence « après signature » testable strictement.
- **N16** : distinguer source/provenance logicielle de la preuve
  indépendante d'une dispatch GPU effective, par traces observables.
- **N17** : distinguer systématiquement les cinq identités de scène
  des trois images binaires uniques.

## Conditions avant G06 FULL

Chaque Nxx devra produire dans **une même campagne identifiée** :
état initial source/artefacts gelés, mutation d'un seul paramètre,
refus effectif correspondant au code annoncé, témoin positif,
preuve conservée et comparaison par un oracle non producteur.

L'inventaire ne prouve **ni 16 PASS sur 17, ni 8 PASS**, seulement
des points de départ documentés à revoir. Il n'autorise pas les
promotions G06 ou G10.

**Proposition :** ouvrir CP-L01 par N04/N05/N16 (autorité
topologique et provenance), puis CP-L02 pour la campagne complète
N01–N17, lorsque CP-I02 a un nouveau renderer continu à attaquer.
