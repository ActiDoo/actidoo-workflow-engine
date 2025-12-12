"""
This module contains customizations to the SpiffWorkflow BPMN engine.
- serialize / deserialize additional data in the task/workflow instances (assigned users, ...)
- parse additional values
- script engine customization
"""

import logging
import re
import traceback
import uuid
from copy import copy, deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

import orjson
from SpiffWorkflow.bpmn.exceptions import WorkflowDataException
from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser, full_tag
from SpiffWorkflow.bpmn.parser.ProcessParser import ProcessParser
from SpiffWorkflow.bpmn.script_engine.feel_engine import FeelLikeScriptEngine
from SpiffWorkflow.bpmn.script_engine.python_engine import PythonScriptEngine
from SpiffWorkflow.bpmn.script_engine.python_environment import TaskDataEnvironment
from SpiffWorkflow.bpmn.serializer.config import ParallelMultiInstanceTask, SequentialMultiInstanceTask
from SpiffWorkflow.bpmn.serializer.default.process_spec import BpmnProcessSpecConverter
from SpiffWorkflow.bpmn.serializer.default.task_spec import (
    BpmnTaskSpecConverter,
    EventConverter,
    MultiInstanceTaskConverter,
)
from SpiffWorkflow.bpmn.serializer.helpers.bpmn_converter import BpmnConverter
from SpiffWorkflow.bpmn.serializer.workflow import BpmnWorkflowSerializer
from SpiffWorkflow.bpmn.specs import BpmnProcessSpec
from SpiffWorkflow.bpmn.specs.data_spec import TaskDataReference
from SpiffWorkflow.bpmn.specs.defaults import IntermediateCatchEvent, IntermediateThrowEvent, ServiceTask, StartEvent
from SpiffWorkflow.bpmn.specs.event_definitions.timer import TimerEventDefinition
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.camunda.parser.CamundaParser import (
    NSMAP,
    CamundaIntermediateCatchEventParser,
    CamundaIntermediateThrowEventParser,
    CamundaParser,
    CamundaStartEventParser,
    CamundaTaskParser,
)
from SpiffWorkflow.camunda.serializer.config import CAMUNDA_CONFIG
from SpiffWorkflow.camunda.serializer.task_spec import UserTaskConverter
from SpiffWorkflow.camunda.specs.user_task import UserTask
from SpiffWorkflow.task import Task

from actidoo_wfe.helpers.mixin import ensure_mixin
from actidoo_wfe.helpers.modules import env_from_module
from actidoo_wfe.wf import providers as workflow_providers
from actidoo_wfe.wf.constants import (
    INTERNAL_DATA_KEY_ASSIGNED_USER,
    INTERNAL_DATA_KEY_STACKTRACE,
)
from actidoo_wfe.wf.exceptions import FormNotFoundException
from actidoo_wfe.wf.form_transformation import empty_form, transform_camunda_form_from_file
from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper
from actidoo_wfe.wf.types import TaskToUserMapping

log = logging.getLogger(__name__)

class MyUserTask(UserTask):
    def __init__(self, wf_spec, name, form, custom_props, **kwargs):
        super().__init__(wf_spec, name, form, **kwargs)
        self.custom_props = custom_props

class MyCamundaUserTaskParser(CamundaTaskParser):
    def create_task(self):
        form = self.get_form()
        custom_props = self.get_custom_props()
        return self.spec_class(
            self.spec, self.bpmn_id, form=form, custom_props=custom_props, **self.bpmn_attributes
        )

    def get_custom_props(self):
        elements = self.xpath(".//zeebe:property")
        props = {e.attrib["name"]: e.attrib["value"] for e in elements if "name" in e.attrib.keys() and "value" in e.attrib.keys()}
        return props

    def get_form(self):
        """Camunda provides a simple form builder; this extracts the form details and constructs a form model."""
        if self.filename is None:
            raise FormNotFoundException(
                f"form file not found for process {self.process_parser.bpmn_id} and usertask {self.bpmn_id}: filename is None"
            )
        form_file_path = Path(self.filename).parent / (self.bpmn_id + ".form")
        if not form_file_path.exists():
            log.exception(f"form file not found for process {self.process_parser.bpmn_id} and usertask {self.bpmn_id}: {str(form_file_path)}")
            raise FormNotFoundException(
                f"form file not found for process {self.process_parser.bpmn_id} and usertask {self.bpmn_id}: {str(form_file_path)}"
            )
        form = transform_camunda_form_from_file(form_file_path)
        return form

