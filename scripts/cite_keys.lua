-- Print citation keys as breakable text in the PDF, so long keys wrap instead of running into the margin.
function Cite(el)
  if FORMAT ~= "latex" then return nil end
  local keys = {}
  for _, c in ipairs(el.citations) do
    table.insert(keys, "\\nolinkurl{" .. c.id .. "}")
  end
  return pandoc.RawInline("latex", "[" .. table.concat(keys, "; ") .. "]")
end
