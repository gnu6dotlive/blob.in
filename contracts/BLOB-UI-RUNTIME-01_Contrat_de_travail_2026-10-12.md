# BLOB-UI-RUNTIME-01 — Contrat de travail d'intégration native 2D

**Programme :** blob.in · capitalisation des travaux graphiques, UI et UX  
**Date de rédaction :** 12 octobre 2026  
**État :** **PROPOSITION DE CONTRAT — NON ENCORE AUTORISATION D'EXÉCUTION**  
**Destinataire :** propriétaire du programme gnu.in.labs  
**Cible principale :** `tension-atoi/blob.in-showcase`, dépôt **privé**, branche canonique `main`  
**Applications et domaines adjacents :** `gnos.ux`, Gnosix, `in.gnu.os`, `in.gnu6`  
**Objet :** transformer les capacités déjà qualifiées de blob.in en un **runtime d'interfaces 2D natif, réutilisable et progressivement autosuffisant**, en prenant l'éditeur blob.in existant comme premier consommateur intégré.

> **Clause de lecture.** Ce document fixe le travail à accomplir, ses responsabilités et ses critères de preuve. Il ne constate pas que toutes les capacités décrites sont déjà opérationnelles et n'autorise pas, à lui seul, une modification de code, une migration Gnosix, une publication, un changement de licence ou un déploiement.

---

## 0. Décision en langage simple

Construire **avec le moteur existant**, pas à côté de lui, une vraie application qui se sert progressivement de ses propres composants pour dessiner son interface et faire fonctionner ses interactions. Le moteur ne devient pas le propriétaire du thème de Gnosix, ni de ses actions système. Il devient un outil graphique réutilisable, capable d'appliquer les règles apportées par ses applications clientes.

La première application de référence doit être **l'éditeur blob.in déjà existant** : espace de travail géométrique, scène SDF, outils de manipulation, panneau d'inspection, contrôles, animations, interactions, rendu natif. Un laboratoire auxiliaire est permis pour isoler une panne, mais il ne constitue **jamais** le produit livré.

**Résultat attendu :** une chaîne cohérente où une intention utilisateur met à jour un état canonique explicite, conduit à une géométrie/layout calculés, produit une description de dessin attribuable, est rendue par un renderer clairement propriétaire de ses ressources, puis fournit une preuve du résultat à l'écran. Les fonctionnalités absentes restent signalées comme absentes.

### Formulation de l'engagement

- **Conserver** les implémentations, preuves et contrats déjà acquis.
- **Raccorder** les capacités aujourd'hui séparées sans changer silencieusement leurs propriétaires.
- **Remplacer progressivement** dans l'éditeur les éléments d'UI encore dépendants d'egui, une famille à la fois.
- **Rendre réutilisables** les composants génériques, sans transférer les responsabilités de Gnosix à blob.in.
- **Mesurer** le fonctionnement réel, avec preuve indépendante et critères falsifiables.
- **Intégrer et sauvegarder** chaque jalon qualifié sur le `main` privé, avec revue ciblée.

---

## 1. Origine de ce mandat — contexte complet de la discussion

### 1.1 Pourquoi blob.in existe

blob.in n'a pas commencé comme un simple gestionnaire de thème ou une bibliothèque de boutons. Son héritage porte sur les **champs de distance signée (SDF)**, les compositions géométriques, les opérations booléennes, les courbes, les matières/paramètres visuels, les transforms, les expérimentations CUDA/Vulkan et la transmission de frames natives. Le rendu 3D hybride a été étudié et possède son propre contrat d'acceptation, mais le produit priorise désormais les **interfaces 2D natives**. Le 3D demeure une extension éventuelle, et non une condition du runtime UI.

### 1.2 Pourquoi nous demandons une convergence

La recherche historique s'est déployée dans plusieurs laboratoires, branches, worktrees, harnais et contrats spécialisés. Les essais ont produit de vraies capacités; néanmoins, accumuler des preuves indépendantes sans les rattacher à l'application canonique rend le progrès difficile à percevoir et pousse les agents suivants à réexplorer des acquis. L'opérateur a rejeté explicitement cette dynamique : **une recherche doit revenir nourrir le tronc commun**. Les worktrees ne sont pas interdits, mais leur usage doit être justifié et leur sortie intégrée.

### 1.3 Ce qui distingue la direction technologique

L'hypothèse d'intérêt de blob.in ne repose pas sur une prétendue exclusivité mondiale des GPU, de la géométrie SDF, du layout, des composants retenus ou des gestes transactionnels — ces techniques possèdent des équivalents dans d'autres moteurs. Le potentiel distinctif réside dans **leur articulation** : formes et matières calculables, UI structurée, layout déterministe, prévisualisation transactionnelle, rendu natif, séparation sémantique et provenance des frames. Cette intégration doit être démontrée sur un même usage réel avant d'être revendiquée comme capacité de produit.

### 1.4 Ce que GPUI représente — et ne représente pas

GPUI est un framework de présentation Rust utilisé actuellement dans Gnosix. Ce n'est pas l'autorité de marque, de thème, de politique utilisateur ou de mutation du bureau. Les composants `gnos.ux` actuels et leurs comportements utiles sont un capital d'ingénierie; ils peuvent fournir **des contrats et des cas d'essai**. Cela n'autorise pas à importer arbitrairement leur implémentation GPUI dans blob.in ni à faire du remplacement de GPUI une dépendance du premier jalon.

### 1.5 Les responsabilités de thème et de système sont distinctes

- `gnos.ux` définit, pour Gnosix, l'identité visuelle du produit, les composants métier, leurs états et les tokens de design.
- `in.gnu.os` possède les contrats explicitement admis de persistance et d'autorité système; il ne délègue pas des droits de mutation à un renderer.
- blob.in accepte des styles/tokens/contraintes **comme données d'entrée** et les projette visuellement; il ne décide ni des choix esthétiques du produit consommateur ni des permissions de l'utilisateur.
- Une application tierce utilisant blob.in demeure libre de définir son propre design system.
- `in.gnu6` possède, dans son périmètre, le modèle sémantique de scène, de temps et de topologie; blob.in n'acquiert pas cette ontologie parce qu'il en projette une image.

### 1.6 Pourquoi l'éditeur blob.in sert de banc d'intégration

Il possède déjà une scène géométrique concrète, des opérations visibles, des gestes, des contrôles et un renderer externe avec un contrat de frames. L'utiliser évite de bâtir une vitrine vide qui simulerait artificiellement le progrès. Chaque pièce intégrée doit améliorer une interaction réelle de cet éditeur.

---

## 2. État initial attesté / état inconnu

Les faits ci-dessous viennent des documents et de la consultation du dépôt local au 12 octobre 2026. Ils décrivent des preuves **bornées**, non une certification générale. **Avant exécution, l'intégrateur doit relever les nouveaux SHA, le statut de l'arbre et les receipts courants.**

