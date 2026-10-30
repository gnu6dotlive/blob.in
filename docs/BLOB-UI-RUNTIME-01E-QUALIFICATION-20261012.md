# BLOB-UI-RUNTIME-01E — Qualification des vrais tracés vectoriels

**Contrat :** contracts/BLOB-UI-RUNTIME-01E-CONTRAT-20261012.md.
**Vérificateur :** python3 scripts/blob_ui01e_verify.py.
**Reçu :** evidence/runs/blob-ui-runtime-01e-20261012/qualification.json.

## Nouveau capital technique
La bibliothèque indépendante blobin-ui-scene dispose de StrokeSegment, Point2, stroke_polyline, transformation/clipping hiérarchiques. La display-list et la composition comptent les segments dans la limite GPU partagée de 64. L'adaptateur wgpu conserve son unique pipeline, buffer uniforme et bind group; le shader prend en charge soit un rectangle arrondi, soit un segment de ligne en distance signée avec bouts arrondis.

## Banc de preuve native
Sous un Weston privé user/net isolé et l'application de production, l'instrument optionnel 01E ajoute 51 rectangles décoratifs et 4 segments verts à 9 commandes des trois vrais contrôles. Les quatre lignes sont de véritables traits, non des rectangles simulant leur apparence. Le total est 64 commandes, 4 couches. La caméra est décentrée initialement seulement dans le laboratoire, puis deux clics Réinitialiser fournissent deux frames CPU SDF réelles, sans troisième requête. La sortie GPU client est capturée avant queue.present, en PNG et RGBA gzip sans perte. L'oracle indépendant vérifie les centres des 51 rectangles, les 4 pixels des segments, des témoins noirs à l'extérieur, les anciens composants, les empreintes et les rejets de preuves falsifiées.

## Limites à respecter
Pas de texte autonome, Bézier, stroke joins paramétrables, remplissage de chemins, clip courbe ou rotation générale. Ce banc ne mesure pas FPS, latence ou retour wp_presentation et n'établit aucune propriété de 60 FPS / SDF GPU / CP03 HYBRID-60. L'input et la typographie restent egui-owned. Les travaux G04B/H en cours restent hors commit.
