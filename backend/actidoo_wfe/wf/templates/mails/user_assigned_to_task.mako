Dear ${user.full_name or user.email},

A new task has been assigned to you:

Workflow: ${task.workflow_instance.title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
Task: ${task.title}

${generate_instance_url(task.workflow_instance.id)}

${email_signature}