class MyCamundaStartEventParser(CamundaStartEventParser):
    def create_task(self):
        task = super().create_task()
        form = self.get_form()
        task.form = form
        return task

    def get_form(self):
        """Camunda provides a simple form builder; this extracts the start form and constructs a form model."""
        if self.filename is None:
            return empty_form()
        form_file_path = Path(self.filename).parent / (self.bpmn_id + ".form")
        form = transform_camunda_form_from_file(form_file_path)
        return form

class MyCamundaServiceTaskParser(CamundaTaskParser):
    def create_task(self):
        service_type = self.get_service_type()
        return self.spec_class(
            self.spec, self.bpmn_id, service_type=service_type, **self.bpmn_attributes
        )

    def get_service_type(self):
        taskDefinitionElements = self.xpath(".//zeebe:taskDefinition")
        service_type = None
        if len(taskDefinitionElements) > 0:
            taskDefinitionElement = taskDefinitionElements[0]
            service_type = taskDefinitionElement.attrib["type"]
        return service_type

class MyServiceTask(ServiceTask):
    # see SpiffWorkflow.spiff.specs.mixins.ServiceTask

    def __init__(self, wf_spec, name, service_type, **kwargs):
        super().__init__(wf_spec, name, **kwargs)
        self.service_type = service_type

    @property
    def spec_type(self):
        return "Service Task"

    def _result_variable(self, task):
        escaped_spec_name = task.task_spec.name.replace("-", "_")
        return f"result_{escaped_spec_name}"

    def _execute(self, task: Task):
        try:
            result = task.workflow.script_engine.call_service(self.service_type, task)
        except Exception as error:
            log.exception(f'Exception in MyServiceTask_execute -> {type(error).__name__}: {error.args}')
            task.error()
            s_traceback = traceback.format_exc()
            task._set_internal_data(**{INTERNAL_DATA_KEY_STACKTRACE: str(s_traceback)})
            log.exception("Error during ServiceTask Execution")
            return False

        parsed_result = orjson.loads(result)
        task.data[self._result_variable(task)] = parsed_result
        return True

class MyCamundaIntermediateThrowEventParser(CamundaIntermediateThrowEventParser):
    def create_task(self):
        task = super().create_task()
        service_type = self.get_service_type()
        task.set_service_type(service_type)
        return task

    def get_service_type(self):
        taskDefinitionElements = self.xpath(".//zeebe:taskDefinition")
        service_type = None
        if len(taskDefinitionElements) > 0:
            taskDefinitionElement = taskDefinitionElements[0]
            service_type = taskDefinitionElement.attrib["type"]
        return service_type

class MyIntermediateThrowEvent(IntermediateThrowEvent):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.set_service_type(kw.get("service_type"))

    def set_service_type(self, service_type):
        self.service_type = service_type

    def _result_variable(self, task):
        escaped_spec_name = task.task_spec.name.replace("-", "_")
        return f"result_{escaped_spec_name}"

    def _execute(self, task: Task):
        try:
            result = task.workflow.script_engine.call_service(self.service_type, task)
        except Exception:
            task.error()
            s_traceback = traceback.format_exc()
            task._set_internal_data(**{INTERNAL_DATA_KEY_STACKTRACE: str(s_traceback)})
            log.exception("Error during ServiceTask Execution")
            return False

        parsed_result = orjson.loads(result)
        task.data[self._result_variable(task)] = parsed_result
        return True

    def _run_hook(self, task):
        return self._execute(task)

class MyCamundaIntermediateCatchEventParser(CamundaIntermediateCatchEventParser):
    def create_task(self):
        task = super().create_task()
        correlation_key = self.get_correlation_key()
        form = self.get_form()
        task.set_correlation_key(correlation_key)
        task.set_form(form)
        return task

    def get_correlation_key(self):
        messageRef = self.xpath(".//bpmn:messageEventDefinition")[0].attrib["messageRef"]
        subscriptionElements = self.xpath(f"//*[@id='{messageRef}']//zeebe:subscription")
        correlation_key = None
        if len(subscriptionElements) > 0:
            subscriptionElement = subscriptionElements[0]
            correlation_key = subscriptionElement.attrib["correlationKey"]
        return correlation_key

    def get_form(self):
        """Camunda provides a simple form builder; this extracts the form details and constructs a form model."""
        if self.filename is None:
            return empty_form()
        form_file_path = Path(self.filename).parent / (self.bpmn_id + ".form")
        form = transform_camunda_form_from_file(form_file_path)
        return form

