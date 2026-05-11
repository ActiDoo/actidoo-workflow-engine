${_("Hello")} ${user.full_name or user.email},

${_("A new task has been assigned to you:")}

${_("Workflow:")} ${workflow_title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
${_("Task:")} ${task_title}

${generate_instance_url(task.workflow_instance.id)}
${signature_block}