| Ensemble | État acquis à préserver | Limite explicite |
|---|---|---|
| Application existante | `blobin-showcase` sous Wayland/Hyprland; éditeur SDF 2D, cercles, opérations CSG, pan/zoom, inspection, diagnostics | UI de production encore largement construite avec egui; moteur de rendu calculé distinct |
| Transport renderer | `BLOB-FRAME-v1`, frames attribuées reçues par IPC, memfd et contrôle d'intégrité; scheduler de révisions | Transport des pixels ne constitue pas une API UI universelle ni une preuve de cadence utilisateur |
| UI01 natif | Application labo winit/wgpu/Vulkan, formes organiques animées, rail, panneau inspecteur, ressorts, reduced motion; 180 soumissions et captures bornées | Le laboratoire n'est pas un toolkit public complet; pas de 60 FPS soutenus démontrés |
| UI-G02/A/B | `blobin-ui-core`, arbres identifiés, transactions, snapshots immuables, réconciliation par clés, invalidation typée et COW par pages | Pas une preuve que le renderer final ne redessine que les régions modifiées; pas une mise à jour persistante O(1) générale |
| UI-G03 | Layout headless déterministe, contraintes, DPI, clipping imbriqué, époques de géométrie | Pas encore une preuve générale de parité de layout avec un produit final sur tous les écrans |
| UI-G04/A | Focus, hit routing, capture, refus des événements périmés dans le core headless | Les preuves de laboratoire ne certifient pas tous les appareils ni tous les compositors |
| UI-G04/B/H | Pont natif Wayland/Vulkan; un essai Hyprland avec `uinput` virtuel et receipts existe localement | La preuve H était **non commitée** lors de la vérification; elle ne prouve pas un périphérique HID physique ni l'ensemble des scénarios |
| AC-01 | Contrat de geste `Begin → Preview → Commit/Cancel`, tests déterministes | Headless/portée initiale seulement |
| AC-02 | Consommateur natif Wayland avec deux cartes, six tests de scène | Une fenêtre/test de laboratoire n'est pas l'éditeur principal |
| AC-03 | Entrée de pointeur d'un Weston isolé vers `winit`, receipts corrélés, réordonnancement et trois échantillons pixel GPU avant/aperçu/après | Pixels lus dans le client GPU avant présentation : pas d'accusé de présentation du compositor ni de HID réel |
| **AC-04** | **Gestes transactionnels désormais adoptés dans le canvas de l'éditeur existant** : prévisualisation locale SDF, un commit et une invalidation, annulation/undo borné | Le canvas egui reste propriétaire de la capture; E2E du renderer BLOB-FRAME après commit encore non qualifié |
| CP03 / hybride | Protocole et instrumentation importants, essais GPU/Wayland bornés | `HYBRID-HERO-60@1` non livré; G01–G07 HOLD; aucun glissement d'acceptation vers les tests UI |
| Gnosix | Présentation actuelle `gnos.ux`/GPUI avec design tokens, composants et règles accessibles | Migration de Gnosix et suppression de GPUI non autorisées par le présent mandat |

**Ancrage observé localement :** sur `blob.in-showcase`, le `main` contenait `f364c69` — *adopt AC04 transactional gestures in production canvas*. Le chemin G04B/H comportait encore des fichiers modifiés/non suivis. Le statut `main...origin/main` ne signalait pas d'écart de commits à cette lecture. Cette observation doit être renouvelée; elle ne permet pas d'inférer un arbre propre.

**Ancrage adjacent :** le `main` local de Gnosix présentait une divergence avec `origin/main` dans une vérification précédente. **Ne pas intervenir dans Gnosix** au prétexte de réparer cette divergence dans le présent mandat.

### Documents de référence — à relire avant toute intervention

1. `README.md` et `docs/PROGRAM-INTEGRATION-SPINE-20261012.md`.
2. `contracts/BLOB-UI-G01-RUNTIME-CONTRACT-20261012.md` et `docs/BLOB-UI-G01-PRIMITIVE-LEDGER-20261012.md`.
3. `docs/BLOB-UI-G02B-INCREMENTAL-RECONCILIATION-20261012.md`.
4. `docs/BLOB-UI-G03-DETERMINISTIC-LAYOUT-20261012.md` et `docs/BLOB-UI-G04A-HEADLESS-INPUT-20261012.md`.
5. `docs/BLOB-AC-01-QUALIFICATION-20261012.md`, `docs/BLOB-AC-02-NATIVE-CONSUMER-QUALIFICATION-20261012.md`, `docs/BLOB-AC-03-QUALIFICATION-20261012.md`.
6. `contracts/BLOB-AC-04-PRODUCTION-UI-ADOPTION-20261012.md` et `docs/BLOB-AC-04-PRODUCTION-UI-QUALIFICATION-20261012.md`.
7. `docs/CP03-I01-SOURCE-TRUTH-AND-NEXT-ACTIONS-20261012.md` et `docs/QCHAIN-CP-JA7L-MATCHED-PIPE-RESULTS-20261012.md`.
8. Côté Gnosix, **lecture seule** : `ARCHITECTURE.md`, `AUTHORITY.md`, `crates/gnos-ux-gpui/src/product_design.rs`, `product_typography.rs`, et preuves d'accessibilité applicables.

Les chemins sont des indices de reprise; les SHA et la présence des fichiers priment. Aucun README ancien ne doit écraser une preuve plus récente.

---

## 3. Objectif produit, cible d'acceptation et définition de réussite

### 3.1 Objectif principal

Livrer un **éditeur blob.in 2D auto-hébergé par son runtime UI sur un périmètre défini**, en conservant la scène SDF existante et son propriétaire de rendu. Le consommateur principal ne doit plus dépendre d'egui pour les composants compris dans le périmètre accepté. Tout composant migré doit posséder une API, un état, une sémantique d'entrée, une représentation visuelle et une preuve de fonctionnement réel.

### 3.2 Expérience utilisateur de référence

Un utilisateur peut lancer l'éditeur sous une session Wayland, voir une scène SDF rendue par son moteur réel, choisir ou ajouter une forme, la déplacer avec prévisualisation, annuler ou valider, modifier une propriété dans un inspecteur, utiliser un panneau de navigation, naviguer au clavier, changer de dimensions de fenêtre, observer la réponse UI sans confondre aperçu local et rendu final, puis fermer l'application sans résidu anormal.

La démonstration doit distinguer explicitement deux objets :

- le **rendu géométrique canonique** calculé par le runtime blob.in et envoyé via BLOB-FRAME;
- les **surcouches UI** (contrôles, aides, aperçu non destructif) produites par le runtime d'interface.

Le résultat n'est accepté que si une action réelle conduit, à terme, à une nouvelle frame géométrique attribuable, et non uniquement à une animation des contrôles.

### 3.3 Périmètre fonctionnel minimal de sortie

- Canvas SDF réel avec ajout/sélection/déplacement d'une primitive et au moins une opération de composition déjà supportée.
- Preview, commit, cancel et undo du déplacement, sans double mutation ni double propriétaire de pointeur.
- Inspecteur éditant au moins une propriété réelle (valeur, validation, application, erreur).
- Navigation/rail, bouton, bascule, contrôle numérique ou champ, panneau et message d'état.
- Layout réactif au redimensionnement et au facteur d'échelle; zones d'entrée alignées sur l'image.
- Contrats de texte, focus, clavier et nom accessible explicites sur les composants migrés.
- États *chargement, erreur, indisponible, attente renderer, aperçu local et rendu confirmé* distincts.
- Au moins un consommateur autonome, compilable sans importer l'application showcase ni dépendre d'egui, à un jalon ultérieur explicitement identifié.
- Journal de preuves et état d'acceptation précis pour chaque fonctionnalité.

