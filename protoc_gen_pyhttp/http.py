import re
import os
from typing import List, Dict, Union

import google.api.annotations_pb2
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse
from google.protobuf.descriptor_pb2 import FileDescriptorProto, ServiceDescriptorProto, MethodDescriptorProto
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.descriptor import FileDescriptor, FieldDescriptor, Descriptor
from google.api.http_pb2 import HttpRule

from protoc_gen_pyhttp import template, util
from protoc_gen_pyhttp.template import ServiceDesc, MethodDesc, TypeDesc


def generate_file(proto_file: FileDescriptorProto, pool: DescriptorPool, gen: CodeGeneratorResponse.File):
    """构建文件"""
    filename = proto_file.name[:-len(".proto")] + "_pb2_http.py"
    gen.name = filename

    generate_file_content(proto_file, pool, gen)


def generate_file_content(proto_file: FileDescriptorProto, pool: DescriptorPool, gen: CodeGeneratorResponse.File):
    services: List[ServiceDesc] = []

    for service in proto_file.service:
        services.append(build_service(proto_file, pool, service))

    build_comment(proto_file, services)

    uses = set()
    for service_desc in services:
        for method_desc in service_desc.methods:
            if method_desc.request.use:
                uses.add(method_desc.request.use)
            if method_desc.response.use:
                uses.add(method_desc.response.use)
            if method_desc.body_type and method_desc.body_type.use:
                uses.add(method_desc.body_type.use)
            if method_desc.response_body_type and method_desc.response_body_type.use:
                uses.add(method_desc.response_body_type.use)

    # 一些公用引入
    has_vars = False
    has_repeated_scalar = False
    has_repeated_composite = False
    has_scalar_map = False
    has_message_map = False
    for service_desc in services:
        for method_desc in service_desc.methods:
            if not has_vars:
                has_vars = method_desc.has_vars

            if not method_desc.body_type:
                continue

            type_desc = method_desc.body_type
            if not type_desc and type_desc.repeated:
                continue

            if not has_repeated_scalar:
                has_repeated_scalar = all([type_desc.scalar, type_desc.alias is not None])

            if not has_repeated_composite:
                has_repeated_composite = all([not type_desc.scalar, type_desc.alias is not None])

            if not has_scalar_map:
                has_scalar_map = all([type_desc.scalar, type_desc.map_alias is not None])

            if not has_message_map:
                has_message_map = all([not type_desc.scalar, type_desc.map_alias is not None])

    content = template.execute(
        services=services,
        uses=list(uses),
        has_vars=has_vars,
        has_repeated_scalar=has_repeated_scalar,
        has_repeated_composite=has_repeated_composite,
        has_scalar_map=has_scalar_map,
        has_message_map=has_message_map
    )
    gen.content = content


def build_comment(proto_file: FileDescriptorProto, services: List[ServiceDesc]):
    comment_dict: Dict[any, List[str]] = {}

    for location in proto_file.source_code_info.location:
        path = tuple(location.path)
        if not path:
            continue

        if not path[0] or path[0] != 6:
            continue

        if len(path) != 2 and len(path) != 4:
            continue

        comment: List[str] = []

        def add_paragraph(v: List[str]):
            if len(comment) > 0:
                comment.append('')
                pass
            comment.extend(s.strip() for s in v)

        if location.leading_detached_comments:
            for paragraph in location.leading_detached_comments:
                add_paragraph(paragraph.rstrip('\n').split('\n'))

        tmp_comment: List[str] = []
        if location.leading_comments:
            tmp_comment.append(location.leading_comments)
        if location.trailing_comments:
            tmp_comment.append(location.trailing_comments)

        if len(tmp_comment) > 0:
            add_paragraph(tmp_comment)

        if len(comment) > 0:
            comment_dict[path] = comment
        else:
            # 默认注释
            comment_dict[path] = ['Missing associated documentation comment in .proto file.']

    # 设置注释
    for i, service in enumerate(services):
        if (6, i) in comment_dict:
            service.comment = comment_dict[(6, i)]
        for j, method in enumerate(service.methods):
            if (6, i, 2, j) in comment_dict:
                method.comment = comment_dict[(6, i, 2, j)]


