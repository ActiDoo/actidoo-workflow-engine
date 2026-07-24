${_("Hello,")}

${_("The following workflow tasks are in an error state ({n_total} total, {n_new} new):").format(n_total=n_total, n_new=n_new)}

% for item in items:
% if item["is_new"]:
* ${_("NEW")} * ${item["title"]}
% else:
${item["title"]}
% endif
${item["admin_url"]}

% endfor
${signature_block}