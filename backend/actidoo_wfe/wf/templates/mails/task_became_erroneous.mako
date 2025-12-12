A task became erroneous:

Workflow: ${task.workflow_instance.title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
Task: ${task.title}

${generate_workflow_instance_admin_url(task.workflow_instance.id)}

${email_signature}