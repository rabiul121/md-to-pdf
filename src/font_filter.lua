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

-- Utility: Identify Emoji characters (range based, expanded for symbols and Windows-visible icons)
local function is_emoji_char(char)
  local code = utf8.codepoint(char)
  -- Regional flags and emoji sequences used in Windows/modern apps.
  if (code >= 0x1F1E6 and code <= 0x1F1FF) then
    return true
  end
  if (code >= 0x1F000 and code <= 0x1FAFF) then
    return true
  end
  if (code >= 0x1F300 and code <= 0x1FAFF) or (code >= 0x1F600 and code <= 0x1F64F) then
    return true
  end
  if (code >= 0x2300 and code <= 0x23FF) then
    return true
  end
  if (code >= 0x2500 and code <= 0x25FF) or (code >= 0x2600 and code <= 0x26FF) or (code >= 0x2700 and code <= 0x27BF) then
    return true
  end
  if (code >= 0x2B00 and code <= 0x2BFF) then
    return true
  end
  if code == 0x200D or code == 0x20E3 or code == 0xFE0E or code == 0xFE0F then
    return true
  end
  return false
end

-- Utility: Identify arrow, math, and miscellaneous symbol characters (for fallback font)
local function is_symbol_char(char)
  local code = utf8.codepoint(char)
  if (code >= 0x20A0 and code <= 0x20CF) then
    return true
  end
  if (code >= 0x2190 and code <= 0x21FF) or (code >= 0x2200 and code <= 0x22FF) then
    return true
  end
  if (code >= 0x2500 and code <= 0x27BF) then
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

local function is_currency_char(char)
  local code = utf8.codepoint(char)
  return code >= 0x20A0 and code <= 0x20CF
end

local function is_symbol_only_char(char)
  local code = utf8.codepoint(char)
  return code == 0x265E
    or code == 0x2690 or code == 0x2691
    or code == 0x2713 or code == 0x2715
    or code == 0x279C
    or code == 0x1F59F or code == 0x1F5BA
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
  local chars = {}
  for _, code in utf8.codes(text) do
    table.insert(chars, utf8.char(code))
  end

  local i = 1
  while i <= #chars do
    local char = chars[i]
    local code = utf8.codepoint(char)

    if is_bengali_char(char) then
      local segment = ""
      while i <= #chars and is_bengali_char(chars[i]) do
        segment = segment .. escape_latex(chars[i])
        i = i + 1
      end
      output = output .. "\\bn{" .. segment .. "}"
    elseif is_arabic_char(char) then
      local segment = ""
      while i <= #chars and is_arabic_char(chars[i]) do
        segment = segment .. escape_latex(chars[i])
        i = i + 1
      end
      output = output .. "\\ar{" .. segment .. "}"
    elseif is_currency_char(char) then
      output = output .. "\\currency{" .. escape_latex(char) .. "}"
      i = i + 1
    elseif is_symbol_only_char(char) then
      output = output .. "\\symb{" .. escape_latex(char) .. "}"
      i = i + 1
    elseif code == 0x1FAF1 or code == 0x1FAF2 then
      output = output .. "\\emojisupplement{" .. escape_latex(char) .. "}"
      i = i + 1
    elseif is_emoji_char(char) then
      local segment = ""
      while i <= #chars do
        local current = chars[i]
        local current_code = utf8.codepoint(current)
        if is_symbol_only_char(current) or current_code == 0x1FAF1 or current_code == 0x1FAF2 then
          break
        end
        if not is_emoji_char(current) or current_code == 0x200D or current_code == 0xFE0F then
          if current_code == 0x200D or current_code == 0xFE0F then
            segment = segment .. escape_latex(current)
            i = i + 1
          else
            break
          end
        else
          segment = segment .. escape_latex(current)
          i = i + 1
        end

        if i <= #chars and utf8.codepoint(chars[i]) >= 0x1F1E6 and utf8.codepoint(chars[i]) <= 0x1F1FF and (code >= 0x1F1E6 and code <= 0x1F1FF) then
          segment = segment .. escape_latex(chars[i])
          i = i + 1
        end

        if i <= #chars then
          local next_code = utf8.codepoint(chars[i])
          if next_code == 0x200D or next_code == 0xFE0F then
            segment = segment .. escape_latex(chars[i])
            i = i + 1
          end
        end

        if not (i <= #chars and is_emoji_char(chars[i])) then
          break
        end
      end
      output = output .. "\\emoji{" .. segment .. "}"
    elseif is_symbol_char(char) then
      local segment = ""
      while i <= #chars and is_symbol_char(chars[i]) do
        segment = segment .. escape_latex(chars[i])
        i = i + 1
      end
      output = output .. "\\symb{" .. segment .. "}"
    else
      output = output .. escape_latex(char)
      i = i + 1
    end
  end

  return output
end

local function contains_arabic(text)
  for _, codepoint in utf8.codes(text) do
    if (codepoint >= 0x0600 and codepoint <= 0x06FF)
      or (codepoint >= 0x0750 and codepoint <= 0x077F)
      or (codepoint >= 0x08A0 and codepoint <= 0x08FF)
      or (codepoint >= 0xFB50 and codepoint <= 0xFDFF)
      or (codepoint >= 0xFE70 and codepoint <= 0xFEFF) then
      return true
    end
  end
  return false
end

local function set_arabic_paragraph_direction(block)
  if contains_arabic(pandoc.utils.stringify(block)) then
    local content = block.content or block.c
    local NO_INDENT = pandoc.RawInline("latex", "\\noindent")
    table.insert(content, 1, NO_INDENT)
    table.insert(content, 2, pandoc.RawInline("latex", "{} "))
    if block.content then
      block.content = content
    else
      block.c = content
    end
    return {
      pandoc.RawBlock("latex", "\\begin{ArabicParagraph}"),
      block,
      pandoc.RawBlock("latex", "\\end{ArabicParagraph}")
    }
  end
  return block
end

function Para(el)
  return set_arabic_paragraph_direction(el)
end

function Plain(el)
  return set_arabic_paragraph_direction(el)
end

function Str(el)
  return pandoc.RawInline("latex", process_text(el.text))
end

function Header(el)
  if pandoc.utils.stringify(el):match("^%s*$") then
    return {}
  end
end

function Table(tbl)
  for _, row in ipairs(tbl.bodies[1].body) do
    for _, cell in ipairs(row.cells) do
      for _, block in ipairs(cell) do
        if block.t == "Para" then
          for i, inline in ipairs(block.c) do
            if inline.t == "Str" then
              block.c[i] = pandoc.RawInline("latex", process_text(inline.text))
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

return {
  traverse = "topdown",
  Para = Para,
  Plain = Plain,
  Str = Str,
  Header = Header,
  Table = Table,
  HorizontalRule = HorizontalRule,
}