### 3.4 Deux niveaux de succès, à ne jamais confondre

**Succès A — intégration verticale utilisable.** Les composants ciblés de l'éditeur sont propulsés par blob.in, avec preuve E2E dans une session native. Certains éléments non migrés peuvent encore utiliser egui, **à condition d'être identifiés**.

**Succès B — runtime UI autonome.** L'éditeur complet pour le périmètre de référence et un consommateur indépendant utilisent les API publiques de blob.in sans recours à egui pour UI, layout, entrée, texte ou composition. L'accessibilité, les performances et les cas limites obtiennent leurs preuves propres. **B n'est jamais acquis par le seul succès de A.**

---

## 4. Invariants d'architecture et d'autorité

**A-01 — Un modèle de composant générique.** `blobin-ui-core` représente des identités et des transactions génériques. Ne pas y encoder `Workspace`, `Dock`, `AppStack`, choix de profil, utilisateur Linux ou politique système.

**A-02 — Une source canonique par donnée.** Une scène SDF est modifiée par son propriétaire actuel. Le runtime UI maintient l'état de ses composants et la projection temporaire d'un geste. Les deux états ne peuvent pas devenir deux vérités silencieusement divergentes.

**A-03 — Le renderer possède ses pixels.** Le code UI ne se proclame pas auteur des pixels BLOB-FRAME. Le renderer géométrique garde ses contrats de calcul, d'intégrité, d'epochs, de ressources et de scheduling. L'UI possède seulement les commandes de dessin de ses éléments et leurs compositions explicites.

**A-04 — Un propriétaire d'entrée à la fois.** Dans le canvas de production egui actuel, **egui conserve la capture et le hit-test** jusqu'à migration explicite. Ne pas superposer `InputRouter` sur la même séquence de pointeur. Après migration, le nouveau pont devient propriétaire sur un périmètre borné et sans double dispatch.

**A-05 — Tokens sans thème imposé.** Le runtime accepte palette, typographie, marges, rayons, épaisseurs de trait, opacités, matières autorisées et préférences de mouvement via un contrat neutre. Il ne contient pas les valeurs de marque de Gnosix comme politique de bibliothèque.

**A-06 — Sens du produit hors du renderer.** `gnos.ux` conserve l'assemblage et la sémantique métier de ses composants; `in.gnu.os` conserve ses autorités persistantes; `in.gnu6` conserve son ontologie de scène là où celle-ci s'applique.

**A-07 — Identité, génération et révision.** Un geste ou un hit ne peut pas s'appliquer à un objet supprimé, à une surface recréée ou à un layout d'une autre génération. Toute mutation canonique visible est attribuée à une révision traçable.

**A-08 — Snapshots non mutables.** Un renderer ne reçoit pas un état que l'UI modifie sous ses pieds. Les réconciliations G02 et layouts G03 existants restent la base, sauf contre-preuve documentée.

**A-09 — Preview ≠ rendu final.** Un ghost local, un transform temporaire ou une réutilisation de la dernière frame doit être marqué comme tel. Une confirmation de commit ne prouve pas que la nouvelle frame est déjà présentée.

**A-10 — Une responsabilité par ressource.** Fenêtre Wayland, surface wgpu, cache GPU, textures, gestion d'événements, scene state et persistance ont des propriétaires nommés. Aucune ouverture accidentelle d'un second cycle de vie GPU.

**A-11 — Portabilité du noyau.** `blobin-ui-core` et le contrat de scène affichable restent séparés de `showcase`, egui, GPUI, F4, Wayland et des détails des drivers. Les couches plateformes et renderers sont des adaptateurs explicites.

**A-12 — Extension 3D facultative.** Aucun jalon UI ne dépend d'un moteur de mesh 3D, d'opérations booléennes mixtes 3D ou de la clôture CP03.

**A-13 — Aucune amplification d'autorité.** Les clics sur des composants UI ne donnent pas accès à une mutation arbitraire du bureau, au lancement de commandes shell ou aux profils. Les intentions système doivent franchir les API autorisées du consommateur.

**A-14 — Accessibilité sémantique.** Un état désactivé, sélectionné, en focus, en cours de chargement ou en erreur doit être cohérent entre présentation, navigation, modèle d'action et représentation d'accessibilité; l'apparence seule ne suffit pas.

**A-15 — Preuve proportionnée.** Un test source ne démontre pas une présentation Wayland; une texture GPU ne démontre pas le photon; un screenshot ne démontre pas l'entrée; un benchmark F4 ne démontre pas la performance UI.

**A-16 — Compatibilité existante.** Tant que la nouvelle voie n'est pas acceptée, la voie egui existante doit pouvoir servir de référence et de retour arrière. Les changements ne doivent pas altérer silencieusement le comportement utilisateur accepté.

---

## 5. Anti-contextes explicites — ce que le mandat ne signifie PAS

Ces exclusions sont normatives. Elles protègent les décisions formulées au cours de l'échange et préviennent les dérives de futurs agents.

1. **PAS** « reconstruire blob.in de zéro », renommer tous les crates ou remplacer son pipeline entier pour paraître plus moderne.
2. **PAS** « créer une nouvelle application vitrine » et déclarer le moteur livré sur la base d'une vidéo ou d'un laboratoire réussi.
3. **PAS** « relancer UI-G02/G03/G04/AC01–04 depuis le commencement » lorsque leurs engagements ont déjà des preuves valides et attribuables.
4. **PAS** « multiplier les worktrees permanents ». L'intégration normale se fait sur `main` avec commits petits et réconciliés; une branche exceptionnelle a un propriétaire, une cible de merge et une condition de fermeture.
5. **PAS** « changer le renderer SDF pour résoudre un problème de widgets » sans preuve et mandat distinct.
6. **PAS** « faire passer une image de preview pour du SDF fraîchement calculé ».
7. **PAS** « mettre deux routers de pointeur sur le même canvas egui ».
8. **PAS** « faire de blob.in l'autorité de thème de Gnosix »; il fournit le mécanisme, l'application conserve les choix.
9. **PAS** « faire de GPUI l'autorité de marque ». Ses types et primitives sont un détail d'adaptation actuel dans `gnos.ux`.
10. **PAS** « copier-coller tous les widgets de `gnos-ux-gpui` vers blob.in ». Extraire le contrat générique; les composants de bureau restent dans Gnosix.
11. **PAS** « migrer Gnosix immédiatement », effacer GPUI, déplacer ses services ou toucher à son `main` divergent.
12. **PAS** « intégrer un runtime GTK, Qt, Electron, QML ou navigateur » comme solution de remplacement cachée; les fournisseurs temporaires doivent être déclarés et bornés.
13. **PAS** « déclarer blob.in compétitivement unique » sans tableau comparatif et preuves spécifiques, ni promettre qu'il remplace aujourd'hui GTK/GPUI/Slint/Rive.
14. **PAS** « prétendre que SDF, GPU, COW, transactions ou clipping sont des inventions exclusives ». L'originalité est une hypothèse de combinaison à démontrer.
15. **PAS** « mélanger `in.gnu6` et blob.in » au prétexte de leur affinité pour les scènes. Le propriétaire de l'ontologie sémantique reste explicite.
16. **PAS** « coupler le noyau UI à un seul backend ou à une seule marque de GPU ».
17. **PAS** « rendre le 3D obligatoire pour la sortie 2D » ni utiliser les tests UI pour modifier les seuils CP03.
18. **PAS** « abaisser CP03 HYBRID-60 » ni l'annoncer PASS à partir des observations à 31 FPS de QCHAIN ou d'une démo animée.
19. **PAS** « confondre `submitted`, `presented`, `observed`, `installed` et `released` ».
20. **PAS** « masquer une fonctionnalité manquante par un fallback silencieux, une maquette statique, un faux serveur ou un état synthétique crédible ».
21. **PAS** « ajouter une librairie pour éviter de résoudre une frontière architecturale » sans bilan maintenance, licence, taille et preuve.
22. **PAS** « importer les sources du donneur historique `blobin-core` GPL-3.0-or-later dans un dépôt actuellement propriétaire » sans revue et autorisation formelle.
23. **PAS** « présumer que l'intention de favoriser MIT vaut droit automatique de re-licencier chaque code existant ou dépendance tierce ».
24. **PAS** « publier le dépôt privé ou des captures accidentelles du bureau personnel ».
25. **PAS** « lancer des tests GPU destructifs, provoquer des resets de driver, ou injecter des entrées dans une session active sans garde et périmètre autorisé ».
26. **PAS** « utiliser GitHub Actions comme banc expérimental »; utiliser des scripts locaux reproductibles et archiver les receipts.
27. **PAS** « supprimer les branches/worktrees/untracked evidence parce que main semble contenir tout le code ». Vérifier les SHA et l'inventaire des fichiers hors Git.
28. **PAS** « optimiser d'abord des FPS sur une fixture artificielle » avant d'avoir une vraie scène, de vraies interactions et une attribution rigoureuse des frames.
29. **PAS** « considérer un rendu joli comme une preuve de texte, IME, focus, lecteur d'écran, récupération GPU ou stabilité mémoire ».
30. **PAS** « annoncer production ready à la fin d'une phase partielle ». Chaque obligation ouverte reste ouverte, même si son voisin est réussi.

