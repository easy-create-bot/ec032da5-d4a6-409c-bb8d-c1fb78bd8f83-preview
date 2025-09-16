from tree_sitter_language_pack import get_parser
# These return fully initialized Parser instances
JS_PARSER = get_parser("javascript")
TS_PARSER = get_parser("typescript")
TSX_PARSER = get_parser("tsx")

EXT_PARSER_MAP = {
    "js": JS_PARSER,
    "jsx": JS_PARSER,
    "ts": TS_PARSER,
    "tsx": TSX_PARSER,
}

def parse_file_str(code_str: str, file_extension: str):
    print(f"Parsing file with extension: {file_extension}")
    """
    Parse code from a string and extract all function, class, and variable declarations recursively.
    Returns a list of declarations with their metadata.
    """
    parser = EXT_PARSER_MAP.get(file_extension.lower())
    if not parser:
        raise ValueError(f"Unsupported file extension: {file_extension}")

    code_bytes = code_str.encode("utf8")
    tree = parser.parse(code_bytes)

    # Map byte offsets to line numbers
    line_offsets = [0]
    for i, c in enumerate(code_bytes):
        if c == ord(b'\n'):
            line_offsets.append(i + 1)

    def byte_to_line(byte_offset):
        for idx, offset in enumerate(line_offsets):
            if offset > byte_offset:
                return idx
        return len(line_offsets)

    declarations = []

    def walk(node):
        if node.type in (
            "jsx_element",
            "jsx_self_closing_element",
            "function_declaration",
            "arrow_function",
            "method_definition",
            "class_declaration",
            "variable_declaration",
            "lexical_declaration"
        ):
            name = ""
            if node.type in ("jsx_element", "jsx_self_closing_element"):
                if node.type == "jsx_element":
                    opening = node.child_by_field_name("opening_element")
                    if opening and opening.named_child_count:
                        tag_node = opening.named_children[0]
                        if tag_node:
                            name = tag_node.text.decode()
            if node.type in ("function_declaration", "class_declaration"):
                id_node = node.child_by_field_name("name")
                if id_node:
                    name = id_node.text.decode()
            elif node.type in ("variable_declaration", "lexical_declaration"):
                declarator = node.child_by_field_name("declarator")
                if declarator is None and node.named_children:
                    declarator = node.named_children[0]
                if declarator:
                    name_node = declarator.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode()
                    else:
                        name = declarator.text.decode()
            elif node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = name_node.text.decode()
            elif node.type == "arrow_function":
                parent = node.parent
                if parent and parent.type == "variable_declarator":
                    id_node = parent.child_by_field_name("name")
                    if id_node:
                        name = id_node.text.decode()

            declarations.append({
                "type": node.type,
                "name": name,
                "start_line": byte_to_line(node.start_byte),
                "end_line": byte_to_line(node.end_byte),
                "code": code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")
            })

        # Recursively process children
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return declarations