def build_service(proto_file: FileDescriptorProto, pool: DescriptorPool,
                  service: ServiceDescriptorProto) -> ServiceDesc:
    service_desc = ServiceDesc()
    filename = os.path.split(proto_file.name)[-1]
    entity_name = filename[:-len(".proto")]
    service_desc.entity_package = entity_name + "_pb2"
    service_desc.name = service.name
    service_desc.snake_case_name = util.pascal_case_to_snake_case(service_desc.name)
    service_desc.pascal_case_name = util.snake_case_to_pascal_case(service_desc.snake_case_name)
    service_desc.metadata = proto_file.name
    service_desc.comment = ""
    service_desc.methods = []
    service_desc.uses = set()

    for method in service.method:
        method_desc = build_method(pool, method)
        if method_desc is None:
            continue
        service_desc.methods.append(method_desc)

    return service_desc


def build_method(pool: DescriptorPool, m: MethodDescriptorProto) -> Union[MethodDesc, None]:
    http = m.options.Extensions[google.api.annotations_pb2.http]
    if http is {}:
        return None

    assert isinstance(http, HttpRule)

    method_desc = MethodDesc()

    method_desc.name = m.name
    method_desc.snake_case_name = util.pascal_case_to_snake_case(method_desc.name)
    method_desc.pascal_case_name = util.snake_case_to_pascal_case(method_desc.snake_case_name)

    input_type = m.input_type
    if input_type.startswith('.'):
        input_type = input_type[1:]
    output_type = m.output_type
    if output_type.startswith('.'):
        output_type = output_type[1:]

    input_type_name = input_type.split('.')[-1]
    output_type_name = output_type.split('.')[-1]
    method_desc.request = build_message_pool(pool, input_type, input_type_name)
    method_desc.response = build_message_pool(pool, output_type, output_type_name)

    if http.get:
        method = 'get'
        path = http.get
    elif http.delete:
        method = 'delete'
        path = http.delete
    elif http.post:
        method = 'post'
        path = http.post
    elif http.put:
        method = 'put'
        path = http.put
    elif http.patch:
        method = 'patch'
        path = http.patch
    else:
        if http.custom and http.custom.kind:
            method = http.custom.kind
            path = http.custom.path
        else:
            return None

    method_desc.method = method
    method_desc.path = path

    match = re.search(r"\{.*?\}", path)
    method_desc.has_vars = match is not None

    body = http.body
    method_desc.body_type = None
    has_body = False
    if body == '*':
        has_body = True
        method_desc.body = ''
    elif body != '':
        has_body = True
        method_desc.body = body
        method_desc.body_type = build_message_pool(pool, input_type, input_type_name, body)

    response_body = http.response_body
    if response_body is not None and response_body != '':
        method_desc.response_body = response_body
        method_desc.response_body_type = build_message_pool(pool, output_type, output_type_name, response_body)

    method_desc.has_body = has_body

    if http.get or http.delete:
        if has_body:
            raise AttributeError(f'{method} {path} body should not be declared')
    else:
        if not has_body:
            raise AttributeError(f'{method} {path} does not declare a body')

    return method_desc


def build_message_pool(pool: DescriptorPool, symbol: str, type_name: str, field: str = None) -> TypeDesc:
    """
    构建类型描述

    Args:
        pool: 协议缓冲区描述符集合
        symbol: 符号名称  api.helloworld.HelloWorld
        type_name: 类型名称  HelloWorld
        field: 可选 类型中的字段名称
    """
    file_descriptor = pool.FindFileContainingSymbol(symbol)
    assert isinstance(file_descriptor, FileDescriptor)
    message_descriptor = file_descriptor.message_types_by_name[type_name]
    assert isinstance(message_descriptor, Descriptor)

    if field and field != '':
        # 获取的是message类型声明中的字段，并不是message本身
        field_descriptor = message_descriptor.fields_by_name[field]
        assert isinstance(field_descriptor, FieldDescriptor)
        return build_field(field_descriptor)

    file_descriptor = message_descriptor.file
    assert isinstance(file_descriptor, FileDescriptor)

    return build_message(file_descriptor, message_descriptor)


