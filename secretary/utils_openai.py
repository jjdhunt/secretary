"""
Utilities for using OpenAI Chat API.
- Includes tools for creating conversation histories, getting chat completions, and tool calling.
"""

from dotenv import load_dotenv
import numpy as np
from openai import OpenAI
from typing import Literal, Optional

load_dotenv()

openai_client_global = OpenAI() # Defaults to api_keu = os.environ.get("OPENAI_API_KEY")

### Embeddings ###

def get_embedding(content):
    response = openai_client_global.embeddings.create(input=content,
                                                      model="text-embedding-3-small")
    embedding = np.array(response.data[0].embedding)
    return embedding

### Chats ###

class Messages():

    def __init__(self):
        self.messages = []

    def clear(self):
        self.messages = []

    def keep_last(self, n: int):
        """Drop all but the last n messages."""
        self.messages = self.messages[-n:]

    def add_message(self, role: Literal['user', 'assistant'], message: str):
        message = {"role": role, "content": message}
        self.messages.append(message)

def get_completion(comment, system_message, model_class='best', tools=None, temperature=0):

    models = {'fast': 'gpt-4o-mini',
              'best': 'gpt-4o'}

    completion = openai_client_global.chat.completions.create(
                                                model=models[model_class],
                                                temperature=temperature,
                                                tools=tools,
                                                messages=[
                                                    {"role": "system", "content": system_message},
                                                    {"role": "user", "content": comment}
                                                ],
                                                )
    return completion.choices[0].message.content, completion.choices[0].message.tool_calls

def get_conversation_completion(messages, model_class='best', tools=None, temperature=0):

    models = {'fast': 'gpt-4o-mini',
              'best': 'gpt-4o'}

    completion = openai_client_global.chat.completions.create(
                                                model=models[model_class],
                                                temperature=temperature,
                                                tools=tools,
                                                messages=messages,
                                                )
    return completion.choices[0].message.content, completion.choices[0].message.tool_calls

def _strip_special(s:str, prefixes:Optional[list[str]]=[], suffixes:Optional[list[str]]=[]) -> str:
    for prefix in prefixes:
        if s.startswith(prefix):
            s = s[len(prefix):]
    for suffix in suffixes:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

def clean_response_json(json_str):
    # Clean up the json string. Gpt can add unwanted decorators and things.
    prefixes = ["```json"]
    suffixes = ["```"]
    json_str = _strip_special(json_str, prefixes, suffixes)
    return json_str

### Tool calling ###

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
        
def add_function_to_tools(tools, func):
    """
    This will put the function callable and a tool-schema suitable for providing to the OpenAI Chat API
    into the provided tools dict.

    The idea for this came from https://community.openai.com/t/tool-calls-does-the-schema-matter/859354/2
    """
    tool = {
        'schema': schematize_function(func),
        'callable': func
    }
    tools[func.__name__] = tool
    return tools