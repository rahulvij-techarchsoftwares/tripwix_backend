from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Protocol, Set, Tuple, Type

from kolo.types import JSON


class Step(Protocol):
    indent_delta: ClassVar[int] = 0

    def render(self, pytest: bool) -> str: ...  # pragma: no branch

    def get_imports(self, pytest: bool) -> Set["Import"]:
        return set()

    @classmethod
    def get_steps(cls, steps: List["Step"]) -> List[Tuple[slice, List["Step"]]]:
        selected = []
        for index, step in enumerate(steps):
            if isinstance(step, cls):
                selected.append((slice(index, index + 1), [step]))
        return selected


def get_steps_slice(
    start_class: Type[Step], end_class: Type[Step], steps: List[Step]
) -> List[Tuple[slice, List[Step]]]:
    selected = []
    indices = []
    for index, step in enumerate(steps):
        if isinstance(step, start_class):
            indices.append(index)
        elif isinstance(step, end_class):
            start_index = indices.pop()
            _slice = slice(start_index, index + 1)
            selected.append((_slice, steps[_slice]))

    return selected


@dataclass(frozen=True)
class Import:
    import_path: str

    def render(self):
        return f"{self.import_path}\n"


@dataclass()
class CodeComment(Step):
    comment: str

    def render(self, pytest):
        return f"# {self.comment}\n"


@dataclass(frozen=True)
class EmptyLine(Step):
    def render(self, pytest):
        return "\n"


@dataclass(frozen=True)
class ModuleImports(Step):
    def render(self, pytest):
        return ""


@dataclass()
class TestClass(Step):
    name: str
    parents: Tuple[str, ...] = field(default_factory=tuple)
    imports: Set[Import] = field(default_factory=set)
    indent_delta = 1

    def render(self, pytest):
        parents = ", ".join(self.parents)
        return f"class {self.name}({parents}):\n"

    def get_imports(self, pytest):
        return self.imports

    @classmethod
    def get_steps(cls, steps: List[Step]) -> List[Tuple[slice, List[Step]]]:
        return get_steps_slice(cls, EndTestClass, steps)


@dataclass(frozen=True)
class EndTestClass(Step):
    indent_delta = -1

    def render(self, pytest):
        return ""


@dataclass()
class Code(Step):
    code: str
    imports: Set[Import] = field(default_factory=set)

    def render(self, pytest):
        return f"{self.code}\n"

    def get_imports(self, pytest):
        return self.imports


@dataclass()
class TestMethod(Step):
    name: str
    indent_delta = 1

    def render(self, pytest):
        return f"def {self.name}(self):\n"

    @classmethod
    def get_steps(cls, steps: List[Step]) -> List[Tuple[slice, List[Step]]]:
        return get_steps_slice(cls, EndTestMethod, steps)


@dataclass(frozen=True)
class EndTestMethod(Step):
    indent_delta = -1

    def render(self, pytest):
        return ""


@dataclass()
class TestFunction(Step):
    name: str
    fixtures: Tuple[str, ...] = field(default_factory=tuple)
    indent_delta = 1

    def render(self, pytest):
        fixtures = ", ".join(self.fixtures)
        return f"def {self.name}({fixtures}):\n"

    @classmethod
    def get_steps(cls, steps: List[Step]) -> List[Tuple[slice, List[Step]]]:
        return get_steps_slice(cls, EndTestFunction, steps)


@dataclass(frozen=True)
class EndTestFunction(Step):
    indent_delta = -1

    def render(self, pytest):
        return ""


@dataclass()
class StartTimeTravel(Step):
    call: str
    args: Tuple[str, ...] = field(default_factory=tuple)
    imports: Set[Import] = field(default_factory=set)
    indent_delta = 1

    def render(self, pytest):
        args = ", ".join(self.args)
        return f"with {self.call}({args}):\n"

    def get_imports(self, pytest):
        return self.imports

    @classmethod
    def get_steps(cls, steps: List[Step]) -> List[Tuple[slice, List[Step]]]:
        return get_steps_slice(cls, EndTimeTravel, steps)


@dataclass(frozen=True)
class EndTimeTravel(Step):
    indent_delta = -1

    def render(self, pytest):
        return ""


@dataclass()
class With(Step):
    call: str
    args: Tuple[str, ...] = field(default_factory=tuple)
    defines_variable_name: Optional[str] = None
    imports: Set[Import] = field(default_factory=set)
    indent_delta = 1

    def render(self, pytest):
        args = ", ".join(self.args)
        if self.defines_variable_name:
            return f"with {self.call}({args}) as {self.defines_variable_name}:\n"
        return f"with {self.call}({args}):\n"

    def get_imports(self, pytest):
        return self.imports

    @classmethod
    def get_steps(cls, steps: List[Step]) -> List[Tuple[slice, List[Step]]]:
        return get_steps_slice(cls, EndWith, steps)


