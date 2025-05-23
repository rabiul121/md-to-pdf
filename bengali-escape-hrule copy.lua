-- Combined Lua filter: wrap Bengali + escape LaTeX + fix HorizontalRule

-- Utility: Identify Bengali characters (including danda U+0964, U+0965)
local function is_bengali_char(char)
  local code = utf8.codepoint(char)
  return code == 0x0964 or code == 0x0965 or (code >= 0x0980 and code <= 0x09FF)
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

-- Process text: wrap Bengali and escape all LaTeX specials
local function process_text(text)
  local output = ""
  local in_bengali = false

  for _, c in utf8.codes(text) do
    local char = utf8.char(c)
    if is_bengali_char(char) then
      if not in_bengali then
        output = output .. "\\bn{"
        in_bengali = true
      end
      output = output .. escape_latex(char)
    else
      if in_bengali then
        output = output .. "}"
        in_bengali = false
      end
      output = output .. escape_latex(char)
    end
  end

  if in_bengali then
    output = output .. "}"
  end

  return output
end

-- Inline string processor
function Str(el)
  local new_text = process_text(el.text)
  return pandoc.RawInline("latex", new_text)
end

-- Escape + wrap Bengali text inside table cells
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
