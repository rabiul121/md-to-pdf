use clap::Parser;
use std::path::PathBuf;
use pdf_creator_studio::{config,converter,profiles};

#[derive(Parser, Debug)]
#[command(name="pdf-creator-studio-cli", version, about="Convert documents to PDF with Pandoc and XeLaTeX")]
struct Args {
    /// One or more supported documents to convert.
    #[arg(value_name="FILE")]
    files: Vec<PathBuf>,
    /// Start the interactive conversion wizard.
    #[arg(long)]
    wizard: bool,
    /// Select the built-in or saved settings profile.
    #[arg(long)]
    profile: Option<String>,
    /// Override the PDF output directory.
    #[arg(long)]
    output_dir: Option<PathBuf>,
    /// Override the PDF output name for a single input.
    #[arg(long)]
    output_name: Option<String>,
    /// Treat the input as literal plain text rather than Markdown.
    #[arg(long)]
    plain: bool,
    /// Reconvert one input whenever its modification time changes.
    #[arg(long)]
    watch: bool,
    /// Seconds between file-change checks while watching (default: 2).
    #[arg(long)]
    watch_interval: Option<u64>,
}

fn main() {
    let args=Args::parse();
    if args.watch_interval.is_some() && !args.watch {
        eprintln!("--watch-interval requires --watch (use --wizard --watch for the interactive watch flow).");
        std::process::exit(2);
    }
    if args.watch_interval==Some(0) {
        eprintln!("Watch interval must be at least one second.");
        std::process::exit(2);
    }
    if args.wizard || args.files.is_empty() { interactive_wizard(args.watch,args.watch_interval.unwrap_or(2)); return; }
    if args.watch && args.files.len()!=1 { eprintln!("Watch mode requires exactly one input file."); std::process::exit(2); }
    let watch_interval=args.watch_interval.unwrap_or(2);
    let mut settings=args.profile.as_deref().and_then(|name|profiles::load_profiles().remove(name)).unwrap_or_default();
    if let Some(dir)=args.output_dir { settings.output_directory=dir.to_string_lossy().into_owned(); }
    if let Some(name)=args.output_name { settings.output_name=name; }
    if args.files.len()>1&&!settings.output_name.is_empty(){eprintln!("Batch mode uses each input's filename; ignoring the custom output name.");settings.output_name.clear();}
    let mut log=|line:String|println!("{line}");
    let mut failures=0;
    for file in &args.files {
        if let Err(error)=converter::convert_one(file,&settings,if args.plain{Some("plain")}else{None},None,&mut log) {
            failures+=1;
            eprintln!("Failed to convert '{}': {error:#}",file.display());
        }
    }
    if failures>0 && !args.watch { std::process::exit(1); }
    if args.watch {
        let file=&args.files[0];
        let mut last=std::fs::metadata(file).and_then(|m|m.modified()).ok();
        println!("Watching {} for changes. Press Ctrl+C to stop.",file.display());
        loop { std::thread::sleep(std::time::Duration::from_secs(watch_interval)); let modified=std::fs::metadata(file).and_then(|m|m.modified()).ok(); if modified.is_some()&&modified!=last { last=modified; println!("[WATCH] File changed; converting again."); if let Err(error)=converter::convert_one(file,&settings,if args.plain{Some("plain")}else{None},None,&mut log){eprintln!("Failed to convert '{}': {error:#}",file.display());} } }
    }
}