@dataclass(frozen=True)
class EndWith(Step):
    indent_delta = -1

    def render(self, pytest):
        return ""


@dataclass()
class AssertEqual(Step):
    left: str
    right: str
    imports: Set[Import] = field(default_factory=set)

    def render(self, pytest):
        if pytest:
            return f"assert {self.left} == {self.right}\n"
        return f"self.assertEqual({self.left}, {self.right})\n"

    def get_imports(self, pytest):
        return self.imports


@dataclass()
class AssertStatusCode(Step):
    status_code: int

    def render(self, pytest):
        if pytest:
            return f"assert response.status_code == {self.status_code}\n"
        return f"self.assertEqual(response.status_code, {self.status_code})\n"


@dataclass()
class AssertResponseJson(Step):
    response_json: JSON

    def render(self, pytest):
        if pytest:
            return f"assert response.json() == {self.response_json}\n"
        return f"self.assertEqual(response.json(), {self.response_json})\n"


@dataclass()
class AssertTemplateUsed(Step):
    template_name: str

    def render(self, pytest):
        if pytest:
            assertTemplateUsed = "assertTemplateUsed"
        else:
            assertTemplateUsed = "self.assertTemplateUsed"
        return f"{assertTemplateUsed}(response, {repr(self.template_name)})\n"

    def get_imports(self, pytest):
        if pytest:
            return {Import("from pytest_django.asserts import assertTemplateUsed")}
        return set()


@dataclass()
class RegisterMocket(Step):
    method: str
    url: str
    status_code: int
    body: Optional[str] = None
    json_body: Optional[JSON] = None
    content_type: str = ""

    @classmethod
    def from_outbound_request(cls, outbound_request):
        request = outbound_request["request"]
        response = outbound_request["response"]
        return cls(
            request["method"],
            request["url"],
            response["status_code"],
            response["body"],
            response.get("json_body", None),
            response["content_type"],
        )

    def render(self, pytest):
        rendered = f"""\
Entry.single_register(
    Entry.{self.method},
    "{self.url}",
    status={self.status_code},
"""
        if self.json_body:
            rendered += f"    body=json.dumps({self.json_body}),\n"
        elif self.body:
            rendered += f"    body={repr(self.body)},\n"
        if self.content_type:
            rendered += f'    headers={{"Content-Type": {repr(self.content_type)}}},'
        rendered += ")\n"
        return rendered

    def get_imports(self, pytest):
        imports = {Import("from mocket.mockhttp import Entry")}
        if self.json_body:
            imports.add(Import("import json"))
        return imports


@dataclass()
class DjangoTestClient(Step):
    method: str
    path_info: str
    query_params: Dict[str, Any]
    request_body: Dict[str, Any]
    headers: Dict[str, Any]

    def render(self, pytest):
        if pytest:
            client = "client"
        else:
            client = "self.client"
        rendered = f"""\
response = {client}.{self.method}(
    {repr(self.path_info)},
"""
        if self.request_body:
            rendered += self.render_query_dict(self.request_body)
        elif self.query_params:
            rendered += self.render_query_dict(self.query_params)
        for header, value in self.headers.items():
            rendered += f"    {header}={repr(value)},\n"
        rendered += ")\n"
        return rendered

    def render_query_dict(self, query_dict):
        rendered = "    {"
        for key, value in query_dict.items():
            if isinstance(value, list) and len(value) == 1:
                value = value[0]
            rendered += f"    {repr(key)}: {repr(value)},\n"
        rendered += "    },"
        return rendered


@dataclass(frozen=True)
class DjangoField:
    name: str
    value: str
    imports: Set[Import] = field(default_factory=set)

    @classmethod
    def from_field(cls, field):
        return cls(
            field.name,
            field.value_repr,
            {Import(i) for i in field.imports()},
        )


@dataclass()
class ModelCreate(Step):
    module: str
    model: str
    fields: List[DjangoField]
    defaults: List[DjangoField]
    defines_variable_name: str
    method: str = "get_or_create"

    def get_imports(self, pytest):
        imports = {Import(f"from {self.module} import {self.model}")}
        for field in self.fields:
            imports.update(field.imports)
        for field in self.defaults:
            imports.update(field.imports)
        return imports

    @classmethod
    def from_fixture(cls, fixture):
        return cls(
            module=fixture.module,
            model=fixture.model,
            fields=[DjangoField.from_field(f) for f in fixture.fields],
            defaults=[DjangoField.from_field(fixture.primary_key)],
            defines_variable_name=fixture.variable_name,
        )

    def render(self, pytest):
        rendered = f"{self.defines_variable_name}"
        if self.method == "get_or_create":
            rendered += ", _created"

        rendered += f" = {self.model}.objects.{self.method}(\n"
        for field in self.fields:
            rendered += f"    {field.name}={field.value},\n"

        if self.method == "get_or_create":
            rendered += "    defaults={\n"
            for field in self.defaults:
                rendered += f"        {repr(field.name)}: {field.value},\n"
            rendered += "    },\n"
        rendered += ")\n"
        return rendered


