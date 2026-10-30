//! Headless consumer example. No compositor, renderer, F4 broker or UI toolkit.
use blobin_ui_core::{NodeProperties, Role, SurfaceId, UiTree};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let surface = SurfaceId(42);
    let mut ui = UiTree::new();
    let commit = ui.transact(|transaction| {
        transaction.open_surface(surface)?;
        let root =
            transaction.append_root(surface, NodeProperties::new(Role::Container, "Workbench"))?;
        transaction.append_child(root, NodeProperties::new(Role::Button, "Open inspector"))?;
        transaction.append_child(root, NodeProperties::new(Role::Text, "Ready"))?;
        Ok(())
    })?;

    let snapshot = ui.snapshot();
    let root = snapshot.roots(surface).ok_or("surface not created")?[0];
    let children = snapshot.get(root).ok_or("root missing")?.children();

    assert_eq!(commit.revision, 1);
    assert_eq!(snapshot.node_count(), 3);
    assert_eq!(children.len(), 2);
    println!(
        "BLOBIN_UI_CORE_HEADLESS_OK surface={} revision={} nodes={}",
        surface.0,
        snapshot.revision(),
        snapshot.node_count()
    );
    Ok(())
}
