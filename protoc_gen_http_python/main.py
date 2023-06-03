import os
import sys
import google.protobuf.compiler.plugin_pb2 as plugin
from google.protobuf.descriptor_pool import DescriptorPool

if __package__ is None and not hasattr(sys, "frozen"):
    path = os.path.realpath(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))
from protoc_gen_http_python import http

__version__ = "0.0.3"


def main() -> None:
    request = plugin.CodeGeneratorRequest.FromString(sys.stdin.buffer.read())

    response = plugin.CodeGeneratorResponse()
    response.supported_features = plugin.CodeGeneratorResponse.FEATURE_PROTO3_OPTIONAL

    pool = DescriptorPool()
    for proto in request.proto_file:
        pool.Add(proto)

    gen = response.file.add()

    for proto_file in request.proto_file:
        http.generate_file(proto_file, pool, gen)

    sys.stdout.buffer.write(response.SerializeToString())


if __name__ == "__main__":
    main()