fn interactive_wizard(auto_mode:bool, default_watch_interval:u64) {
    use std::io::{self,Write};
    let mut settings=config::Settings::default();
    println!("PDF Creator Studio — Rust CLI");
    let input_dir=config::input_dir();
    let mut available=std::fs::read_dir(&input_dir).ok().into_iter().flatten()
        .filter_map(Result::ok).map(|entry|entry.path())
        .filter(|path|path.is_file()&&path.extension().and_then(|s|s.to_str())
            .is_some_and(|ext|config::SUPPORTED_EXTENSIONS.contains(&ext.to_ascii_lowercase().as_str())))
        .collect::<Vec<_>>();
    available.sort();
    let mut files=Vec::new();
    if !available.is_empty() {
        println!("\nDocuments in {}:",input_dir.display());
        for (index,path) in available.iter().enumerate(){println!("  {}. {}",index+1,path.file_name().unwrap_or_default().to_string_lossy());}
        println!("  A. Convert all listed files");
        println!("  0. Enter custom path(s), separated by semicolons");
        loop {
            print!("Choose file [1-{}, A, 0] (default 1): ",available.len());
            let _=io::stdout().flush();
            let mut choice=String::new();
            if io::stdin().read_line(&mut choice).is_err()||choice.is_empty(){return;}
            let choice=choice.trim();
            if choice.is_empty(){files.push(available[0].clone());break;}
            if choice.eq_ignore_ascii_case("a"){files=available;break;}
            if choice=="0"{files=read_custom_paths();break;}
            if let Ok(index)=choice.parse::<usize>() {
                if let Some(path)=index.checked_sub(1).and_then(|i|available.get(i)){
                    files.push(path.clone());break;
                }
            }
            println!("Invalid selection. Choose a listed number, A, or 0.");
        }
    } else {
        println!("No supported documents found in {}.",input_dir.display());
        files=read_custom_paths();
    }
    if files.is_empty(){println!("No files selected.");return;}
    if auto_mode&&files.len()!=1{eprintln!("Watch mode requires exactly one input file.");return;}
    let ask=|prompt:&str,default:&str|->String { print!("{prompt} [{default}]: ");let _=io::stdout().flush();let mut value=String::new();let _=io::stdin().read_line(&mut value);if value.trim().is_empty(){default.into()}else{value.trim().to_owned()} };
    let yes=|prompt:&str,default:bool|->bool { let suffix=if default{"Y/n"}else{"y/N"}; let answer=ask(&format!("{prompt} {suffix}"),"").to_lowercase(); if answer.is_empty(){default}else{matches!(answer.as_str(),"y"|"yes")} };
    println!("Selected {} document(s).",files.len());
    let page=ask("Page size: 1 A4, 2 Letter, 3 A5, 4 Legal, 5 For Mobile, 6 For PC","1");
    settings.page_size_choice=match page.as_str(){"2"=>"Letter","3"=>"A5","4"=>"Legal","5"=>"For Mobile","6"=>"For PC",_=>"A4"}.into();
    settings.orientation=if ask("Orientation (Portrait/Landscape)","Portrait").to_lowercase().starts_with('l'){"Landscape"}else{"Portrait"}.into();
    let margin=ask("Margin preset: 1 Page default, 2 Narrow, 3 Standard, 4 Wide 1.25in, 5 Wide 1.5in, 6 Compact, 7 Custom","1");
    settings.margin_choice=match margin.as_str(){"2"=>"Narrow (0.5 in)","3"=>"Standard (1 in)","4"=>"Wide (1.25 in)","5"=>"Wide (1.5 in)","6"=>"Compact (7 mm)","7"=>"Custom",_=>"Page default"}.into();
    if settings.margin_choice=="Custom"{settings.custom_margin=ask("Custom margin dimension","25mm");}
    let font=ask("Font size: 1 Standard, 2 Medium, 3 Large, 4 Custom","2");
    settings.font_size_choice=match font.as_str(){"1"=>"Standard","3"=>"Large","4"=>"Custom",_=>"Medium"}.into();
    if settings.font_size_choice=="Custom"{settings.custom_font_size=ask("Custom font size in points","14").parse::<f32>().unwrap_or(14.0).clamp(6.0,36.0);}
    settings.english_font=ask("English font","DejaVu Sans");settings.heading_font=ask("Heading font",&settings.english_font);
    settings.bengali_font=ask("Bengali font","SolaimanLipi");settings.arabic_font=ask("Arabic font","Amiri");
    settings.code_font=ask("Code font","JetBrains Mono");
    settings.include_toc=yes("Include Table of Contents",true);settings.beautify_toc=yes("Beautify TOC",true);
    settings.toc_language=if ask("TOC language: 1 English, 2 Bangla","1")=="2"{"Bangla"}else{"English"}.into();
    settings.toc_alignment=match ask("TOC title alignment: 1 Left, 2 Center, 3 Right","2").as_str(){"1"=>"Left","3"=>"Right",_=>"Center"}.into();
    settings.toc_design=match ask("TOC design: 1 Classic, 2 Minimal, 3 Decorative","1").as_str(){"2"=>"Minimal","3"=>"Decorative",_=>"Classic"}.into();
    settings.page_numbers=yes("Show page numbers",false);
    if settings.page_numbers {
        settings.page_number_language=if ask("Page numeral language: 1 English, 2 Bangla","1")=="2"{"Bangla"}else{"English"}.into();
        settings.page_number_style=ask("Page-number style (arabic/roman)","arabic");
        settings.page_number_format=match ask("Page format: 1 Page 1 of 10, 2 1 / 10, 3 Page 1, 4 1","1").as_str(){"2"=>"1 / 10","3"=>"Page 1","4"=>"1",_=>"Page 1 of 10"}.into();
        settings.page_number_position=match ask("Number position: 1 Bottom left, 2 Middle, 3 Bottom right","2").as_str(){"1"=>"Bottom left","3"=>"Bottom right",_=>"Middle"}.into();
        settings.page_number_size=ask("Page-number font size","9pt");
    }
    settings.front_page_numbers=settings.include_toc&&yes("Number TOC/front-matter pages",false);
    if settings.front_page_numbers {
        settings.front_page_number_style=ask("Front-matter style (roman/arabic)","roman");
        settings.front_page_number_format=match ask("Front format: 1 Page 1 of 10, 2 1 / 10, 3 Page 1, 4 1","4").as_str(){"1"=>"Page 1 of 10","2"=>"1 / 10","3"=>"Page 1",_=>"1"}.into();
        settings.front_page_number_position=match ask("Front position: 1 Bottom left, 2 Middle, 3 Bottom right","2").as_str(){"1"=>"Bottom left","3"=>"Bottom right",_=>"Middle"}.into();
        settings.front_page_number_size=ask("Front-page number size","9pt");
        settings.front_page_number_language=if ask("Front page numeral language: 1 English, 2 Bangla","1")=="2"{"Bangla"}else{"English"}.into();
    }
    settings.indent_first_line=yes("Indent first paragraph line",false);
    if settings.indent_first_line{settings.indent_amount=ask("Indent amount","0.25in");}
    settings.center_headings=yes("Center headings",true);settings.bold_headings=yes("Bold headings",true);
    settings.page_border=yes("Decorative page border",false);settings.hyphenation=yes("Enable hyphenation",true);
    settings.copy_friendly_text=yes("Copy-friendly text for script fonts",false);
    settings.line_height=ask("Line spacing multiplier","1.1");
    settings.paragraph_spacing=match ask("Paragraph spacing: 1 None, 2 3pt, 3 6pt, 4 9pt, 5 Custom","3").as_str(){"1"=>"0pt".into(),"2"=>"3pt".into(),"4"=>"9pt".into(),"5"=>ask("Custom spacing","6pt"),_=>"6pt".into()};
    settings.output_name=if files.len()==1{ask("Custom output filename (blank uses input name)","")}else{String::new()};
    settings.output_directory=ask("Output directory",&settings.output_directory);
    let watch_interval=if auto_mode{ask("Watch interval in seconds",&default_watch_interval.to_string()).parse::<u64>().ok().filter(|seconds|*seconds>0).unwrap_or(default_watch_interval.max(1))}else{2};
    let mut log=|line:String|println!("{line}");
    if auto_mode {
        let input=files[0].clone();let mut last=std::fs::metadata(&input).and_then(|m|m.modified()).ok();
        println!("Watching {} every {watch_interval} second(s). Press Ctrl+C to stop.",input.display());
        if let Err(error)=converter::convert_one(&input,&settings,None,None,&mut log){eprintln!("Failed to convert '{}': {error:#}",input.display());}
        loop { std::thread::sleep(std::time::Duration::from_secs(watch_interval));let modified=std::fs::metadata(&input).and_then(|m|m.modified()).ok();if modified.is_some()&&modified!=last{last=modified;println!("[WATCH] File changed; converting again.");if let Err(error)=converter::convert_one(&input,&settings,None,None,&mut log){eprintln!("Failed to convert '{}': {error:#}",input.display());}} }
    }
    let mut succeeded=Vec::new();let mut failed=Vec::new();
    for file in &files { match converter::convert_one(file,&settings,None,None,&mut log) { Ok(path)=>succeeded.push(path),Err(error)=>failed.push((file.clone(),error.to_string())) } }
    println!("Finished: {} of {} file(s) converted.",succeeded.len(),files.len());
    for path in &succeeded { println!("PDF: {}",path.display()); }
    for (file,error) in &failed { println!("Failed: {} — {error}",file.display()); }
    if let Some(path)=succeeded.first() { if yes("Open the latest generated PDF",false){let _=open::that(path);} }
    if yes("Open the output folder",false){let _=open::that(&settings.output_directory);}
    if yes("Convert another set of documents",false){interactive_wizard(false,2);}
}

fn read_custom_paths()->Vec<PathBuf>{
    use std::io::{self,Write};
    loop {
        print!("Enter supported document path(s), separated by semicolons: ");
        let _=io::stdout().flush();
        let mut line=String::new();
        if io::stdin().read_line(&mut line).is_err()||line.is_empty(){return Vec::new();}
        let paths=line.split(';').map(|p|PathBuf::from(p.trim().trim_matches('"'))).collect::<Vec<_>>();
        if !paths.is_empty()&&paths.iter().all(|path|path.is_file()&&path.extension().and_then(|s|s.to_str())
            .is_some_and(|ext|config::SUPPORTED_EXTENSIONS.contains(&ext.to_ascii_lowercase().as_str()))) {
            return paths;
        }
        println!("One or more paths are missing or have an unsupported extension. Try again.");
    }
}
