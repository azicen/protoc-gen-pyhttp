import os
from typing import List, Dict

import google.api.annotations_pb2
from google.protobuf.compiler.plugin_pb2 import CodeGeneratorResponse
from google.protobuf.descriptor_pb2 import FileDescriptorProto, ServiceDescriptorProto, MethodDescriptorProto
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.descriptor import FileDescriptor
from google.api.http_pb2 import HttpRule

from protoc_gen_http_python import template, util
from protoc_gen_http_python.template import ServiceDesc, MethodDesc, TypeDesc


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
    for service in services:
        for use in service.uses:
            uses.add(use)

    content = template.execute(services=services, uses=list(uses))
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
        if location.leading_comments:
            add_paragraph([location.leading_comments])
        if location.trailing_comments:
            add_paragraph([location.trailing_comments])

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
    service_desc.snake_case_name = util.pascal_case_to_snake_case(service.name)
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

    for method_desc in service_desc.methods:
        service_desc.uses.add(method_desc.request.use)
        service_desc.uses.add(method_desc.reply.use)
        if method_desc.body_type is not None:
            service_desc.uses.add(method_desc.body_type.use)

    # if len(service_desc.methods) > 0:
    #     s = {tuple(location.path): location for location in proto_file.source_code_info.location}
    #     raise AttributeError(f'{s}')

    return service_desc


def build_method(pool: DescriptorPool, m: MethodDescriptorProto) -> MethodDesc | None:
    http = m.options.Extensions[google.api.annotations_pb2.http]
    if http is {}:
        return None

    assert isinstance(http, HttpRule)

    method_desc = MethodDesc()

    method_desc.snake_case_name = util.pascal_case_to_snake_case(m.name)
    method_desc.pascal_case_name = util.snake_case_to_pascal_case(method_desc.snake_case_name)

    input_type = m.input_type
    if input_type.startswith('.'):
        input_type = input_type[1:]
    output_type = m.output_type
    if output_type.startswith('.'):
        output_type = output_type[1:]

    method_desc.request = build_type(pool, input_type)
    method_desc.reply = build_type(pool, output_type)

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
            # raise AttributeError(f'no http type in method {m.name}')

    method_desc.method = method
    method_desc.path = path

    body = http.body
    method_desc.body_type = None
    has_body = False
    if body == '*':
        has_body = True
        method_desc.body = ''
    elif body != '':
        has_body = True
        method_desc.body = util.pascal_case_to_snake_case(body)
        method_desc.body_type = build_type(pool, body)

    method_desc.has_body = has_body

    if http.get or http.delete:
        if has_body:
            raise AttributeError(f'{method} {path} body should not be declared')
    else:
        if not has_body:
            raise AttributeError(f'{method} {path} does not declare a body')


    return method_desc


def build_type(pool: DescriptorPool, type_full_name: str) -> TypeDesc:
    file_descriptor = pool.FindFileContainingSymbol(type_full_name)
    assert isinstance(file_descriptor, FileDescriptor)

    type_desc = TypeDesc()

    package = file_descriptor.package
    file_path = file_descriptor.name

    file_name = os.path.basename(file_path)
    file_name_without_extension = os.path.splitext(file_name)[0]

    type_name = type_full_name.rsplit(".", 1)[-1]

    type_desc.snake_case_name = util.pascal_case_to_snake_case(type_name)
    type_desc.pascal_case_name = util.snake_case_to_pascal_case(type_desc.snake_case_name)

    package_alias = util.build_alias(f'{package}.{file_name_without_extension}_pb2')
    alias = f'{package_alias}.{type_desc.pascal_case_name}'
    type_desc.alias = alias

    use = f'from {package} import {file_name_without_extension}_pb2 as {package_alias}'
    type_desc.use = use

    return type_desc
