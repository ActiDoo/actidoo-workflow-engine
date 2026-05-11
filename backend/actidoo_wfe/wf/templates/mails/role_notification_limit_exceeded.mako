${_("A task notification was sent only to a capped subset of role members.")}

${_("Workflow:")} ${workflow_title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
${_("Task:")} ${task_title}
${_("Role(s):")} ${", ".join(role_names)}

${_("The role contains {total} members with an email address, which exceeds the configured cap of {cap}. Only the first {cap} members (sorted by email) were notified.").format(total=total_role_members, cap=cap)}

${generate_workflow_instance_admin_url(task.workflow_instance.id)}
${signature_block}