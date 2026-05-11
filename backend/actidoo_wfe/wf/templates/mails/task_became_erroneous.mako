${_("A task became erroneous:")}

${_("Workflow:")} ${workflow_title}${(" / "+task.workflow_instance.subtitle) if task.workflow_instance.subtitle else ""}
${_("Task:")} ${task_title}

${generate_workflow_instance_admin_url(task.workflow_instance.id)}
${signature_block}