class MyIntermediateCatchEvent(IntermediateCatchEvent):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.set_correlation_key(kw.get("correlation_key"))
        self.set_form(kw.get("form"))

    def set_form(self, form):
        self.form = form

    def set_correlation_key(self, correlation_key):
        self.correlation_key = correlation_key

    def evaluate_correlation_key(self, task):
        result = task.workflow.script_engine.evaluate(task, self.correlation_key, {
            "instance_id": str(task.workflow.task_tree.id)
        })
        return result

class FeelExpressionReference:
    """
    DataSpec-like wrapper for FEEL expressions.
    - get(task): evaluate FEEL in the given task context
    - exists(task): True if get() returns a non-None value
    - set(): forbidden (read-only expression)
    Note: No caching; expressions are evaluated on each access.
    """
    def __init__(self, expr: str, bpmn_id: str):
        self.expr = expr.strip()
        self.bpmn_id = bpmn_id

    def get(self, task):
        # FEEL evaluation is routed by the script engine (leading '=' supported there)
        return task.workflow.script_engine.evaluate(task, self.expr)

    def exists(self, task) -> bool:
        try:
            return self.get(task) is not None
        except Exception:
            return False

    def set(self, task, value):
        raise WorkflowDataException(
            f'Cannot set value of FEEL expression "{self.expr}".', task
        )
    
class MultiInstanceMixin:
    def _add_multiinstance_task(self, loop_characteristics):
        """
        Simplified MI parser for Camunda 8 / Zeebe diagrams only.

        Expected structure:
          <bpmn:multiInstanceLoopCharacteristics [isSequential="true|false"]>
            <bpmn:extensionElements>
              <zeebe:loopCharacteristics
                  inputCollection="=feelExpr"
                  inputElement="varName"
                  [outputCollection="collectionVar"]
                  [outputElement="=feelExpr"] />
            </bpmn:extensionElements>
            <bpmn:completionCondition xsi:type="bpmn:tFormalExpression">=feelExpr</bpmn:completionCondition>
          </bpmn:multiInstanceLoopCharacteristics>
        """
        # --- basic flags ---
        sequential = loop_characteristics.get('isSequential') == 'true'

        # --- resolve Zeebe loopCharacteristics node ---
        z_nodes = self.xpath('./bpmn:multiInstanceLoopCharacteristics/bpmn:extensionElements/zeebe:loopCharacteristics')
        if not z_nodes:
            self.raise_validation_exception("Missing zeebe:loopCharacteristics inside multiInstanceLoopCharacteristics.")
        z = z_nodes[0]

        # --- read attributes (Camunda semantics) ---
        in_coll_raw = z.get('inputCollection')        # FEEL (required)
        in_elem_raw = z.get('inputElement')           # string (required)
        out_coll_raw = z.get('outputCollection')      # string (optional)
        out_elem_raw = z.get('outputElement')         # FEEL (optional)

        # completionCondition primarily on BPMN node; Zeebe attr rarely used
        cond_nodes = self.xpath('./bpmn:multiInstanceLoopCharacteristics/bpmn:completionCondition')
        condition = cond_nodes[0].text if len(cond_nodes) > 0 else z.get('completionCondition')

        # --- minimal validation for Camunda style ---
        if not in_coll_raw:
            self.raise_validation_exception("zeebe:loopCharacteristics@inputCollection is required (FEEL).")
        if not in_elem_raw:
            self.raise_validation_exception("zeebe:loopCharacteristics@inputElement is required (string).")
        if out_elem_raw and not out_coll_raw:
            self.raise_validation_exception("outputElement requires outputCollection.")

        # --- build data refs / expressions ---
        # FEEL inputCollection → evaluate at runtime
        loop_input = FeelExpressionReference(
            expr=in_coll_raw,
            bpmn_id=f'{self.bpmn_id}::inputCollection',
        )

        # inputElement (plain string)
        input_item = TaskDataReference(in_elem_raw)

        # outputCollection (plain string; optional)
        loop_output = TaskDataReference(out_coll_raw) if out_coll_raw else None

        # FEEL outputElement (optional; evaluated per child)
        output_item = FeelExpressionReference(
            expr=out_elem_raw,
            bpmn_id=f'{self.bpmn_id}::outputElement',
        ) if out_elem_raw else None

        # --- create Spiff MI task (no cardinality support in this simplified variant) ---
        original = self.spec.task_specs.pop(self.task.name)
        params = {
            'task_spec': '',
            'cardinality': None,           # not supported in this simplified Camunda mode
            'data_input': loop_input,
            'data_output': loop_output,
            'input_item': input_item,
            'output_item': output_item,
            'condition': condition,        # FEEL string (kept with '='), evaluated at runtime
        }

        if sequential:
            self.task = self.SEQUENTIAL_MI_CLASS(
                self.spec, original.name, description='Sequential MultiInstance', **params
            )
        else:
            self.task = self.PARALLEL_MI_CLASS(
                self.spec, original.name, description='Parallel MultiInstance', **params
            )

        self._copy_task_attrs(original, loop_characteristics)