def build_message(file_descriptor: FileDescriptor, message_descriptor: Descriptor) -> TypeDesc:
    type_desc = TypeDesc()
    type_desc.scalar = False
    type_desc.repeated = False

    package = file_descriptor.package
    file_path = file_descriptor.name

    file_name = os.path.basename(file_path)
    file_name_without_extension = os.path.splitext(file_name)[0]

    type_name = message_descriptor.name
    type_desc.name = type_name

    package_alias = util.build_alias(f'{package}.{file_name_without_extension}_pb2')
    alias = f'{package_alias}.{type_name}'
    type_desc.alias = alias

    use = f'from {package} import {file_name_without_extension}_pb2 as {package_alias}'
    type_desc.use = use

    return type_desc


def build_field(field_descriptor: FieldDescriptor) -> TypeDesc:
    if field_descriptor.type not in [FieldDescriptor.TYPE_MESSAGE, FieldDescriptor.TYPE_ENUM]:
        return build_scalar(field_descriptor)

    message_descriptor = field_descriptor.message_type
    assert isinstance(message_descriptor, Descriptor)

    type_desc = TypeDesc()
    type_desc.name = message_descriptor.name

    scalar = False
    repeated = field_descriptor.label == FieldDescriptor.LABEL_REPEATED

    key_field = None
    value_field = None
    if 'key' in message_descriptor.fields_by_name and 'value' in message_descriptor.fields_by_name:
        key_field = message_descriptor.fields_by_name['key']
        value_field = message_descriptor.fields_by_name['value']

    if key_field and value_field:
        # 是map的字段声明
        assert isinstance(key_field, FieldDescriptor)
        assert isinstance(value_field, FieldDescriptor)
        # map的key必须为"bool | int | str"
        key_type_desc = build_scalar(key_field)
        # map的value可以为任意类型
        if value_field.type in [FieldDescriptor.TYPE_MESSAGE, FieldDescriptor.TYPE_ENUM]:
            value_type_desc = build_field(value_field)
        else:
            value_type_desc = build_scalar(value_field)

        type_desc.map_alias = (key_type_desc.alias, value_type_desc.alias)
        type_desc.use = value_type_desc.use
        scalar = value_type_desc.scalar

    else:
        file_descriptor = message_descriptor.file
        assert isinstance(file_descriptor, FileDescriptor)
        value_type_desc = build_message(file_descriptor, message_descriptor)
        type_desc.name = value_type_desc.name
        type_desc.alias = value_type_desc.alias
        type_desc.use = value_type_desc.use

    type_desc.scalar = scalar
    type_desc.repeated = repeated

    return type_desc


def build_scalar(field_descriptor: FieldDescriptor) -> TypeDesc:
    type_desc = TypeDesc()
    type_desc.scalar = True
    repeated = field_descriptor.label == FieldDescriptor.LABEL_REPEATED
    type_desc.repeated = repeated

    # 基础类型
    type_name = 'object'
    if field_descriptor.type == FieldDescriptor.TYPE_BOOL:
        type_name = 'bool'
    elif field_descriptor.type == FieldDescriptor.TYPE_STRING:
        type_name = 'str'
    elif field_descriptor.type == FieldDescriptor.TYPE_BYTES:
        type_name = 'bytes'
    elif field_descriptor.type in [FieldDescriptor.TYPE_DOUBLE, FieldDescriptor.TYPE_FLOAT]:
        type_name = 'float'
    elif field_descriptor.type in [
        FieldDescriptor.TYPE_INT64,
        FieldDescriptor.TYPE_UINT64,
        FieldDescriptor.TYPE_INT32,
        FieldDescriptor.TYPE_FIXED64,
        FieldDescriptor.TYPE_FIXED32,
        FieldDescriptor.TYPE_UINT32,
        FieldDescriptor.TYPE_SFIXED32,
        FieldDescriptor.TYPE_SFIXED64,
        FieldDescriptor.TYPE_SINT32,
        FieldDescriptor.TYPE_SINT64,
    ]:
        type_name = 'int'

    type_desc.name = type_name
    type_desc.alias = type_name
    return type_desc
