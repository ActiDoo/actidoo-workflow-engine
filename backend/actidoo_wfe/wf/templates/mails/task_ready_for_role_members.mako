${_("Hello")} ${user.full_name or user.email},

${_("A task in your role(s) {roles} is waiting for someone to pick it up:").format(roles=", ".join(role_names))}

${_("Workflow:")} ${workflow_title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
${_("Task:")} ${task_title}

${generate_instance_url(task.workflow_instance.id)}