def apply_mixin_overrides(override_map, mixin):
    """
    Apply the given mixin to every parser class inside the map (idempotent).
    """
    new_map = {}
    for tag, (parser_cls, model_cls) in override_map.items():
        new_map[tag] = (ensure_mixin(parser_cls, mixin), model_cls)
    return new_map

OVERRIDE_PARSER_CLASSES = copy(BpmnParser.PARSER_CLASSES)
OVERRIDE_PARSER_CLASSES.update(CamundaParser.OVERRIDE_PARSER_CLASSES)
OVERRIDE_PARSER_CLASSES[full_tag("userTask")] = (MyCamundaUserTaskParser, MyUserTask)
OVERRIDE_PARSER_CLASSES[full_tag("serviceTask")] = (
    MyCamundaServiceTaskParser,
    MyServiceTask,
)
OVERRIDE_PARSER_CLASSES[full_tag("intermediateThrowEvent")] = (
    MyCamundaIntermediateThrowEventParser,
    MyIntermediateThrowEvent,
)
OVERRIDE_PARSER_CLASSES[full_tag("intermediateCatchEvent")] = (
    MyCamundaIntermediateCatchEventParser,
    MyIntermediateCatchEvent,
)
OVERRIDE_PARSER_CLASSES[full_tag("startEvent")] = (MyCamundaStartEventParser, StartEvent)

OVERRIDE_PARSER_CLASSES = apply_mixin_overrides(OVERRIDE_PARSER_CLASSES, MultiInstanceMixin)

MY_NSMAP = copy(NSMAP)
MY_NSMAP["zeebe"] = "http://camunda.org/schema/zeebe/1.0"

class MyProcessParser(ProcessParser):
    def get_wflanes(self):
        lane_xpath = "//bpmn:lane"
        custom_properties_xpath = "bpmn:extensionElements/zeebe:properties/zeebe:property"
        node_xpath = "bpmn:flowNodeRef"

        wflanes = {}

        lanes = self.xpath(lane_xpath)
        if len(lanes) == 0:
            raise Exception(f"No lanes found in {self.spec.name}, but we expect at least one lane.")  # type: ignore

        for lane in lanes:
            lane_id = lane.get("id")
            if not lane_id:
                raise Exception(f"Lane without ID found in {self.spec.name}. This should not happen if Camunda Modeler saved the file correctly.")  # type: ignore

            lane_name = lane.get("name")
            if not lane_name:
                log.warning(f"Lane with no name found in {self.spec.name}, will take id='{lane_id}' as fallback")  # type: ignore
            custom_properties = {}

            properties = lane.xpath(custom_properties_xpath, namespaces=MY_NSMAP)
            for prop in properties:
                name = prop.get("name")
                value = prop.get("value")
                custom_properties[name] = value

            nodes = lane.xpath(node_xpath, namespaces=MY_NSMAP)
            nodes_list = [node_ref.text for node_ref in nodes]

            wflanes[lane_id] = {
                "id": lane_id,
                "name": lane_name,
                "custom_properties": custom_properties,
                "nodes": nodes_list
            }

        return wflanes

    def get_custom_props(self):
        elements = self.xpath("./bpmn:extensionElements/zeebe:properties/zeebe:property")
        props = {e.attrib["name"]: e.attrib["value"] for e in elements if "name" in e.attrib.keys() and "value" in e.attrib.keys()}
        return props

    def _parse(self):
        # This is where the real parsing of the BPMN happens by the SpiffWorkflow engine
        ret = super()._parse()
        self.spec.custom_props = self.get_custom_props()
        self.spec.wflanes = self.get_wflanes()
        return ret

