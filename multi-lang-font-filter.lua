-- Combined Lua filter: Bengali, Arabic, Emoji, Symbol, LaTeX escape, HorizontalRule
-- Supports: Bengali, Arabic, Emoji, Symbol, Table cell wrapping, HorizontalRule

-- Utility: Identify Bengali characters (including danda U+0964, U+0965)
local function is_bengali_char(char)
  local code = utf8.codepoint(char)
  return code == 0x0964 or code == 0x0965 or (code >= 0x0980 and code <= 0x09FF)
end

-- Utility: Identify Arabic characters (U+0600 to U+06FF, U+0750 to U+077F, U+08A0 to U+08FF, U+FB50 to U+FDFF, U+FE70 to U+FEFF)
local function is_arabic_char(char)
  local code = utf8.codepoint(char)
  return (code >= 0x0600 and code <= 0x06FF)
    or (code >= 0x0750 and code <= 0x077F)
    or (code >= 0x08A0 and code <= 0x08FF)
    or (code >= 0xFB50 and code <= 0xFDFF)
    or (code >= 0xFE70 and code <= 0xFEFF)
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
    if code == 0x279C then return false end
    return true
  end
  if code == 0xFE0F then
    return true
  end
  return false
end

-- Utility: Identify arrow and math symbol characters (for fallback font)
local function is_symbol_char(char)
  local code = utf8.codepoint(char)
  if (code >= 0x2190 and code <= 0x21FF) then
    return true
  end
  if (code >= 0x2B00 and code <= 0x2BFF) then
    return true
  end
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

local function escape_latex(str)
  return (str:gsub("[\\${}&%%#_^~]", function(c)
    return replacements[c] or c
  end))
end

-- Process text: wrap Bengali, Arabic, emoji, symbol and escape all LaTeX specials
local function process_text(text)
  local output = ""
  local in_bengali = false
  local in_arabic = false
  local in_emoji = false
  local in_symbol = false

  for _, c in utf8.codes(text) do
    local char = utf8.char(c)
    if is_bengali_char(char) then
      if in_arabic then output = output .. "}" in_arabic = false end
      if in_emoji then output = output .. "}" in_emoji = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      if not in_bengali then output = output .. "\\bn{" in_bengali = true end
      output = output .. escape_latex(char)
    elseif is_arabic_char(char) then
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_emoji then output = output .. "}" in_emoji = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      if not in_arabic then output = output .. "\\ar{" in_arabic = true end
      output = output .. escape_latex(char)
    elseif is_emoji_char(char) then
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_arabic then output = output .. "}" in_arabic = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      if not in_emoji then output = output .. "\\emoji{" in_emoji = true end
      output = output .. escape_latex(char)
    elseif is_symbol_char(char) then
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_arabic then output = output .. "}" in_arabic = false end
      if in_emoji then output = output .. "}" in_emoji = false end
      if not in_symbol then output = output .. "\\symb{" in_symbol = true end
      output = output .. escape_latex(char)
    else
      if in_bengali then output = output .. "}" in_bengali = false end
      if in_arabic then output = output .. "}" in_arabic = false end
      if in_emoji then output = output .. "}" in_emoji = false end
      if in_symbol then output = output .. "}" in_symbol = false end
      output = output .. escape_latex(char)
    end
  end

  if in_bengali then output = output .. "}" end
  if in_arabic then output = output .. "}" end
  if in_emoji then output = output .. "}" end
  if in_symbol then output = output .. "}" end

  return output
end

function Str(el)
  local new_text = process_text(el.text)
  return pandoc.RawInline("latex", new_text)
end

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

function HorizontalRule()
  return pandoc.RawBlock('latex', "\\par\\noindent\\rule{\\linewidth}{0.8pt}\\par\\vspace{1.5ex}")
end
