import os
import sys

from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pool import DescriptorPool

if __package__ is None and not hasattr(sys, "frozen"):
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))
from protoc_gen_pyhttp import http

__version__ = "1.0.0rc2"


def main():
    request = plugin.CodeGeneratorRequest.FromString(sys.stdin.buffer.read())

    pool = DescriptorPool()
    for proto in request.proto_file:
        pool.Add(proto)

    for proto_file in request.proto_file:
        response = plugin.CodeGeneratorResponse()
        response.supported_features = plugin.CodeGeneratorResponse.FEATURE_PROTO3_OPTIONAL

        gen = response.file.add()
        http.generate_file(proto_file, pool, gen)

        sys.stdout.buffer.write(response.SerializeToString())


if __name__ == "__main__":
    main()
