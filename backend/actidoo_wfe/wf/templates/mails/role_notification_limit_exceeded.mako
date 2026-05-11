A task notification was sent only to a capped subset of role members.

Workflow: ${task.workflow_instance.title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
Task: ${task.title}
Role${"s" if len(role_names) > 1 else ""}: ${", ".join(role_names)}

The role contains ${total_role_members} members with an email address, which exceeds the configured cap of ${cap}. Only the first ${cap} members (sorted by email) were notified. Consider narrowing the role membership or raising notify_role_members_max for this lane.

${generate_workflow_instance_admin_url(task.workflow_instance.id)}

${email_signature}
