# BLOB-UI-RUNTIME-01D — Qualification d'une scène native composée

**Contrat :** \`contracts/BLOB-UI-RUNTIME-01D-CONTRAT-20261012.md\`
**Reproduction intégrale :** \`python3 scripts/blob_ui01d_verify.py\`
**Reçu :** \`evidence/runs/blob-ui-runtime-01d-20261012/qualification.json\`
**Oracle pixel seul :** \`python3 scripts/blob_ui01d_oracle.py --source evidence/runs/blob-ui-runtime-01d-20261012/native\`.

## Surface de production

Les trois contrôles réels (Contours, Distance, Réinitialiser) sont désormais transmis par \`blobin-ui-scene::composition::compose\` à l'encodeur wgpu actuel. La composition reçoit les surfaces G02 \`0x10A\`, \`0x10B\` et \`0x10C\`, conserve leur ordre, identités, révisions, et vérifie clips et transformations. En mode normal elle produit **3 couches / 9 commandes**. Le passage GPU est le même et le texte/les interactions sont toujours possédés par egui.

Les tests du core couvrent deux transforms composées, douze ancêtres, clips hiérarchiques, invisibilité isolée, ordre stable, surface/node dupliqué, coordonnées invalides et limite 64/65. \`solid_rectangle\` expose une primitive axis-aligned sans rayon, **pas** des objets vectoriels génériques, path tessellation ni transforms affine arbitraire.

## Witness native 64 commandes

Le test de charge est opt-in uniquement sur une **nouvelle session Weston privée**, avec un nouveau plugin seat \`blob-ui-01d-private-*\` et les drapeaux d'activation du banc. Il ajoute 55 formes strictement décoratives aux 9 commandes des trois vrais contrôles. Le vrai binaire \`blobin-showcase\` sur GPU RTX 3070/Vulkan exécute une seule passe wgpu, avec l'arène et le bind group persistants du jalon 01B; \`ui01d_scene_submit\` enregistre 4 couches et 64 commandes réellement envoyées à l'encodeur. Le vrai \`blobin_renderd\` CPU sert deux révisions 3/4 à la scène; aucune substitution par le serveur de mires.

Un buffer original RGBA 1280×800 est capturé via \`COPY_SRC\` sur la vraie surface cliente, reconstitué en PNG sans perte et archivé gzip. L'oracle vérifie les **55 centres** à la valeur exacte \`(224,70,130,255)\`, plus trois points hors fixture inchangés. SHA-256 de l'archive, logs originaux de Weston/Render Bridge/production et événements permettent la requalification. Les deux tests négatifs doivent rejeter une trace fabriquant 65 commandes et une image PNG altérée.

La qualification constitue une preuve de **capacité bornée de composition + rendu**. Elle n'est pas un benchmark de FPS ni une démonstration de 64 widgets interactifs. Le \`COPY_SRC\` a été fait **avant** \`queue.present\` : aucun accusé \`wp_presentation\`, écran physique ni latence photons n'est prouvé.

## Régressions et limites

Les vrais bancs 01A, 01B et 01C sont rejoués sur le binaire produit par 01D, sans réécriture de leurs reçus historiques. Le banc 01D ne touche jamais l'entrée Hyprland et le code renderer SDF/workers reste inchangé.
Tous les chemins G04B/H non committés ont été exclus du staging et laissés byte-identiques. Code 01D first-party uniquement, aucune source ArtCraft importée.

**Non qualifiés :** autonomie UI générale, typographie/IME, accessibilité AT-SPI, clipping de forme non rectangulaire, paths/Bezier, rotations/skews, device lost recovery, cross-vendor, feedback compositeur, GPU SDF, 60 FPS et CP03 HYBRID-60. BLOB-UI-RUNTIME-01 parent reste **OPEN**.

## Suite recommandée

01E : primitive path/stroke et interface de texte/focus fondée sur des besoins réels, qualification de latence avec feedback de présentation, et charges successives 16/32/64 pour mieux caractériser les coûts d'allocation/encodage. Ne pas promouvoir Gnosix/GPUI sur la seule base de 01D.