class MyCamundaParser(CamundaParser):
    OVERRIDE_PARSER_CLASSES = OVERRIDE_PARSER_CLASSES
    PROCESS_PARSER_CLASS = MyProcessParser

    def __init__(self, namespaces=None, validator=None):
        super().__init__(namespaces=namespaces or MY_NSMAP, validator=validator)

class MyUserTaskConverter(UserTaskConverter):
    def to_dict(self, spec):
        dct = self.get_default_attributes(spec)
        dct["form"] = spec.form
        if hasattr(spec, "custom_props"):
            dct["custom_props"] = spec.custom_props
        else:
            dct["custom_props"] = {}
        return dct

    def from_dict(self, dct):
        return self.task_spec_from_dict(dct)

class MyServiceTaskConverter(BpmnTaskSpecConverter):
    def __init__(self, target_class, registry):
        super().__init__(target_class, registry)

    def to_dict(self, spec):
        dct = self.get_default_attributes(spec)
        dct["service_type"] = spec.service_type
        return dct

    def from_dict(self, dct):
        return self.task_spec_from_dict(dct)

class MyStartEventConverter(EventConverter):
    def to_dict(self, spec):
        dct = super().to_dict(spec)
        dct["form"] = getattr(spec, "form", None)
        return dct

    def from_dict(self, dct):
        return super().from_dict(dct=dct)

class MyIntermediateThrowEventConverter(EventConverter):
    def to_dict(self, spec):
        dct = super().to_dict(spec)
        dct["service_type"] = getattr(spec, "service_type", None)
        return dct

    def from_dict(self, dct):
        return super().from_dict(dct=dct)

class MyIntermediateCatchEventConverter(EventConverter):
    def to_dict(self, spec):
        dct = super().to_dict(spec)
        dct["correlation_key"] = getattr(spec, "correlation_key", None)
        dct["form"] = getattr(spec, "form", None)
        return dct

    def from_dict(self, dct):
        return super().from_dict(dct=dct)

class MyBpmnProcessSpecConverter(BpmnProcessSpecConverter):
    def to_dict(self, spec):
        dct = super().to_dict(spec)
        dct["wflanes"] = getattr(spec, "wflanes", None)
        dct["custom_props"] = getattr(spec, "custom_props", None)
        return dct

    def from_dict(self, dct):
        ret = super().from_dict(dct=dct)
        ret.wflanes = dct.get("wflanes", None)
        ret.custom_props = dct.get("custom_props", None)
        return ret

class FeelDataSpecificationConverter(BpmnConverter):
    """
    Serializer for FEEL DataSpecs.
    JSON → {'expr': '=...', 'bpmn_id': 'Task_1::...'}
    """

    def to_dict(self, data_spec: FeelExpressionReference):
        # Only JSON-safe fields; no caching metadata
        return {
            "expr": data_spec.expr,      # including leading '=' if present
            "bpmn_id": data_spec.bpmn_id,
        }

    def from_dict(self, dct):
        # Rebuild runtime object (ignore any extra fields like 'cache' from old dumps)
        return FeelExpressionReference(
            expr=dct.get("expr", ""),
            bpmn_id=dct.get("bpmn_id", ""),
        )

MY_CAMUNDA_SPEC_CONFIG = deepcopy(CAMUNDA_CONFIG)
MY_CAMUNDA_SPEC_CONFIG[MyServiceTask] = MyServiceTaskConverter
MY_CAMUNDA_SPEC_CONFIG[MyUserTask] = MyUserTaskConverter
MY_CAMUNDA_SPEC_CONFIG[UserTask] = MyUserTaskConverter  # Backwards compatibility
MY_CAMUNDA_SPEC_CONFIG.pop(StartEvent)
MY_CAMUNDA_SPEC_CONFIG[StartEvent] = MyStartEventConverter
MY_CAMUNDA_SPEC_CONFIG.pop(IntermediateThrowEvent)
MY_CAMUNDA_SPEC_CONFIG[MyIntermediateThrowEvent] = MyIntermediateThrowEventConverter
MY_CAMUNDA_SPEC_CONFIG.pop(IntermediateCatchEvent)
MY_CAMUNDA_SPEC_CONFIG[MyIntermediateCatchEvent] = MyIntermediateCatchEventConverter