@dataclass()
class ModelUpdate(Step):
    model: str
    fields: List[DjangoField]
    references_variable_name: str

    @classmethod
    def from_fixture(cls, fixture):
        return cls(
            model=fixture.model,
            fields=[DjangoField.from_field(f) for f in fixture.fields],
            references_variable_name=fixture.variable_name,
        )

    def render(self, pytest):
        for field in self.fields:
            rendered = f"{self.references_variable_name}.{field.name} = {field.value}\n"

        rendered += f"{self.references_variable_name}.save()\n"
        return rendered


@dataclass()
class FactoryCreate(Step):
    module: str
    factory: str
    fields: List[DjangoField]
    defines_variable_name: str

    @classmethod
    def from_fixture(cls, fixture):
        return cls(
            module=fixture.module,
            factory=fixture.factory,
            fields=[DjangoField.from_field(f) for f in fixture.fields],
            defines_variable_name=fixture.variable_name,
        )

    def render(self, pytest):
        rendered = f"{self.defines_variable_name} = {self.factory}.create(\n"
        for field in self.fields:
            rendered += f"    {field.name}={field.value},\n"
        rendered += ")\n"
        return rendered

    def get_imports(self, pytest):
        imports = {Import(f"from {self.module} import {self.factory}")}
        for field in self.fields:
            imports.update(field.imports)
        return imports


@dataclass()
class AssertInsert(Step):
    module: str
    model: str
    lookup_fields: List[DjangoField]
    assert_fields: List[DjangoField]
    defines_variable_name: str

    @classmethod
    def from_fixture(cls, fixture):
        lookup_fields, assert_fields = fixture.get_fields()
        return cls(
            module=fixture.module,
            model=fixture.model,
            lookup_fields=[DjangoField.from_field(f) for f in lookup_fields],
            assert_fields=[DjangoField.from_field(f) for f in assert_fields],
            defines_variable_name=fixture.variable_name,
        )

    def render(self, pytest):
        rendered = f"{self.defines_variable_name} = {self.model}.objects.get(\n"
        for field in self.lookup_fields:
            rendered += f"    {field.name}={field.value},\n"
        rendered += ")\n"
        for field in self.assert_fields:
            if pytest:
                rendered += f"assert {self.defines_variable_name}.{field.name} == {field.value}\n"
            else:
                rendered += f"self.assertEqual({self.defines_variable_name}.{field.name}, {field.value})\n"

        return rendered

    def get_imports(self, pytest):
        imports = {Import(f"from {self.module} import {self.model}")}
        for field in self.lookup_fields:
            imports.update(field.imports)
        for field in self.assert_fields:
            imports.update(field.imports)
        return imports


@dataclass()
class AssertUpdate(Step):
    model: str
    fields: List[DjangoField]
    references_variable_name: str

    @classmethod
    def from_fixture(cls, fixture):
        return cls(
            model=fixture.model,
            fields=[DjangoField.from_field(f) for f in fixture.fields],
            references_variable_name=fixture.variable_name,
        )

    def render(self, pytest):
        rendered = f"{self.references_variable_name}.refresh_from_db()\n"
        for field in self.fields:
            if pytest:
                rendered += f"assert {self.references_variable_name}.{field.name} == {field.value}\n"
            else:
                rendered += f"self.assertEqual({self.references_variable_name}.{field.name}, {field.value})\n"
        return rendered

    def get_imports(self, pytest):
        imports = set()
        for field in self.fields:
            imports.update(field.imports)
        return imports


@dataclass()
class AssertDelete(Step):
    module: str
    model: str
    fields: List[DjangoField]

    @classmethod
    def from_fixture(cls, fixture):
        return cls(
            module=fixture.module,
            model=fixture.model,
            fields=[DjangoField.from_field(f) for f in fixture.fields],
        )

    def grouped_fields(self):
        fields: Dict[str, List[str]] = {}
        for field in self.fields:
            fields.setdefault(field.name, []).append(field.value)
        return fields

    def render(self, pytest):
        if pytest:
            rendered = "assert not "
        else:
            rendered = "self.assertFalse("
        rendered += f"{self.model}.objects.filter(\n"

        for name, values in self.grouped_fields().items():
            if len(values) == 1:
                value = values[0]
                rendered += f"    {name}={value},\n"
            else:
                joined_values = ", ".join(values)
                rendered += f"    {name}__in=({joined_values}),\n"
        if pytest:
            rendered += ").exists()\n"
        else:
            rendered += ").exists())\n"
        return rendered

    def get_imports(self, pytest):
        imports = {Import(f"from {self.module} import {self.model}")}
        for field in self.fields:
            imports.update(field.imports)
        return imports
