# BLOB-UI-RUNTIME-01B — Contrat de travail borné

**12 octobre 2026. Autorisation : GO NEXT après 01A ratifié.**
Dépôt canonique privé tension-atoi/blob.in-showcase, main, baseline 66c1735f4a2cef2ebf7ca367baf547ae0177faa9.
Parent : BLOB-UI-RUNTIME-01 et avenant 01A, conservés dans contracts.

## Mission

Migrer une seconde famille de composant graphique dans le véritable éditeur blob.in : le bouton sélectionnable Distance de la section Visualisation. Contrairement au toggle Contours, Distance change le mode de rendu réel Coverage vers Distance et demande exactement une nouvelle frame du véritable moteur SDF CPU. Le reclic sur Distance est un no-op.

## Partage et autorité

- Scène neutre blobin-ui-scene : état de bouton sélectionnable (idle/hover/pressed/selected/focused/disabled), palette injectée, commandes de rectangles arrondis avec provenance et clipping; aucun import egui/wgpu/GPUI/Gnosix.
- Contrôle de layout G02/G03 réutilisable : NodeId, UiSnapshot, LayoutSnapshot, clip, géométrie et epoch partagés par le toggle historique et le nouveau bouton, au lieu de créer deux autorités de mise en page.
- La capture, l'activation clavier/pointeur, le libellé et le focus restent à egui; pas de second InputRouter concurrent, pas de faux runtime autonome.
- La surface, la queue, le device et les frames F4/BLOB-FRAME restent la propriété du showcase et du vrai renderer. Aucun renderer SDF ni worker modifié.
- Une passe wgpu pour deux DisplayLists (six commandes), buffer uniforme persistant de 64 instances et bind group résident avec offsets dynamiques, un upload seulement quand les paramètres changent.
- Pas de nouveaux buffers GPU ou bind groups **par commande** dans le chemin UI natif; les captures de laboratoire créent leurs propres buffers temporaires.
- Fallback indépendant BLOB_UI_01B_LEGACY=1 ; l'instrument historique 01A force ce fallback pour garantir les bounds de sa preuve originale. BLOB_UI_01A_LEGACY reste opérationnel.

## Gates

**G01** : inventaire et préservation des quatre chemins G04B/H non committés et du SHA Git origin/main.
**G02** : API ActionVisualState/ActionPalette/action_button testée, sans dépendances interdites, état sélectionné, clipping, stale layout.
**G03** : hôte G02/G03 partagé, NodeIds stables et surfaces distinctes, tests 01A et 01B.
**G04** : vraie interface egui, clic Distance une fois => changement de mode et exactement une invalidation; reclic aucun effet; Contours conserve son indépendance.
**G05** : wgpu réel, une passe, six commandes, deux familles, buffer uniforme et bind group réutilisés sans allocation par primitive.
**G06** : Weston 15 privé, namespace user/net indépendant, deux clics natifs; premier => nouvelle frame CPU SDF; second => aucune requête SDF supplémentaire.
**G07** : captures GPU client originales action idle/action selected/toggle off; origines SHA et archives lossless; oracle pixel, révisions [3,4], geometry hash égal car mode de visualisation et non déplacement géométrique.
**G08** : deux oracles négatifs (trace de requête falsifiée, PNG altéré) rejetés.
**G09** : oracle archivé 01A et relance native 01A en mode fallback 01B qualifiés.
**G10** : Clippy -D warnings, build offline, tests workspace, format ciblé.
**G11** : contrats, références et SHA de preuves intégrés au même dépôt main.
**G12** : commit ciblé, push GitHub privé, correspondance SHA avec origin/main, aucune intervention sur G04B/H.

## Anti-contextes

Ne pas importer des sources ArtCraft, GPUI ou GPL sans validation de licence; ne pas transférer l'autorité du thème ou de Gnosix. Ne pas remplacer le renderer SDF, déplacer le programme vers worktrees orphelins, fabriquer des pixels, modifier Hyprland ou inventer des qualifications FPS/HID/compositor.
Le laboratoire Weston est test-only; aucune preuve de présentation réelle du compositeur, HDR, accessibilité AT-SPI, saisie IME, moteur 3D, P1 complet, GPU SDF, CP03 HYBRID-60 ou autonomie Gnosix.

## Sortie

SCOPED PASS seulement après réception exacte des gates. Suite recommandée : 01C généralisation de la scène, primitives et transforms/clips/texte/focus, et troisième composant fonctionnel avec tests réels.
