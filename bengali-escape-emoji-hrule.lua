-- Combined Lua filter: wrap Bengali + escape LaTeX + fix HorizontalRule + emoji font

-- Utility: Identify Bengali characters (including danda U+0964, U+0965)
local function is_bengali_char(char)
  local code = utf8.codepoint(char)
  return code == 0x0964 or code == 0x0965 or (code >= 0x0980 and code <= 0x09FF)
end

-- Utility: Identify Emoji characters (range based, expanded for symbols)
local function is_emoji_char(char)
  local code = utf8.codepoint(char)
  -- Common emoji ranges
  if (code >= 0x1F300 and code <= 0x1FAFF) or (code >= 0x1F600 and code <= 0x1F64F) then
    return true
  end
  -- Dingbats, Misc Symbols, etc.
  if (code >= 0x2600 and code <= 0x26FF) or (code >= 0x2700 and code <= 0x27BF) then
    -- Exception: U+279C (➜) should be treated as a symbol, not emoji
    if code == 0x279C then return false end
    return true
  end
  -- Variation Selector-16 (U+FE0F) should be treated as part of emoji
  if code == 0xFE0F then
    return true
  end
  return false
end

-- Utility: Identify arrow and math symbol characters (for fallback font)
local function is_symbol_char(char)
  local code = utf8.codepoint(char)
  -- Arrows and math symbols
  if (code >= 0x2190 and code <= 0x21FF) then
    return true
  end
  -- Miscellaneous Symbols and Arrows (for ⬅, ⬆, ⬇, ⬛, ⬜, etc.)
  if (code >= 0x2B00 and code <= 0x2BFF) then
    return true
  end
  -- Dingbats, Misc Symbols, etc. (for ➜ U+279C)
  if code == 0x279C then
    return true
  end
  return false
end

-- LaTeX special character replacements
local replacements = {
  ["\\"] = "\\textbackslash{}",
  ["{"]  = "\\{",
  ["}"]  = "\\}",
  ["$"]  = "\\$",
  ["&"]  = "\\&",
  ["#"]  = "\\#",
  ["%"]  = "\\%",
  ["_"]  = "\\_",
  ["^"]  = "\\textasciicircum{}",
  ["~"]  = "\\textasciitilde{}",
}

-- Escape LaTeX special characters
local function escape_latex(str)
  return (str:gsub("[\\${}&%%#_^~]", function(c)
    return replacements[c] or c
  end))
end

-- Process text: wrap Bengali, emoji and escape all LaTeX specials
local function process_text(text)
  local output = ""
  local in_bengali = false
  local in_emoji = false
  local in_symbol = false

  for _, c in utf8.codes(text) do
    local char = utf8.char(c)
    if is_bengali_char(char) then
      if in_emoji then output = output .. "}" in_emoji = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      if not in_bengali then output = output .. "\\bn{" in_bengali = true end
      output = output .. escape_latex(char)
    elseif is_emoji_char(char) then
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      if not in_emoji then output = output .. "\\emoji{" in_emoji = true end
      output = output .. escape_latex(char)
    elseif is_symbol_char(char) then
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_emoji then output = output .. "}" in_emoji = false end
      if not in_symbol then output = output .. "\\symb{" in_symbol = true end
      output = output .. escape_latex(char)
    else
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_emoji then output = output .. "}" in_emoji = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      output = output .. escape_latex(char)
    end
  end

  if in_bengali then output = output .. "}" end
  if in_emoji then output = output .. "}" end
  if in_symbol then output = output .. "}" end

  return output
end

-- Inline string processor
function Str(el)
  local new_text = process_text(el.text)
  return pandoc.RawInline("latex", new_text)
end

-- Escape + wrap Bengali and emoji text inside table cells
function Table(tbl)
  for _, row in ipairs(tbl.bodies[1].body) do
    for _, cell in ipairs(row.cells) do
      for _, block in ipairs(cell) do
        if block.t == "Para" then
          for i, inline in ipairs(block.c) do
            if inline.t == "Str" then
              local new_text = process_text(inline.text)
              block.c[i] = pandoc.RawInline("latex", new_text)
            end
          end
        end
      end
    end
  end
  return tbl
end

-- Replace HorizontalRule (`---`) with LaTeX full-width line
function HorizontalRule()
  return pandoc.RawBlock('latex', '\\par\\noindent\\rule{\\linewidth}{0.8pt}\\par\\vspace{1.5ex}')
end