---

## 6. Carte des composants, des dépendances et des propriétaires

### 6.1 Architecture logique cible

```text
 Application cliente (éditeur blob.in ; plus tard Gnosix/autres)
 ├── Intention produit, scène métier et permissions : autorité APP
 ├── Thème résolu / design tokens / motion policy : autorité APP
 └── Composants génériques : API publique blob.in
       │
       ▼
 blobin-ui-core (G02/G03/G04, état, layout, transactions, focus)
       │ snapshot déterministe + sémantique + styles résolus
       ▼
 blobin-ui-scene [à livrer] (commandes de dessin attribuables)
       ├── formes 2D / traits / clipping / transforms / opacité
       ├── texte et propriétés sémantiques
       ├── surfaces/frames de scène SDF comme ressources externes
       └── régions invalidées et epochs
       │
       ▼
 blobin-ui-render-wgpu [à livrer] + blobin-ui-platform-wayland [à livrer]
       │ ressources UI GPU, Wayland, événements, feedback attribué
       ▼
 Fenêtre native et pixels UI

 Pipeline SDF existant (autorité renderer distincte)
  SceneState + Scheduler → Render Bridge/F4 → BLOB-FRAME-v1
                                             │ frame id/hash/epoch
                                             └──────→ surface SDF du canvas UI
```

Les noms de futurs crates reprennent les **frontières logiques** du contrat UI-G01. Leur existence physique n'est pas présumée; un découpage en modules internes est recevable si les barrières de dépendances sont vérifiables.

### 6.2 Registre d'autorité

| Élément | Propriétaire de vérité | Le présent chantier peut-il le modifier ? |
|---|---|---|
| Formes et paramètres de la scène SDF de l'éditeur | Éditeur blob.in / SceneState canonique | Oui, par commandes déjà admises, de façon atomique |
| Calcul des pixels SDF | Renderer F4/Bridge propriétaire | Non, hors mandat explicitement approuvé et preuve distincte |
| État, layout, focus et transactions des composants UI | `blobin-ui-core` | Oui, dans son contrat public |
| Production d'une display-list UI | Nouveau domaine `blobin-ui-scene` | Oui, via API indépendante du renderer |
| Composition finale UI | Adaptateur renderer explicitement désigné | Oui, sous preuve de propriété des ressources et compatibilité |
| Capture de pointeur canvas actuel | egui tant que le canvas egui reste actif | Non, pas de second router concurrent |
| Thème d'un produit client | Produit client; `gnos.ux` pour Gnosix | Lecture/consommation de tokens, pas transfert d'autorité |
| Préférences et mutations de bureau Gnosix | `in.gnu.os` / composants propriétaires | Non |
| Sémantique de scène `in.gnu6` | `in.gnu6` | Non |
| Publication/licence/visibilité | Opérateur et détenteurs des droits | Non, sans autorisation spécifique |

### 6.3 Schémas contractuels à définir

- `UiSnapshot` / `LayoutSnapshot` existants : préciser champs publics, epochs et interdictions de mutation.
- `ResolvedStyle`: valeurs de rendu résolues — couleur, spacing, rayon, trait, typographie, matériau compatible, mouvement réduit — indépendantes du produit et de GPUI.
- `DisplayCommand`: `Fill`, `Stroke`, `Path`, `TextRun`, `Clip`, `Transform`, `OpacityLayer`, `ExternalFrame` et bounds/damage associés. Ne pas inventer de commande sans consommateur prouvé.
- `ExternalFrameRef`: identifiant de scène SDF, révision de commande, format, dimension, intégrité, statut de fraîcheur.
- `RenderReceipt`: source UI revision, layout epoch, SDF frame ID (si présent), GPU submit ID, feedback Wayland si réellement disponible.
- `InteractionReceipt`: origine native, cible typée, capture/focus, previews, commits, cancels, mutation canonique et invalidation.
- `ThemeSource`/`ThemeSnapshot`: entrée du consommateur, version, fallback explicite, sans écriture persistante par le renderer.

Les structures ci-dessus sont des **exigences de contrat**, pas des API déjà compilées.

---

## 7. Plan de travail séquencé et borné

Les phases sont **ordonnées par dépendance**, non par calendrier artificiel. Chaque phase doit livrer code + tests + preuves + mise à jour d'index + décision d'intégration. Il faut privilégier un incrément utilisable dans l'éditeur à chaque fermeture de jalon.

### PHASE P0 — Établir la ligne de base, sans régression

**Mission :** retrouver exactement l'autorité canonique et conserver les travaux encore non suivis.

**Travaux :**

1. Relever HEAD local/remote, statut du dépôt, worktrees, chemins sales, versions Rust, dépendances et host d'essai.
2. Vérifier les receipts G02/G03/G04 et AC01–04, sans rejouer des essais matériels déjà fermés sans hypothèse nouvelle.
3. Inspecter séparément les preuves G04B/H non commités; ne rien écraser.
4. Dresser la matrice « déjà disponible / disponible via egui / historique donneur / manquant / bloqué par licence ».
5. Établir des tests de régression rapides de l'éditeur existant et un comportement utilisateur de référence avant migration.
6. Identifier le propriétaire renderer/bridge et les modifications interdites de ses fichiers.

