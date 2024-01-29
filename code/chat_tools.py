tools = [
    {
        "type": "function",
        "function": {
            "name": "set_item_completion",
            "description": "set one or more items as completed or not completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_index": {
                        "type": "integer",
                        "description": "The index of the item that the user has indicated is completed or not completed, if any.",
                    },
                    "completion": {
                        "type": "boolean",
                        "description": "True if the user has indicated the item is done, or false if they have indicated it is not done.",
                    },
                },
                "required": [],
            },
        }
    },
]