//! BLOB-AC-01 consumer: UI-G02 tree + UI-G03 geometry + UI-G04 events.
//! Previews are ephemeral; only Commit writes to the document, once.
use blobin_ui_core::gestures::{GestureAction, GestureCoordinator};
use blobin_ui_core::input::{EventKind, InputEvent, InputRouter, Point, Units};
use blobin_ui_core::layout::{compute, LayoutStyles, Length, Size, Style, Viewport};
use blobin_ui_core::{NodeProperties, Role, SurfaceId, UiTree};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut tree = UiTree::new();
    let surface = SurfaceId(101);
    let mut target = None;
    tree.transact(|tx| {
        tx.open_surface(surface)?;
        let root = tx.append_root(surface, NodeProperties::new(Role::Container, "scene"))?;
        target = Some(tx.append_child(
            root,
            NodeProperties::new(Role::Custom("draggable".into()), "handle"),
        )?);
        Ok(())
    })?;
    let target = target.ok_or("no drag target")?;
    let baseline = tree.snapshot();
    let mut styles = LayoutStyles::new();
    let root = baseline.roots(surface).ok_or("no surface roots")?[0];
    styles.set(&baseline, root, Style::fill())?;
    styles.set(
        &baseline,
        target,
        Style {
            width: Length::Px(150.0),
            height: Length::Px(75.0),
            ..Style::default()
        },
    )?;
    let viewport = Viewport::new(Size::new(320.0, 180.0), 1.5, 1);
    let layout = compute(&baseline, &styles, surface, viewport)?;
    let mut router = InputRouter::new();
    let mut gestures = GestureCoordinator::new();
    let mut previews = 0u32;
    let mut commits = 0u32;
    let mut undo = Vec::new();
    let inputs = [
        EventKind::PointerDown {
            pointer: 7,
            button: 1,
            position: Point::new(20.0, 20.0),
            units: Units::Logical,
        },
        EventKind::PointerMove {
            pointer: 7,
            position: Point::new(32.0, 20.0),
            units: Units::Logical,
        },
        EventKind::PointerMove {
            pointer: 7,
            position: Point::new(48.0, 20.0),
            units: Units::Logical,
        },
        EventKind::PointerUp {
            pointer: 7,
            button: 1,
            position: Point::new(55.0, 20.0),
            units: Units::Logical,
        },
    ];
    for (i, kind) in inputs.into_iter().enumerate() {
        let event = InputEvent::for_layout(&layout, i as u64 + 1, i as u64 * 1000 + 1, kind);
        let receipt =
            router.dispatch(&tree.snapshot(), &styles, &layout, viewport, event.clone())?;
        // The consumer must use the SAME input event for routing and gesture interpretation.
        for action in gestures.observe(
            &tree.snapshot(),
            &styles,
            &layout,
            viewport,
            &event,
            &receipt,
        )? {
            match action {
                GestureAction::Begin { .. } => {}
                GestureAction::Preview { .. } => {
                    previews += 1;
                    assert_eq!(
                        tree.snapshot().revision(),
                        baseline.revision(),
                        "preview must not mutate canonical state"
                    );
                }
                GestureAction::Commit {
                    target: id, delta, ..
                } => {
                    let old = tree
                        .snapshot()
                        .get(id)
                        .ok_or("missing node")?
                        .properties()
                        .clone();
                    undo.push((id, old.clone()));
                    let mut new = old;
                    new.label = format!("translated x={} y={}", delta.x, delta.y);
                    let commit = tree.transact(|tx| tx.set_properties(id, new))?;
                    assert!(commit.changed());
                    commits += 1;
                }
                GestureAction::Cancel { .. } => {}
            }
        }
    }
    assert_eq!((previews, commits), (2, 1));
    assert_eq!(tree.snapshot().revision(), baseline.revision() + 1);
    assert_eq!(
        tree.snapshot()
            .get(target)
            .ok_or("missing target")?
            .properties()
            .label,
        "translated x=35 y=0"
    );
    for (id, old) in undo {
        tree.transact(|tx| tx.set_properties(id, old))?;
    }
    assert_eq!(
        tree.snapshot()
            .get(target)
            .ok_or("missing target")?
            .properties()
            .label,
        "handle"
    );
    println!("BLOB_AC01_HEADLESS_OK previews={previews} commits={commits} undo=1");
    Ok(())
}
