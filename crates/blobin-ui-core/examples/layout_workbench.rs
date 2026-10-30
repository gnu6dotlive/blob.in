//! UI-G03 geometry consumer: headless rail/workspace, DPI + clipped bounds.
use blobin_ui_core::layout::{compute, Axis, Insets, LayoutStyles, Length, Size, Style, Viewport};
use blobin_ui_core::{NodeProperties, Role, SurfaceId, UiTree};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut tree = UiTree::new();
    let surface = SurfaceId(7);
    let mut ids = Vec::new();
    tree.transact(|tx| {
        tx.open_surface(surface)?;
        let root = tx.append_root(surface, NodeProperties::new(Role::Container, "Workbench"))?;
        ids.push(root);
        ids.push(tx.append_child(
            root,
            NodeProperties::new(Role::Container, "Navigation rail"),
        )?);
        ids.push(tx.append_child(root, NodeProperties::new(Role::Container, "Inspector"))?);
        Ok(())
    })?;
    let mut styles = LayoutStyles::new();
    let mut root = Style::fill();
    root.axis = Axis::Row;
    root.padding = Insets::uniform(12.0);
    root.gap = 8.0;
    root.clip_children = true;
    styles.set(&tree.snapshot(), ids[0], root)?;
    let mut rail = Style {
        width: Length::Px(180.0),
        ..Style::default()
    };
    rail.min.width = 120.0;
    styles.set(&tree.snapshot(), ids[1], rail)?;
    let mut inspector = Style {
        width: Length::Px(280.0),
        ..Style::default()
    };
    inspector.min.width = 160.0;
    inspector.flex_grow = 1.0;
    styles.set(&tree.snapshot(), ids[2], inspector)?;
    let viewport = Viewport::new(Size::new(800.0, 450.0), 1.5, 1);
    let geometry = compute(&tree.snapshot(), &styles, surface, viewport)?;
    let rail = geometry.get(ids[1]).ok_or("rail missing")?;
    let inspector = geometry.get(ids[2]).ok_or("inspector missing")?;
    assert_eq!(geometry.paint_order, ids);
    println!(
        "BLOBIN_UI_G03_HEADLESS_OK rail={:?} inspector={:?} dpr={}",
        rail.rect, inspector.rect, viewport.scale_factor
    );
    Ok(())
}