**Livrables :** `BASELINE.md`, table d'API et dépendances, inventaire des états sales, SHA/versions et script de qualification minimal.  
**Gate P0 :** base reproductible, propriétaire de chaque composant nommé, aucune preuve perdue, aucun nouveau renderer de substitution.  
**STOP :** arbre sale non classifié, divergence du remote, provenance source douteuse, ou tests de référence impossibles à reproduire.

### PHASE P1 — Scene/display-list UI découplée de l'application

**Mission :** rendre possible une composition UI propriétaire de ses commandes graphiques, sans dépendre d'egui.

**Travaux :**

1. Construire le contrat de display-list indépendante de Wayland/wgpu/egui.
2. Faire correspondre `UiSnapshot` + `LayoutSnapshot` à des commandes attribuées, avec bounds et clips.
3. Implémenter la sortie pour un sous-ensemble minimal : rectangles, lignes/traits, remplissages, transform, clipping, opacity et primitive vectorielle contrôlée.
4. Introduire un adaptateur de rendu local qui respecte l'unique propriétaire des ressources GPU UI.
5. Construire un oracle de référence indépendant des appels de rendu (ordre des commandes, bounds, clips, révisions) et un oracle pixel sur une scène fixe.

**Livrables :** API de scène, test unitaire et pixel-oracle, au moins une petite zone d'UI réelle rendue avec ce chemin dans l'éditeur, avec commutateur de comparaison contre la voie actuelle.  
**Gate P1 :** sortie native attribuable sans import egui dans le cœur; même layout cohérent entre hit regions et dessin; pas de création d'une seconde fenêtre cachée.  
**Hors P1 :** moteur de texte complet, migration Gnosix, matériau SDF universel.

### PHASE P2 — Composer la vraie frame SDF avec l'UI native

**Mission :** obtenir une première chaîne utile géométrie → frame propriétaire → UI → présentation.

**Travaux :**

1. Consommer les frames réelles `BLOB-FRAME-v1` dans une commande de canvas `ExternalFrame`, avec génération et validation de format/stride/size.
2. Conserver le scheduler de la scène SDF; ne pas recalculer à chaque preview.
3. Dessiner le ghost/aperçu comme couche transitoire explicitement étiquetée, puis retirer cette couche après commit et confirmation de la frame canonique appropriée.
4. Séparer les révisions UI, layout, scène SDF, requête et frame présentée; documenter l'ordre et les retards acceptables.
5. Tester erreurs, stale frame, resize, suppression de cible, invalidation GPU, surface perdue et reprise sans fausse confirmation.

**Livrables :** canvas de l'éditeur rendu/composé par le nouveau chemin, traces corrélées, captures natives sans autre fenêtre privée, invalidation exactement une fois au commit sur le cas défini.  
**Gate P2 :** une opération réelle de l'utilisateur provoque une modification de scène et **une nouvelle frame provenant du véritable renderer**, confirmée par un oracle indépendant.  
**STOP :** contenu rendu localement mais présenté comme sortie du moteur SDF; mismatch de génération; double scheduler.

### PHASE P3 — Entrées, gestes, focus et texte utiles à l'éditeur

**Mission :** faire migrer une interaction réelle de l'éditeur sans dupliquer la capture egui.

**Travaux :**

1. Choisir un **seul** périmètre possédé par le router blob.in; conserver le reste à egui tant que nécessaire.
2. Rejouer la sémantique AC04 et AC01 dans le nouveau pipeline, avec reconduction de previews, une mutation canonique, undo/cancel, blur et resize.
3. Installer des événements de focus et de navigation clavier avec des identités stables de composants.
4. Construire un minimum texte exploitable : mesure et shaping appropriés au périmètre, étiquettes, champs numériques éditables, curseur/sélection, validation; traiter IME international comme une gate à part plutôt que le déclarer supporté sans essai.
5. Faire correspondre le nom, rôle, état et action du contrôle à son comportement réel; définir le pont d'accessibilité requis et signaler les omissions.

**Livrables :** interaction canvas réelle et un champ d'inspecteur sur blob.in, tests clavier/pointeur, journal entrée → cible → action → frame, rapports d'accessibilité mécanique.  
**Gate P3 :** chaque événement ne produit qu'une activation; un champ modifie réellement la scène; Escape/annulation n'altère pas la source canonique; pas de dépendance cachée à des boutons egui pour ce périmètre.  
**STOP :** double capture, focus fantôme, nom accessible trompeur, modification lors du preview, faux support IME.

### PHASE P4 — Bibliothèque de composants génériques et tokens

**Mission :** obtenir des primitives suffisamment utiles pour bâtir l'interface de référence.

**Travaux :**

1. Factoriser Button, Toggle, Panel, Rail/NavItem, Label, NumericField, InspectorRow, Status, Tooltip, ScrollContainer selon les besoins **réels** de l'éditeur.
2. Réutiliser les contrats de focus, disabled/selected, animation réduite et visibilité; ne pas coder des composants seulement décoratifs.
3. Permettre un `ResolvedStyle` apporté par l'application et des règles de responsive layout indépendantes du backend.
4. Analyser en lecture seule les composants de `gnos.ux`/GPUI : distinguer concepts génériques des composants particuliers du bureau.
5. Construire un adaptateur de design tokens, sans recopier les types `gpui::Rgba`, `Div`, `FocusHandle` dans les API centrales.
6. Documenter variants, tailles, marges, rayons, traits, focus, erreur, loading, reduced motion; les tokens par défaut de blob.in ne prétendent pas être ceux de Gnosix.

**Livrables :** catalogue utilisable et tests de comportement pour chaque contrôle du périmètre; comparateur visuel/résolution; carte de provenance de concepts GPUI.  
**Gate P4 :** au moins les contrôles requis par l'éditeur ont une action fonctionnelle, état typé, clavier et thème externe; aucun composant métier Gnosix n'est transféré dans le core.  
**STOP :** le moteur fixe lui-même l'identité de marque ou réimplémente des règles métier de workspaces.

### PHASE P5 — Matières, géométrie vectorielle et mouvement comme capacités du runtime

**Mission :** capitaliser la spécificité graphique plutôt que de produire un simple clone de widgets.

**Travaux :**

