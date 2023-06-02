def pascal_case_to_snake_case(v: str) -> str:
    """将大驼峰转换为蛇形"""
    snake_case_name = ""
    for i, char in enumerate(v):
        if i > 0 and char.isupper():
            snake_case_name += "_"
        snake_case_name += char.lower()

    return snake_case_name


def snake_case_to_pascal_case(v: str) -> str:
    """将蛇形转换为大驼峰"""
    words = v.split("_")
    pascal_case_name = "".join(word.capitalize() for word in words)
    return pascal_case_name


def build_alias(v: str) -> str:
    """将'.'连接的字符串转换为引入时使用的别名"""
    v = v.replace("_", "__")
    v = v.replace(".", "_dot_")
    return v
