import base64
import json

import httpx


def get_json(response):
    tokens = response.text.split()
    for i, token in enumerate(tokens):
        if token == "window.formDefinition":
            unparsed = tokens[i + 2]
            break
    return json.loads(base64.b64decode(unparsed.split('"')[1]))


def form_mapping(form_definition_json):
    mapping = {}
    for component in form_definition_json["components"]:
        if component.get("options") and not component.get("hidden"):
            label = component.get("label")
            options = [opt["value"] for opt in component.get("options")]
            mapping[label] = options
    return mapping


r = httpx.get("https://app.smartsheet.com/b/form/463e9faa2a644f4fae2a956f331f451c")
form_definition_json = get_json(r)
form_mapping_json = form_mapping(form_definition_json)

print(json.dumps(form_mapping_json))
