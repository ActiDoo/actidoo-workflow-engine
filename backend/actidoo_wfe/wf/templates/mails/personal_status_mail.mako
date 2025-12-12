Dear ${user.full_name or user.email},

% if len(assigned_to_me) > 0:
Currently you have personally assigned tasks in the following workflow instances:

% for t in assigned_to_me:
${t.title} / ${t.subtitle}
${generate_instance_url(t.id)}

% endfor
% endif
\
% if len(not_assigned) > 0:
%if len(assigned_to_me) > 0:

%endif

There are also tasks for the groups you are a member of. Feel free to assign these tasks to yourself:

% for t in not_assigned:
${t.title} / ${t.subtitle}
${generate_instance_url(t.id)}

% endfor
% endif
\
${email_signature}