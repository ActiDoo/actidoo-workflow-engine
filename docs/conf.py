# Sphinx build configuration. See https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "Actidoo WFE"
html_title = "Actidoo WFE"
language = "en"

extensions = [
    "myst_parser",           # Markdown instead of reStructuredText
    "sphinxcontrib.mermaid", # ```mermaid fences
]

# Markdown dialect. colon_fence gives us ::: directives (admonitions), the attrs
# extensions allow {.class} / {#id} annotations.
myst_enable_extensions = [
    "attrs_block",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "fieldlist",
]
# ```mermaid blocks are handed to the mermaid directive.
myst_fence_as_directive = ["mermaid"]
# Slugs for headings up to level 3, so [text](glossary.md#some-term) resolves.
myst_heading_anchors = 3

html_theme = "furo"
html_static_path = []
exclude_patterns = ["_build", "requirements.txt"]