1. Identifier les formes déjà **réellement** disponibles (CSG de cercles dans l'éditeur, vecteurs organiques UI01, chemins Bézier historiques sous réserve de licence).
2. Introduire des primitives de forme/style génériques et testables dans le modèle de scène UI; éviter toute dépendance à un SDF hybride 3D absent.
3. Définir exactement les matériaux pris en charge — remplissage, contour, gradient ou effet seulement si une implémentation et un oracle existent; un « matériau » n'est pas une promesse de simulation physique.
4. Retargeter animations à partir de l'état courant, avec durée/delta bornés, no-op au repos et politique reduced motion.
5. Attribuer invalidation de composant, damage UI et invalidation du renderer SDF à leurs propriétaires respectifs.
6. Mettre un exemple réel dans l'éditeur : une forme de contrôle non rectangulaire ou un panneau animé dont la géométrie affecte correctement le hit-test.

**Livrables :** un composant géométrique animé intégré au travail utilisateur, diagnostics de rendu, tests de clips/transform/hit, preuve d'inactivité au repos.  
**Gate P5 :** comportement visuel et interaction partagent les mêmes bounds/transformations; aucune revendication de « vraie matière » ou de « moteur 3D unifié » non prouvée.  
**STOP :** forme déformée dessinée à un endroit tandis que sa zone cliquable reste l'ancien rectangle.

### PHASE P6 — Premier éditeur blob.in auto-hébergé sur son propre runtime UI

**Mission :** faire du produit existant la preuve maîtresse, pas une vitrine dédiée.

**Travaux :**

1. Migrer par famille l'UI de l'éditeur tout en maintenant le parcours utilisateur intact.
2. Exposer un seul hôte natif autoritaire; les contrats de scène, focus et entrée doivent être compatibles avec le renderer de géométrie existant.
3. Retirer egui des **chemins migrés**; puis viser, pour la sortie complète B, l'absence de dépendance egui dans le binaire de référence.
4. Couvrir sélection, ajout, CSG, édition d'une propriété, viewport, undo/cancel, navigation, diagnostics, erreurs de runtime et fermeture.
5. Vérifier la récupération après perte/recréation de surface; deux surfaces si ce scénario fait partie de la gate de runtime portable.
6. Interdire un « mode démonstration » qui remplace discrètement les frames SDF par des mires synthétiques.

**Livrables :** application existante réellement utilisable, script de scénario utilisateur, captures, traces, diff de dépendances, liste fermée des composants encore adaptés à egui le cas échéant.  
**Gate P6A :** usage courant défini possible sans régression majeure, et composants ciblés auto-hébergés.  
**Gate P6B :** application de référence sur blob.in UI complet sans egui pour ses fonctions du périmètre et sans autorité système superflue.  
**STOP :** disparition d'une fonction utilisateur sans remplacement, ou panneau visuellement équivalent mais inopérant.

### PHASE P7 — API publique interne et second consommateur indépendant

**Mission :** prouver que blob.in n'est pas uniquement un éditeur codé sur mesure.

**Travaux :**

1. Établir des exports documentés, versions de contrats, exemples courts et compatibilité compilée.
2. Construire une application indépendante dans `examples/interface-workbench` ou un package consommateur séparé, **sans importer le binaire ou les modules privés du showcase**.
3. Couvrir un canvas vectoriel simple, un inspecteur, une liste défilante utile, une action réelle, une animation, redimensionnement, clavier et fermeture.
4. Vérifier les barrières de dépendances, packaging, licenses et absence de couplage à l'environnement d'une station particulière.

**Livrables :** second consommateur reproductible, API stable **pour le périmètre indiqué seulement**, guide d'intégration, tests hermétiques et native E2E.  
**Gate P7 :** compilation et exécution sans imports egui/GPUI/showcase au cœur du consommateur; API documentée suffisante pour réutiliser les primitives.  
**STOP :** le second consommateur n'est qu'une copie de dossier du premier.

### PHASE P8 — Compatibilité Gnosix / GPUI (option indépendante)

**Mission :** rendre techniquement envisageable une substitution de renderer sans ouvrir une migration non autorisée.

**Travaux permis en lecture seule :** inventorier `gnos.ux` : tokens, contrôles, states, focus, keyboard traversal, rôles d'accessibilité, surface management. Proposer une interface de tokens neutre, un adaptateur GPUI et un adaptateur blob.in; mesurer par une preuve isolée **sans toucher au `main` Gnosix**.

**Livrable :** matrice de parité/écarts et proposition de migration incrémentale par composant.  
**Gate P8 :** aucune affirmation de remplaçabilité tant que les tests de parité, fonctionnalités de bureau et autorités ne sont pas qualifiés.  
**Non autorisé ici :** suppression de GPUI, remplacement du Dock/Bar en production, changement de thème global, modification `in.gnu.os`, déploiement de Gnosix.

---

## 8. Matrice de vérification transversale

Les verdicts sont produits par **phase et par scénario**, jamais par satisfaction générale. Les tests se rangent par niveau de preuve.

| Gate | Instrument minimal | Ce qu'un PASS autorise à dire | Ce qu'il n'autorise PAS |
|---|---|---|---|
| G-BASE | Git SHA, arbre, deps, receipts, ancien parcours fonctionnel | Base auditée et reproductible | Moteur complet |
| G-MODEL | Tests déterministes G02, rollbacks, snapshots, stale IDs | Modèle UI et transitions corrects dans le périmètre | Rendu réel affiché |
| G-LAYOUT | Fixtures dimension/DPR/clip/transforms, oracle géométrique | Layout défini correct | Clic Wayland arrivé |
| G-SCENE | Oracles display-list et ordre/clip/damage | Commandes de dessin attribuées | GPU et présentation qualifiés |
| G-PIXELS | Lecture pixels GPU et captures compositables, état vérifié | Image client/capture correspondante sur fixture | Photons, latence, 60 FPS |
| G-INPUT | Entrée livrée à `winit`, receipts sans double propriétaire | Chemin native input prouvé sous compositor nommé | HID matériel universel |
| G-SDF | BLOB-FRAME réelle avec ID/hash/revision et comparaison indépendante | Effet d'un commit sur rendu SDF réel | Toutes opérations 3D, toute précision |
| G-COMPONENTS | Tests état/erreur/disabled/focus/clavier/visuel | Composants fonctionnels ciblés | Suite UI universelle |
| G-TEXT | Shaping, sélection, édition, saisie, Unicode; essais IME séparés | Texte et champs pour cas testés | Toutes langues/IME sans test |
| G-A11Y | Rôles, noms, actions, focus + observation AT-SPI si disponible | Mécanique accessible du périmètre | Audit humain de tous les lecteurs d'écran |
| G-PERF | Mesures sur binaire, scène et machine nommés; compositor feedback | Résultats chiffrés bornés | Garantie générique de FPS/latence |
| G-RECOVERY | Resize, scale, close/reopen, SurfaceLost, Timeout, stale frame | Reprise contrôlée sur cas testés | Robustesse multi-matériel totale |
| G-PORTABLE | Consommateur indépendant clean-build | API réutilisable démontrée | Distribution publique autorisée |
| G-RIGHTS | Provenance/source/licence et tiers vérifiés | Redistribution selon permissions explicitement établies | Re-licenciation rétroactive implicite |

### 8.1 Tests négatifs indispensables

- Un `Preview` ne change pas `SceneState`, la caméra canonique ni le compteur de requêtes SDF.
- Un `Cancel` ou un no-op ne déclenche pas de nouvelle évaluation SDF.
- Un `Commit` ne déclenche pas deux invalidations pour une même action.
- Le relâchement ne revient pas à un delta zéro à cause d'egui 0.36 (régression AC04).
- Escape, blur, viewport epoch périmée, coordonnées NaN/Inf et cible supprimée échouent proprement.
- Le reparent/reorder ne réaffecte pas le focus à un contrôle sémantiquement différent.
- Une frame tardive ne remplace pas une frame plus récente en la prétendant courante.
- Une capture de source non désirée, une fenêtre privée incidente ou une divergence de SHA invalide l'archive.
- Une action de préférence Gnosix ne peut pas devenir une commande shell générique par le renderer.
- Un état disabled ne reste pas activable au clavier ou par accessibilité.
- Une erreur de device/window se traduit en état typé, pas en faux succès silencieux.

### 8.2 Performance, sans promesse préalable

L'objectif produit est une UI native fluide et économe; ce n'est pas encore une valeur prouvée. Définir **avant** campagne le scénario `BLOBIN-UI-60` avec résolution, nombre de nœuds, animation/idle, scène SDF, GPU/driver, état d'alimentation, frame IDs et durée. Mesurer soumissions, feedback Wayland réels, percentiles, latence entrée→présentation, mémoire/ressources, activité GPU/CPU au repos, erreurs et récupération. Fixer puis ratifier des seuils qui ne changent pas en fonction du résultat. La preuve CP03 HYBRID-60 reste **séparée**.

---

## 9. Politique de livraison, de sauvegarde et de reprise

### 9.1 Discipline des modifications

- Référentiel canonique blob.in : `/home/tension_atoi/Projects/blob.in-showcase` → `tension-atoi/blob.in-showcase` **privé**.
- Utiliser `main` pour les tâches sérielles et bornées après qualification de l'arbre courant.
- Commit ciblé, tests ciblés puis régressions de workspace, receipt, index, push privé; comparer SHA local et distant.
- Ne pas exécuter `git add -A`, un formatage global ou un nettoyage destructif si des fichiers G04B/H d'un autre chantier restent sales.
- Ne pas masquer des modifications préexistantes par un commit de contrat; isoler précisément la liste des fichiers du jalon.
- Worktree seulement si concurrence réelle, essai dangereux ou obligation d'isolation; noter propriétaire, branche parent, objectif et plan d'intégration à sa création.
- Un jalon fermé doit être intégré au `main` privé, ou explicitement classifié `HOLD` avec conservation de ses données. **Ne jamais abandonner une branche « terminée » sans destination.**
- Une sauvegarde GitHub exige un `push` confirmé; un commit local ou une preuve hors repo ne suffit pas.

### 9.2 Retours des agents et handoff

Chaque retour doit rapporter dans cet ordre :

1. **Périmètre et phase** (ce qui était autorisé, ce qui ne l'était pas).
2. **SHA avant/après**, branche, tree dirty/clean, état remote, version d'environnement pertinente.
3. **Fichiers touchés**, raisons, contrats et propriétaires concernés.
4. **Tests exécutés** avec sorties exactes et toute omission `NOT_RUN`.
5. **Preuves** : manifests, hashes, captures tronquées à la fenêtre propre, événements attribués, contre-exemples.
6. **Verdict** `PASS / FAIL / HOLD / NOT_RUN / NOT_OBSERVED` par gate, sans synthèse abusive.
7. **Dette ouverte**, régression, retour arrière et prochaine intervention concrète.
8. **Statut commit/push** et preuve de présence sur `origin/main` privé.

### 9.3 Classe de gravité des blocages

- **STOP immédiat :** perte potentielle de preuve, droit de redistribution incertain, double autorité de pointeur, données privées capturées, GPU/desktop hôte menacé, altération du moteur géométrique sans propriétaire.
- **HOLD ciblé :** un instrument requis indisponible, une preuve native non reproductible, un scénario de texte/IME/accessibilité non fini, performance insuffisamment attribuée.
- **OPEN acceptable :** fonctionnalité hors périmètre du jalon, 3D différé, comparaison concurrentielle non finalisée, migration Gnosix non commencée.

### 9.4 Politique des licences

Les travaux first-party peuvent privilégier MIT **lorsque les titulaires de droits peuvent légalement l'accorder et que l'opérateur l'autorise**. Le dossier historique `blobin-core` contient du code sous GPL-3.0-or-later et le showcase privé possède des mentions propriétaires. Aucune préférence générale pour MIT n'efface ces régimes. Avant réutilisation de code, établir un tableau de provenance des contributions, copyright, dépendances et compatibilité; sans décision expresse, **réimplémenter le comportement par une source première indépendante** ou conserver le donneur en référence de recherche, sans vendoring.

### 9.5 Sécurité et garde du poste

Pas de modification de configuration Hyprland permanente, d'injection de pointeur dans le bureau non surveillé, de reset GPU, de test thermique agressif hors garde ni d'exposition publique du dépôt. Les tests GPU lourds se déroulent selon les gardes de laboratoire déjà ratifiés (`gnu6-lab-run` lorsqu'applicable). Les fixtures Weston/virtual-seat restent des outils de laboratoire et ne sont jamais livrées comme capacité de production.

---

## 10. Critères de non-régression de l'existant

La fermeture du mandat exige que les opérations essentielles de l'éditeur restent disponibles et vérifiables : ouverture/fermeture de fenêtre; choix du backend réellement annoncé; ajout et sélection de cercle; changement de taille; opérations CSG exposées; pan/zoom; quatre états au minimum (actif, preview, erreur, rendu attendu); diagnostics sincères; résistance au resize; attente/reprise d'un renderer; undo compatible d'un mouvement; libération des descripteurs et textures sans fuite manifeste.

Une migration n'est pas réussie si elle produit une UI plus esthétique mais perd une action, accepte deux fois un clic ou affiche une scène obsolète sans le signaler. Le test de parité doit distinguer **identité visuelle**, **action sémantique**, **latence**, **accessibilité** et **restauration d'état**. Un compromis est autorisé uniquement s'il est documenté, isolé et accepté pour la phase concernée.

---

## 11. Risques anticipés, compromis et stratégies de repli

| Risque | Symptôme | Stratégie |
|---|---|---|
| Recréation d'un deuxième moteur UI | Deux arbres/layouts/routers maintenus en parallèle | Une API canonique G02/G03/G04; adaptateurs explicitement temporaires |
| Double entrée egui/blob | Clicks doublés, drag erratique, perte de capture | Périmètres disjoints, propriétaire unique et preuve d'ingress |
| Faux rendu SDF | Preview local présenté comme résultat GPU | Badge/état `LOCAL PREVIEW`, ID et révision de frame, oracle après commit |
| Couplage GPU/Wayland au core | Core impossible à tester sans fenêtre | Scène headless; adaptateurs de plateformes et renderer séparés |
| Texte insuffisant | Inspecteur impossible à éditer vraiment | Scoper champs et shaping, puis IME/accessibilité en gates dédiées |
| Import GPUI trop tôt | Dépendances circulaires ou composants Gnosix « natifs blob » fictifs | Lire les contrats Gnosix; reproduire les sémantiques génériques avec tests |
| Mauvaises licences | Dépôt privé réutilise GPL donneur en silence | Provenance et revue juridique avant copie; sinon clean-room |
| Perte d'intégration | Tests en branches mortes, preuves locales non sauvegardées | Main + commit + push + receipt + index à chaque étape |
| Optimisation prématurée | FPS d'un labo sans scène utilisateur | Scénario réel d'abord; protocole perf distinct et ratifié |
| Régression de récupération | SurfaceLost ou resize gèle l'éditeur | Outcome typé, test de fail/recover, retour arrière local |
| Confusion d'autorité | Le renderer écrit les settings/profils | Contrats de lecture de tokens uniquement; mutation via produit propriétaire |
| Champ de travail sans fin | Nouvelle bibliothèque de 100 widgets hors besoin | Inventaire des interactions réelles de l'éditeur et gates de phase |

---

## 12. Livrables physiques et structure documentaire

Chaque phase doit produire un sous-ensemble réellement justifié de ces artefacts dans le dépôt canonique :

- Contrat de phase et statut de gate mis à jour.
- Code Rust intégré dans des modules/crates possédés, sans dépendance introduite subrepticement.
- Tests unitaires, tests de propriétés/invariants, E2E compositor quand exigés.
- Oracle indépendant capable de rejeter des preuves truquées (falsification négative).
- Captures et buffers attribués à une fenêtre propre, ainsi que manifestes SHA-256.
- `qualification.json` ou équivalent avec les classes de résultat par gate, hardware/driver/commit et révisions d'objets.
- Guide opératoire court : lancer, manipuler, diagnostiquer, quitter, comprendre les limites.
- Matrice « ancienne UI / nouvelle UI » et conséquences des divergences.
- Mise à jour de `docs/PROGRAM-INTEGRATION-SPINE-20261012.md` ou de son successeur canonique sans réécrire l'histoire.
- Notification de fermeture : quelle capacité maintenant utilisable **dans l'éditeur**, pas seulement testée ailleurs.

Les archives de captures ou gros traces peuvent rester dans un stockage privé séparé si leurs références, hashes et règles de conservation sont explicites. **Ne pas inventer un lien GitHub pour une preuve toujours uniquement locale.**

---

## 13. Conditions de réception globale

Le mandat peut être annoncé « **BLOB-UI-RUNTIME-01 — intégration de référence terminée** » uniquement si :

1. L'éditeur canonique possède un parcours utilisateur complet, reproductible et sans perte sur le périmètre convenu.
2. Son UI ciblée utilise effectivement les composants et la chaîne de rendu blob.in, pas un laboratoire séparé déguisé.
3. Une action sur la scène conduit de l'entrée native à une mutation canonique, une frame SDF recalculée **par le renderer propriétaire**, une composition UI et une observation d'image attribuable.
4. La preview reste non destructive, le commit est unique, cancel/undo sont vérifiés et les frames retardées sont traitées sans mensonge d'état.
5. Layout, géométrie, clipping, hit-test, focus et actions désignent les mêmes cibles et les mêmes epochs.
6. Texte et composants utilisés sont testés au clavier; les mécanismes d'accessibilité supportés sont vérifiés et les déficits demeurent ouverts.
7. Un consommateur indépendant prouve la réutilisation des primitives; sinon, on ne clôt **que l'intégration verticale**, pas le runtime général.
8. Les preuves et limitations relatives aux performances sont publiées dans leur registre privé, sans déclarer `60 FPS`, `input-to-photon` ou `CP03 PASS` en leur absence.
9. La provenance, la licence et les dépendances de tout code importé sont vérifiées.
10. Tous les jalons achevés sont intégrés et poussés sur le dépôt privé, avec SHA et état d'arbre rapportés.
11. Les interactions et thèmes de Gnosix restent sous les propriétaires d'origine; aucune migration du bureau n'a été imposée.
12. Un agent futur peut reprendre sur `main` depuis l'index et les receipts sans refaire les preuves déjà clôturées.

### Résultat expressément insuffisant

Une capture séduisante, des composants fictifs, un projet de laboratoire isolé, un UI-G02 PASS historique, un benchmark Vulkan rapide, un screenshot GPU client sans cause native, ou une maquette de Dock Gnosix ne ferme **aucune** réception globale.

---

## 14. Ordre de mission initial, immédiatement actionnable après approbation

**Premier incrément recommandé : `BLOB-UI-RUNTIME-01A — Renderer-owned 2D scene dans l'éditeur existant`.**

1. Partir de `main`, relever ses SHA, classifier les fichiers sales G04B/H sans les modifier, vérifier AC04 et les tests de régression.
2. Identifier la plus petite zone de l'éditeur que l'on peut peindre via un `UiSnapshot → LayoutSnapshot → DisplayList → GPU` indépendant d'egui **sans toucher au renderer SDF**.
3. Produire **une** primitive native utilisable, par exemple un bouton/contrôle d'inspecteur qui réagit à un état réel et partage les bons bounds avec son hit-test.
4. Conserver l'existant egui en repli; ne jamais faire écouter la même séquence de pointeur par les deux systèmes.
5. Vérifier la projection avec oracle headless, pixels GPU et, si la gate le requiert, entrée Wayland réelle.
6. Exposer la preuve et les limites; ne pas revendiquer d'application complète après ce jalon.
7. Commit ciblé, sauvegarde privée sur `origin/main`, index mis à jour, état des travaux préexistants inchangé.

**Condition d'extension :** seulement après réception de 01A, enchaîner P2 puis P3. Une connexion du SDF au compositing vaut davantage qu'une dizaine de nouveaux widgets démonstratifs sans rendu canonique.

**Définition de la prochaine décision opérateur :** autoriser ou amender ce contrat et déterminer si sa première phase exécutable est `01A`. Cette décision **ne vaut pas** autorisation de publier blob.in, de modifier Gnosix, d'extraire le donneur GPL ni d'accepter CP03.

---

## 15. Glossaire et discipline de langage

- **Moteur de rendu :** exécute la représentation visuelle; n'est pas automatiquement propriétaire d'une scène métier ni d'un thème.
- **Runtime UI :** gère l'état des composants, le layout, l'interaction et le lien vers la présentation.
- **Design system :** ensemble de règles d'apparence et de comportement appartenant au produit consommateur.
- **Composant générique :** bouton, contrôle, liste, inspecteur, etc., avec contrat comportemental réutilisable, sans sémantique métier de bureau.
- **Canvas SDF :** viewport des primitives géométriques rendues par le moteur SDF; n'est pas l'ensemble du système UI.
- **Preview :** projection provisoire sans mutation canonique; n'est pas une frame finale recalculée.
- **Transaction :** opération avec début, aperçu et issue unique commit ou cancel.
- **Headless :** test du modèle sans affichage/gestionnaire de fenêtre; ne démontre pas la livraison d'un événement natif.
- **GPU readback :** lecture client des pixels GPU; ne démontre pas nécessairement leur présentation compositor ni leur apparition à l'écran physique.
- **Compositor feedback :** observation de présentation par le compositor, à distinguer du GPU submit et des pixels lus côté client.
- **Autorité :** droit de décider ou modifier un domaine; ni une dépendance technique ni une apparence visuelle ne l'accordent.
- **CAPITALISATION :** rendre l'acquis réutilisable, intégré, sauvegardé, retrouvé et attribuable.

---

## 16. Provenance et statut de rédaction

Ce document synthétise l'échange du 12 octobre 2026 et les sources du dépôt privé disponibles durant la conversation. Les observations de code ont notamment couvert `README.md`, la *Integration Spine*, UI-G01, G02/B, UI01, AC03, AC04, les bornes CP03 et le design system actuel `gnos.ux`/GPUI. Il s'agit d'un **contrat proposé**; aucun build natif, benchmark, merge, push ou test matériel nouveau n'a été exécuté pour sa rédaction. Une source et un test historiques restent des observations antérieures à requalifier uniquement lorsque leur contexte matériel, leur code ou leurs préconditions ont changé.

**Fin du contrat proposé.**