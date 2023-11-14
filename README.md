# protoc-gen-pyhttp

一个用于快速将`.proto`构建为Python使用的`HTTP Api`工具


## 使用

### 使用PyPI安装
#### 安装protoc-gen-pyhttp
```shell
pip install protoc-gen-pyhttp
```

#### 安装可能需要使用的其他软件包
```shell
pip install protobuf \
            types-protobuf \
            googleapis-common-protos \
            googleapis-common-protos-stubs \
            grpcio-tools
```
构建`HTTP Api`需要使用到`protoc`工具，该工具由`grpcio-tools`包提供（您也可以使用[protobuf](https://github.com/protocolbuffers/protobuf)的可执行文件替代这个包），同时需要使用到将`.proto`文件构建为Python类型的功能，`protobuf`、`types-protobuf`、`googleapis-common-protos`、`googleapis-common-protos-stubs`这些软件包提供了这个功能。

### 将proto文件构建为HTTP Api
```shell
protoc --proto_path=./proto \
       --python_out=. \
       --pyi_out=. \
       --pyhttp_out=. \
       you_proto_file_list...
```
使用`--proto_path`设置proto文件所在的路径，该参数可以有多个；使用`--python_out`设置构建Python类型的存放路径；使用`--pyi_out`设置构建用于IDE工具识别Python文件的存放路径；使用`--pyhttp_out`设置构建`HTTP Api`的存放路径。

