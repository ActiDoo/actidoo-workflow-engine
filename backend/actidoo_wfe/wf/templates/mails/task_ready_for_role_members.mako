Dear ${user.full_name or user.email},

A task in your role${"s" if len(role_names) > 1 else ""} ${", ".join(role_names)} is waiting for someone to pick it up:

Workflow: ${task.workflow_instance.title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
Task: ${task.title}

${generate_instance_url(task.workflow_instance.id)}

${email_signature}
