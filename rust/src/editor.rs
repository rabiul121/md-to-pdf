//! Markdown buffer operations and bounded undo/redo history.

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Snapshot {
    pub text: String,
    pub selection: (usize, usize),
}

#[derive(Default)]
pub struct History {
    undo: Vec<Snapshot>,
    redo: Vec<Snapshot>,
    limit: usize,
}

/// Continue Markdown list, task-list, and quote prefixes when Enter is pressed.
/// Returns `None` when the current line is not a supported Markdown item.
pub fn continue_markdown_line(text: &str, selection: (usize, usize)) -> Option<(String, (usize, usize))> {
    if selection.0 != selection.1 || selection.0 > text.len() || !text.is_char_boundary(selection.0) {
        return None;
    }
    let cursor = selection.0;
    let line_start = text[..cursor].rfind('\n').map_or(0, |index| index + 1);
    let line_end = text[cursor..].find('\n').map_or(text.len(), |index| cursor + index);
    if cursor != line_end { return None; }

    let line = &text[line_start..line_end];
    let indent_len = line.bytes().take_while(|byte| *byte == b' ' || *byte == b'\t').count();
    let indent = &line[..indent_len];
    let content = &line[indent_len..];
    let (marker_len, continuation) = if content.starts_with("- [ ] ") || content.starts_with("- [x] ") || content.starts_with("- [X] ") {
        (6, format!("{indent}- [ ] "))
    } else if content.starts_with("- ") || content.starts_with("* ") || content.starts_with("+ ") {
        (2, format!("{indent}{} ", &content[..1]))
    } else {
        let digits = content.bytes().take_while(|byte| byte.is_ascii_digit()).count();
        let delimiter = content.get(digits..digits + 2).filter(|value| *value == ". " || *value == ") ");
        if digits > 0 {
            if let Some(delimiter) = delimiter {
                let number = content[..digits].parse::<u64>().ok()?;
                (digits + 2, format!("{indent}{}{delimiter}", number.saturating_add(1)))
            } else {
                let (marker_len, continuation) = quote_continuation(indent, content)?;
                (marker_len, continuation)
            }
        } else {
            let (marker_len, continuation) = quote_continuation(indent, content)?;
            (marker_len, continuation)
        }
    };

    let item_text = &content[marker_len..];
    let mut updated = text.to_owned();
    let next_cursor;
    if item_text.trim().is_empty() {
        updated.replace_range(line_start..cursor, "");
        next_cursor = line_start;
    } else {
        updated.insert_str(cursor, &format!("\n{continuation}"));
        next_cursor = cursor + 1 + continuation.len();
    }
    Some((updated, (next_cursor, next_cursor)))
}

fn quote_continuation(indent: &str, content: &str) -> Option<(usize, String)> {
    let mut marker_len = 0;
    let mut rest = content;
    while let Some(after_marker) = rest.strip_prefix('>') {
        marker_len += 1;
        rest = after_marker;
        if let Some(after_space) = rest.strip_prefix(' ') {
            marker_len += 1;
            rest = after_space;
        } else {
            break;
        }
    }
    (marker_len > 0).then(|| (marker_len, format!("{indent}{}", &content[..marker_len])))
}

impl History {
    pub fn new(limit: usize) -> Self { Self { undo: Vec::new(), redo: Vec::new(), limit } }
    pub fn can_undo(&self) -> bool { !self.undo.is_empty() }
    pub fn can_redo(&self) -> bool { !self.redo.is_empty() }
    pub fn record(&mut self, before: Snapshot, after: &Snapshot) {
        if before.text == after.text { return; }
        self.undo.push(before);
        if self.undo.len() > self.limit { self.undo.remove(0); }
        self.redo.clear();
    }
    pub fn undo(&mut self, current: Snapshot) -> Option<Snapshot> {
        let previous = self.undo.pop()?;
        self.redo.push(current);
        Some(previous)
    }
    pub fn redo(&mut self, current: Snapshot) -> Option<Snapshot> {
        let next = self.redo.pop()?;
        self.undo.push(current);
        Some(next)
    }
    pub fn clear(&mut self) { self.undo.clear(); self.redo.clear(); }
}

