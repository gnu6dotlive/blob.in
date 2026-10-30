
# BLOB-RENDER-RECONCILE-01 — Contrat de réconciliation du capital de rendu

**Mandat opérateur :** « ok next alors » après confirmation des laboratoires 3D/2.5D et de la chaîne UI 01A–01I.
**Date :** 2026-10-12.
**Dépôt de réception :** tension-atoi/blob.in-showcase, main privé.
**Baseline :** `d2903f0a53d648a739f4cabdf03d3842577108e9`.
**Périmètre :** provenance et architecture, aucun merge des moteurs, aucune publication de sources donneuses.

## Livrables et gates

1. Enregistrer les SHA-256 des fichiers Rust/WGSL/Cargo de F1, F2, F3, F4, F4B, F4C, puis comparer les anciens worktrees à la copie Git valide CP01, sans altérer ni réparer leurs `.git`.
2. Prouver les HEAD CP01/CP02/main et leur état Git; distinguer le commit GPU00 historique de la branche CP02 actuelle.
3. Relancer hors ligne CP01, F2, F4C et la compilation/test CP02, avec cible Cargo distincte des sources. Ne pas faire passer le build CP02 pour une nouvelle exécution physique Vulkan.
4. Confronter les responsabilités F2(topologie), F3(matériaux), F4(effets), F4B(résilience), F4C(damage), CP01(géométrie 3D), CP02(compute Vulkan), GPU05/QCHAIN(présentation), G02/G03(UI native).
5. Conserver le statut **CP03 HYBRID-HERO-60@1 NOT QUALIFIED**, la séparation de preuves entre scènes, et les barrières de licence.
6. Écrire le prochain contrat R02 de données, sans coder un doublon de renderer, sans importer F4 dans la scène UI.
7. Préserver sans nettoyage ni stage les quatre chemins G04B/H de travail parallèle.
8. Produire un manifeste requalifiable et un rapport technique, intégrés au main privé seulement après contrôle de staging et SHA GitHub.

## Anti-contextes

Pas de rebase, cherry-pick, merge, réparation des worktrees, vendor GPL/AGPL/historique, migration GPUI/Gnosix, redémarrage de GPU/compositeur, simulation de rendu 3D intégré, ou promotion de CP03. Le main showcase déclare actuellement `LicenseRef-Proprietary` et les manifestes F1–F4C ne déclarent pas de licence de distribution : aucune autorisation publique n'est inférée des termes « clean-room » et « publish=false ».

**Verdict admissible :** `SCOPED_PASS_READ_ONLY_SOURCE_RECONCILIATION`, ce qui ne signifie ni intégration produit ni réussite CP03.
