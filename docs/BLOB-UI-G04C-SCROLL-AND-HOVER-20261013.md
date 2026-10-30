# BLOB-UI-G04/C — Scroll et survol dans le routeur d'entrée (2026-10-13)

**État : SCOPED PASS (headless).** Extension de `blobin-ui-core::input` demandée par le premier consommateur externe, PARITY-02 (interactions du Bar Gnosix). Aucune preuve compositor ni E2E native n'est revendiquée.

## Contrat ajouté

| Élément | Sémantique |
|---|---|
| `EventKind::Scroll { pointer, position, units, delta: ScrollDelta, source: ScrollSource }` | Routé comme un déplacement : cible capturée d'abord, sinon hit-test. **Ne modifie jamais le focus et n'active rien.** `delta` en pixels logiques, convention de signe Wayland `wl_pointer.axis` (`y > 0` = vers le bas du contenu). `ScrollSource` : `Wheel`, `Finger`, `Continuous`. |
| `EventKind::PointerLeave { pointer }` | Fin du survol pour ce pointeur. Les captures restent intactes (`PointerCancel` reste l'unique annulation). |
| `InputRouter::hover(surface, pointer)` | Nœud interactif **géométriquement** sous le pointeur, indépendant de la capture. |
| `InputReceipt::hover: Option<HoverTransition { pointer, from, to }>` | Émis uniquement quand le nœud survolé change ; `None` sinon. |
| `InputError::InvalidScroll` | Delta non fini ou de valeur absolue > 1e6 ; rejet **avant** toute mutation, le serial n'est pas consommé. |

Le survol est remis à zéro avec les autres états lors d'un changement d'epoch de surface et filtré comme les captures quand un nœud disparaît ou cesse d'être interactif. `WindowBlur` (perte du clavier) ne touche pas au survol : une surface layer-shell sans focus clavier garde son état pointeur.

## Qualification

- 4 nouveaux tests dans `crates/blobin-ui-core/tests/input_routing.rs` : transitions de survol et sortie ; survol géométrique pendant une capture ; scroll sans focus ni activation et respect de la capture ; rejet non mutant des deltas invalides.
- `cargo test -p blobin-ui-core` : 8 suites PASS. `cargo test --workspace --lib` : 31 + 51 + 33 PASS. `cargo clippy -p blobin-ui-core --all-targets -- -D warnings` : PASS.
- Journaux : `evidence/runs/blob-ui-input-scroll-hover-20261013/`.

## Limites

Headless uniquement. Le scroll inertiel/cinétique, les axes discrets `value120` et la corrélation avec de vrais événements compositor restent hors périmètre ; G04/B (entrée compositor réelle) reste **HOLD**.
