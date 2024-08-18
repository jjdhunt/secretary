FUNCTIONS_TYPE_MAP = {
    # there are the types for JSON: https://json-schema.org/understanding-json-schema/reference/type
    'list': 'array',
    'dict': 'object',
    'int': 'integer',
    'float': 'number',
    'str': 'string',
    'bool': 'boolean',
    'None': 'null',
}

def schematize_function(func):
    function = {}
    function['name'] = func.__name__
    function['description'] = func.__doc__.strip()
    function['parameters'] = {}
    function['parameters']['type'] = "object"
    function['parameters']['properties'] = {}
    function['parameters']['required'] = []

    input_arg_names = [arg_name for arg_name in func.__code__.co_varnames[:func.__code__.co_argcount]]
    for input_arg_name in input_arg_names:
        function['parameters']['required'].append(input_arg_name) # all arguments are required. could change this
        function['parameters']['properties'][input_arg_name] = {}
        raw_annotation = func.__annotations__[input_arg_name]

        if raw_annotation.__origin__.__name__ in FUNCTIONS_TYPE_MAP:
            ip_type = FUNCTIONS_TYPE_MAP[raw_annotation.__origin__.__name__]
            function['parameters']['properties'][input_arg_name]['type'] = ip_type

            if ip_type == 'array':
                function['parameters']['properties'][input_arg_name]['items'] = {}
                ip_item_type = raw_annotation.__origin__.__args__[0].__name__
                if ip_item_type in FUNCTIONS_TYPE_MAP:
                    function['parameters']['properties'][input_arg_name]['items']['type'] = FUNCTIONS_TYPE_MAP[ip_item_type]
                else:
                    function['parameters']['properties'][input_arg_name]['items']['type'] = ip_item_type

        else:
            ip_type =  raw_annotation.__origin__.__name__
            function['parameters']['properties'][input_arg_name]['type'] = ip_type


        function['parameters']['properties'][input_arg_name]['type'] = ip_type
        function['parameters']['properties'][input_arg_name]['description'] = raw_annotation.__metadata__[0]

    tool = {}
    tool['type'] = 'function'
    tool['function'] = function
    return tool
        
    
def tools_function(tools):
    # From https://community.openai.com/t/tool-calls-does-the-schema-matter/859354/2
    def wrapper(func):
        tool = {}
        tool['schema'] = schematize_function(func)
        tool['callable'] = func
        tools[func.__name__] = tool
        return func
    return wrapper