fn boundaries(text: &str, range: (usize, usize)) -> (usize, usize) {
    let mut start = range.0.min(text.len());
    let mut end = range.1.min(text.len());
    while !text.is_char_boundary(start) { start = start.saturating_sub(1); }
    while !text.is_char_boundary(end) { end += 1; }
    if start > end { std::mem::swap(&mut start, &mut end); }
    (start, end)
}

pub fn wrap_selection(text: &str, range: (usize, usize), prefix: &str, suffix: &str, placeholder: &str) -> (String, (usize, usize)) {
    let (start, end) = boundaries(text, range);
    let selected = &text[start..end];
    let (replacement, selection) = if selected.starts_with(prefix) && selected.ends_with(suffix) && selected.len() >= prefix.len() + suffix.len() {
        let content = &selected[prefix.len()..selected.len() - suffix.len()];
        (content.to_owned(), (start, start + content.len()))
    } else if start >= prefix.len() && text[..start].ends_with(prefix) && text[end..].starts_with(suffix) {
        let before = start - prefix.len();
        let after = end + suffix.len();
        let mut result = String::with_capacity(text.len() - prefix.len() - suffix.len());
        result.push_str(&text[..before]); result.push_str(selected); result.push_str(&text[after..]);
        return (result, (before, before + selected.len()));
    } else if start != end {
        (format!("{prefix}{selected}{suffix}"), (start + prefix.len(), end + prefix.len()))
    } else {
        (format!("{prefix}{placeholder}{suffix}"), (start + prefix.len(), start + prefix.len() + placeholder.len()))
    };
    let mut result = String::with_capacity(text.len() + replacement.len());
    result.push_str(&text[..start]); result.push_str(&replacement); result.push_str(&text[end..]);
    (result, selection)
}

pub fn transform_lines(text: &str, range: (usize, usize), marker: &str) -> (String, (usize, usize)) {
    let (start, end) = boundaries(text, range);
    let line_start = text[..start].rfind('\n').map_or(0, |i| i + 1);
    let line_end = text[end..].find('\n').map_or(text.len(), |i| end + i);
    let block = &text[line_start..line_end];
    let lines: Vec<&str> = block.split('\n').collect();
    let nonempty=lines.iter().filter(|line|!line.trim().is_empty()).collect::<Vec<_>>();
    let remove = !nonempty.is_empty()&&nonempty.iter().all(|line|has_marker(line.trim_start(),marker));
    let transformed = lines.iter().map(|line| {
        if remove {
            let indent = line.len() - line.trim_start().len();
            let rest = &line[indent..];
            let stripped = strip_active_marker(rest,marker);
            let stripped = stripped.strip_prefix(' ').unwrap_or(stripped);
            format!("{}{}", &line[..indent], stripped)
        } else if line.trim().is_empty() { (*line).to_owned() }
        else {
            let indent=line.len()-line.trim_start().len();
            let mut rest=&line[indent..];
            if marker.starts_with('#') { rest=strip_heading(rest); }
            else if marker=="-"||marker.starts_with("- [ ]") { rest=strip_list_marker(rest); }
            else if marker==">" { rest=rest.strip_prefix("> ").or_else(||rest.strip_prefix(">" )).unwrap_or(rest).trim_start(); }
            let separator=if marker.ends_with(' '){""}else{" "};
            format!("{}{marker}{separator}{rest}",&line[..indent])
        }
    }).collect::<Vec<_>>().join("\n");
    let mut result = String::with_capacity(text.len() + transformed.len());
    result.push_str(&text[..line_start]); result.push_str(&transformed); result.push_str(&text[line_end..]);
    let delta = transformed.len() as isize - block.len() as isize;
    let new_end = (end as isize + delta).max(line_start as isize) as usize;
    (result, (line_start, new_end.min(text.len().saturating_add(delta.max(0) as usize))))
}

pub fn heading(text: &str, range: (usize, usize), level: usize) -> (String, (usize, usize)) {
    let marker = format!("{} ", "#".repeat(level.clamp(1, 6)));
    transform_lines(text, range, &marker)
}

