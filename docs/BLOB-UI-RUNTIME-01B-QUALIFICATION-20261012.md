# BLOB-UI-RUNTIME-01B — Qualification native d'une seconde famille UI

**Date :** 2026-10-12.
**Contrat :** contracts/BLOB-UI-RUNTIME-01B-CONTRAT-20261012.md.
**Reproduction :** python3 scripts/blob_ui01b_verify.py.
**Dossier :** evidence/runs/blob-ui-runtime-01b-20261012/.

## Ce qui est intégré

Le vrai éditeur blobin-showcase possède deux contrôles graphiquement rendus par blob.in sur son unique swapchain :
- Contours de contrôle (G) : toggle, action UI-only, aucun nouveau calcul SDF.
- Distance : bouton sélectionnable, changement du vrai mode Coverage vers Distance, une unique nouvelle frame SDF sur le vrai blobin_renderd CPU.

Les deux réutilisent ControlLayoutHost, G02 (snapshot, identity, properties, revision), G03 (layout, bounds, clipping, geometry epoch), des commandes neutres dans blobin-ui-scene et un adaptateur wgpu à deux ressources GPU persistantes (uniform arena et bind group). Les six primitives sont dessinées en une passe avec les mêmes scissor que les zones calculées. Le buffer uniforme borné est mis à jour seulement si son contenu a changé. Les buffers temporaires réservés à la capture ne font pas partie du rendement production.
Les palettes sont toujours fournies par theme.rs et l'input, le focus, le texte par egui. Deux surfaces distinctes sont attribuées aux composants; les indices locaux des NodeIds peuvent être identiques sans collision.

## Test natif observé

Dans une session Weston privée et isolée avec un vrai blobin_renderd CPU, un premier clic artificiel à (985,344) active Distance. G02 progresse 1→2, les deux requêtes SDF ont révisions 3 et 4 et modes Coverage puis Distance. Les géométries SHA sont **identiques** car seule la visualisation change, tandis que les pixels de la frame changent réellement.
Un deuxième clic à (975,670) désactive le toggle Contours (G02 1→2) **sans** troisième requête SDF.
Les captures avant/après des deux zones proviennent de COPY_SRC du vrai framebuffer GPU de l'application avant queue.present. L'oracle indépendant vérifie les pixels de sélection et du pouce, les images PNG, les buffers RGBA gzip et leurs SHA. Deux preuves négatives modifiées sont rejetées.
Le banc 01A historique reste reproductible en lançant son instrument avec BLOB_UI_01B_LEGACY=1 : ses bounds originaux sont conservés et son oracle précédent est qualifié.

## Ce qui reste OPEN

La présentation effective du compositeur n'est pas mesurée. Ni HID réel, ni AMD/Intel, ni cadence 60 FPS, ni kernel SDF GPU, ni IME/AT-SPI natif, ni runtime UI autonome, ni P1 complet ou CP03 HYBRID-60 ne sont acceptés.
Les deux ressources persistantes suivies par l'adaptateur sont buffer uniforme et bind group, pas le total d'allocations GPU par wgpu/egui.
Les quatre chemins G04B/H préexistants demeurent non intégrés et intacts. Aucun code ArtCraft n'a été importé.

## Après 01B

01C : enrichissement de la display-list (transformations, clipping multiple, nouveaux composants), meilleure maîtrise des coûts GPU et parcours clavier/texte accessibles, en gardant les surfaces prouvées et le renderer SDF sous leurs autorités actuelles.