MY_CAMUNDA_SPEC_CONFIG.pop(BpmnProcessSpec)
MY_CAMUNDA_SPEC_CONFIG[BpmnProcessSpec] = MyBpmnProcessSpecConverter

MY_CAMUNDA_SPEC_CONFIG[FeelExpressionReference] = FeelDataSpecificationConverter

MY_CAMUNDA_SPEC_CONFIG[ParallelMultiInstanceTask] = MultiInstanceTaskConverter
MY_CAMUNDA_SPEC_CONFIG[SequentialMultiInstanceTask] = MultiInstanceTaskConverter

def get_parser():
    parser = MyCamundaParser()
    return parser

def get_serializer():
    registry = BpmnWorkflowSerializer.configure(
        config=MY_CAMUNDA_SPEC_CONFIG
    )
    serializer = BpmnWorkflowSerializer(
        registry=registry
    )
    return serializer

class MyScriptEngine(FeelLikeScriptEngine):
    def __init__(self, environment):
        super().__init__(environment=environment)

    def call_service(self, service_type, task):
        """This method is called for service tasks"""
        task_data = task.data
        # service_type is not the task id (like Activity_06zketc), but the Type of the Task Definition (like 'evaluate_form_1')
        # TODO: What about the global environment here?
        service_def = self.environment.globals.get("service_" + service_type, None)
        result = {}
        workflow: BpmnWorkflow = task.workflow

        if service_def is None:
            log.error(f"Service for {service_type} is not defined")
            raise Exception(f"Service for {service_type} is not defined")
        else:
            task_to_user_mapping: TaskToUserMapping = self.get_task_to_user_mapping(
                workflow=workflow
            )

            sth = ServiceTaskHelper(
                workflow=workflow,
                task_data=task_data,
                task_to_user_mapping=task_to_user_mapping,
                task_uuid=task.id
            )
            result = service_def(sth=sth)

        return orjson.dumps(result)

    def validate(self, expression):
        if expression.startswith("="):
            return FeelLikeScriptEngine.validate(self, expression.lstrip("= "))
        else:
            return PythonScriptEngine.validate(self, expression)

    def execute(self, task, script, external_context=None):
        return PythonScriptEngine.execute(self, task, script, external_context)

    def _evaluate(self, expression, context, external_context=None):
        if expression.startswith("="):
            return FeelLikeScriptEngine._evaluate(
                self, expression.lstrip("= "), context, external_context = external_context
            )
        else:
            return self.environment.evaluate(expression, context, external_context)
            #return PythonScriptEngine.evaluate(
            #    self, expression, context, external_context
            #)

    def patch_expression(self, invalid_python, lhs=""):
        patched = super().patch_expression(invalid_python, lhs)
        # Replace single '=' (assignment/equality ambiguity) with '==', but avoid '==', '<=', '>=', '!='
        patched = re.sub(r"(?<!=|<|>|\!)=(?!=|<|>|\!)", "==", patched)
        return patched

    def get_task_to_user_mapping(self, workflow: BpmnWorkflow) -> TaskToUserMapping:
        tasks: Dict[uuid.UUID, Task] = {t.id: t for t in workflow.get_tasks()}
        mapping: TaskToUserMapping = dict()
        for task in tasks.values():
            user = task._get_internal_data(INTERNAL_DATA_KEY_ASSIGNED_USER, None)
            if user is not None:
                mapping[task] = user
        return mapping

def get_script_engine(workflow_name):
    env_globals: Dict[str, object] = {}
    module_path = workflow_providers.get_workflow_module_path(workflow_name)
    if module_path:
        try:
            env_globals.update(env_from_module(module_path))
        except ImportError:
            log.debug("No module found for workflow '%s' at '%s'", workflow_name, module_path)
    custom_env = TaskDataEnvironment(env_globals)
    custom_script_engine = MyScriptEngine(environment=custom_env)
    return custom_script_engine
