fn main() -> eframe::Result {
    let image=image::load_from_memory(include_bytes!("../../assets/pdf_icon.png"))
        .expect("the bundled PDF Creator Studio icon must be a valid PNG").into_rgba8();
    let (width,height)=image.dimensions();
    let icon=eframe::egui::IconData { rgba:image.into_raw(), width, height };
    let options = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default().with_inner_size([1180.0, 800.0]).with_min_inner_size([820.0, 600.0]).with_icon(std::sync::Arc::new(icon)),
        ..Default::default()
    };
    eframe::run_native(
        "PDF Creator Studio",
        options,
        Box::new(|cc| Ok(Box::new(pdf_creator_studio::app::StudioApp::new(cc)))),
    )
}

