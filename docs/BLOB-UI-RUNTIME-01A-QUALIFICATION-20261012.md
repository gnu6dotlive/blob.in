# BLOB-UI-RUNTIME-01A — Qualification de la première UI native de l'éditeur

**Date :** 2026-10-12. **Mandat ratifié :** contracts/BLOB-UI-RUNTIME-01-AVENANT-RATIFICATION-20261012.md.
**Contrat d'origine :** contracts/BLOB-UI-RUNTIME-01_Contrat_de_travail_2026-10-12.md.
**Reproduire :** python3 scripts/blob_ui01a_verify.py.
**Preuve canonique :** evidence/runs/blob-ui-runtime-01a-20261012/qualification.json.

## Application réelle, pas démo

Le vrai éditeur blobin-showcase possède toujours son SceneState et le vrai renderer BLOB-FRAME-v1. Le toggle Contours de contrôle (G) agit toujours sur Model.overlay.
Le core UI-G02 fournit son NodeId stable, sa révision, ses snapshots, ses propriétés. UI-G03 dérive les bounds du contrôle, son clip et l'epoch de géométrie. blobin-ui-scene transforme ce snapshot en trois commandes FillRoundedRect neutres (track, border, thumb). L'adaptateur natif wgpu dessine ces commandes via un pass Load sur le même swapchain que l'éditeur, sans fenêtre, device ou scheduler supplémentaire.

L'egui Response existant possède encore le pointeur et le focus. Le libellé texte demeure egui. La nouvelle scène ne revendique pas le texte, l'IME ou le pont d'accessibilité natif. Les couleurs sont des paramètres fournis par le client à partir de theme.rs.
Les bounds de capture egui et de dessin G03 sont contrôlés à 0,2 px logiques; un layout incompatible est rejeté, jamais affiché silencieusement. Le clip inclut la région visible de la ScrollArea.

Le mode de repli **BLOB_UI_01A_LEGACY=1** rétablit l'ancien checkbox egui si souhaité, et toute panne de géométrie désactive explicitement la voie native en journalisant l'erreur. Ce n'est pas un fallback silencieux.

## Qualification native et images

Weston privé, user+net namespace, siège de test propre; le vrai binaire blobin-showcase, le vrai blobin_renderd CPU et ses workers fingerprintés sont exécutés.
Le contrôle a des bounds G03 identiques aux bounds egui (946,623,52,26) sur le scénario 1280×800. Le pointeur injecté par Weston (975,635) effectue une pression et un relâchement; l'état passe activé→désactivé avec UI revision 1→2. La scène géométrique reste révision 3, **une seule requête SDF et une seule frame SDF** pendant le clic.
Les buffers GPU de la même surface sont copiés après que le premier rendu SDF est reçu, avant queue.present. Ils sont archivés sans perte en PNG et rgba.gz.
Pixels gauche (958,636) bleu→blanc; droite (986,636) blanc→sombre; points témoins hors contrôle inchangés. 2964 octets-canaux diffèrent dans la région propre du toggle 52×26.
L'oracle indépendant doit rejeter une requête SDF artificiellement rajoutée et toute archive dont un SHA ne correspond pas.

## Bornes de vérité

**SCOPED PASS conditionnel au reçu local** signifie : un vrai contrôle de production est partiellement auto-dessiné par le nouveau pipeline 2D.
Cela ne démontre pas présentation compositor/photons, HID matériel, cadence 60 FPS, texte/IME natif, accessibilité observée, composants universels, P1 complet, GPUI remplacé ni CP03 HYBRID-60.
Les travaux G04B/H non intégrés sont laissés inchangés.

## Suite du programme

Prochaine phase proposée **01B/P1** : généraliser display-list, rajouter transforms/clip et primitives vectorielles, diminuer les créations de buffers GPU, puis migrer un deuxième contrôle utile. Ne pas déclarer runtime autonome ni migrer Gnosix avant preuve complète.
