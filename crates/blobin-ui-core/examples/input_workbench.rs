//! UI-G04/A headless consumer: pointer and keyboard event receipts.
use blobin_ui_core::input::{EventKind, InputEvent, InputRouter, Key, Point, Units};
use blobin_ui_core::layout::{compute, Axis, LayoutStyles, Length, Size, Style, Viewport};
use blobin_ui_core::{NodeProperties, Role, SurfaceId, UiTree};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut tree = UiTree::new();
    let surface = SurfaceId(5);
    let mut button = None;
    tree.transact(|tx| {
        tx.open_surface(surface)?;
        let root = tx.append_root(surface, NodeProperties::new(Role::Container, "workbench"))?;
        button = Some(tx.append_child(root, NodeProperties::new(Role::Button, "Open"))?);
        Ok(())
    })?;
    let button = button.ok_or("missing button")?;
    let mut styles = LayoutStyles::new();
    let mut root = Style::fill();
    root.axis = Axis::Row;
    let tree_snapshot = tree.snapshot();
    let root_id = tree_snapshot.roots(surface).ok_or("missing surface")?[0];
    styles.set(&tree_snapshot, root_id, root)?;
    let button_style = Style {
        width: Length::Px(120.0),
        height: Length::Px(60.0),
        ..Style::default()
    };
    styles.set(&tree_snapshot, button, button_style)?;
    let viewport = Viewport::new(Size::new(300.0, 100.0), 1.5, 1);
    let geometry = compute(&tree_snapshot, &styles, surface, viewport)?;
    let mut router = InputRouter::new();
    let mut dispatch = |seq, kind| {
        router.dispatch(
            &tree_snapshot,
            &styles,
            &geometry,
            viewport,
            InputEvent::for_layout(&geometry, seq, seq * 1000, kind),
        )
    };
    let down = dispatch(
        1,
        EventKind::PointerDown {
            pointer: 7,
            button: 1,
            position: Point::new(30.0, 30.0),
            units: Units::Logical,
        },
    )?;
    let up = dispatch(
        2,
        EventKind::PointerUp {
            pointer: 7,
            button: 1,
            position: Point::new(30.0, 30.0),
            units: Units::Logical,
        },
    )?;
    let enter = dispatch(
        3,
        EventKind::KeyDown {
            key: Key::Enter,
            shift: false,
            repeat: false,
        },
    )?;
    assert_eq!(down.pointer_capture, Some(button));
    assert_eq!(up.activated, Some(button));
    assert_eq!(enter.activated, Some(button));
    println!(
        "BLOBIN_UI_G04_HEADLESS_OK surface={} pointer_click={} keyboard_activate={}",
        surface.0,
        up.activated.is_some(),
        enter.activated.is_some()
    );
    Ok(())
}