pub fn ordered_list(text: &str, range: (usize, usize)) -> (String, (usize, usize)) {
    let (start,end)=boundaries(text,range);
    let line_start=text[..start].rfind('\n').map_or(0,|i|i+1);
    let line_end=text[end..].find('\n').map_or(text.len(),|i|end+i);
    let block=&text[line_start..line_end];
    let lines=block.split('\n').collect::<Vec<_>>();
    let nonempty=lines.iter().filter(|line|!line.trim().is_empty()).collect::<Vec<_>>();
    let remove=!nonempty.is_empty()&&nonempty.iter().all(|line| numbered_marker(line).is_some());
    let mut number=0usize;
    let rewritten=lines.iter().map(|line| {
        if line.trim().is_empty(){return (*line).to_owned();}
        if remove {
            let indent=line.len()-line.trim_start().len();
            let rest=&line[indent..];
            let prefix=numbered_marker(rest).unwrap_or(0).to_string().len()+2;
            format!("{}{}",&line[..indent],&rest[prefix.min(rest.len())..])
        } else {
            number+=1; let indent=line.len()-line.trim_start().len();
            format!("{}{}. {}",&line[..indent],number,&line[indent..])
        }
    }).collect::<Vec<_>>().join("\n");
    let delta=rewritten.len() as isize-block.len() as isize;
    let mut out=String::with_capacity(text.len().saturating_add(delta.max(0) as usize));
    out.push_str(&text[..line_start]);out.push_str(&rewritten);out.push_str(&text[line_end..]);
    (out,(line_start,line_start+rewritten.len()))
}

fn numbered_marker(line:&str)->Option<usize>{
    let (number,rest)=line.split_once(". ")?;
    if number.is_empty()||!number.chars().all(|c|c.is_ascii_digit()){return None;}
    rest.chars().next()?;
    number.parse().ok()
}

fn has_marker(line:&str,marker:&str)->bool {
    if marker=="- [ ]" { line.starts_with("- [ ] ")||line.starts_with("- [x] ")||line.starts_with("- [X] ") }
    else if marker=="1." { numbered_marker(line).is_some() }
    else { line.starts_with(marker) }
}

fn strip_active_marker<'a>(line:&'a str,marker:&str)->&'a str {
    if marker=="- [ ]" { ["- [ ] ","- [x] ","- [X] "].iter().find_map(|prefix|line.strip_prefix(prefix)).unwrap_or(line) }
    else if marker=="1." { if let Some(number)=numbered_marker(line) { &line[(number.to_string().len()+2).min(line.len())..] } else { line.strip_prefix(marker).unwrap_or(line).strip_prefix(' ').unwrap_or(line) } }
    else { line.strip_prefix(marker).unwrap_or(line).strip_prefix(' ').unwrap_or(line) }
}

fn strip_heading(line:&str)->&str {
    let hashes=line.chars().take_while(|c|*c=='#').count();
    if (1..=6).contains(&hashes) { line[hashes..].strip_prefix(' ').unwrap_or(&line[hashes..]) } else { line }
}

fn strip_list_marker(line:&str)->&str {
    if let Some(numbered)=numbered_marker(line) {
        let length=numbered.to_string().len()+2;
        return &line[length.min(line.len())..];
    }
    for prefix in ["- ","* ","+ "] { if let Some(rest)=line.strip_prefix(prefix){return rest;} }
    line
}

pub fn fenced_code(text: &str, range: (usize, usize)) -> (String, (usize, usize)) {
    wrap_selection(text, range, "\n```\n", "\n```\n", "code block")
}

pub fn insert_link(text: &str, range: (usize, usize)) -> (String, (usize, usize)) {
    let (start,end)=boundaries(text,range);
    let url="https://example.com";
    let selected=&text[start..end];
    if start==end {
        let (result,selection)=wrap_selection(text,range,"[",&format!("]({url})"),"link text");
        return (result,selection);
    }
    let replacement=format!("[{selected}]({url})");
    let url_start=start+selected.len()+3;
    let mut result=String::with_capacity(text.len()+replacement.len());
    result.push_str(&text[..start]);result.push_str(&replacement);result.push_str(&text[end..]);
    (result,(url_start,url_start+url.len()))
}

