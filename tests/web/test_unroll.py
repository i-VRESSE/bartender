from bartender.config import (
    ApplicatonConfiguration,
    InteractiveApplicationConfiguration,
)
from bartender.web.unroll import (
    unroll_application_routes,
    unroll_interactive_app_routes,
)


def test_unroll_application_routes_minimal() -> None:
    openapi_schema = {
        "paths": {
            "/api/application/{application}": {
                "put": {
                    "responses": "mock responses",
                    "security": "mock security",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "$ref": "#/components/schemas/JobDescription",
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "JobDescription": "mock JobDescription",
            },
        },
    }
    applications = {
        "app1": ApplicatonConfiguration(command_template="uptime"),
    }

    unroll_application_routes(openapi_schema, applications)

    expected_request_body = {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "properties": {
                        "upload": {
                            "type": "string",
                            "format": "binary",
                            "title": "Upload",
                            "description": "Zip archive.",
                        },
                    },
                    "type": "object",
                    "required": ["upload"],
                    "title": "Upload app1",
                    "additionalProperties": False,
                },
                "encoding": {
                    "upload": {
                        "contentType": "application/zip, application/x-zip-compressed",
                    },
                },
            },
        },
        "required": True,
    }
    expected = {
        "paths": {
            "/api/application/app1": {
                "put": {
                    "tags": ["application"],
                    "operationId": "application_app1",
                    "summary": "Upload job to app1",
                    "requestBody": expected_request_body,
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
        "components": {
            "schemas": {},
        },
    }
    assert openapi_schema == expected


def test_unroll_application_routes_maximum() -> None:
    openapi_schema = {
        "paths": {
            "/api/application/{application}": {
                "put": {
                    "responses": "mock responses",
                    "security": "mock security",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "$ref": "#/components/schemas/JobDescription",
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "JobDescription": "mock JobDescription",
            },
        },
    }
    applications = {
        "app1": ApplicatonConfiguration(
            command_template="echo",
            upload_needs=["file1.txt", "file2.txt"],
            summary="Run app1",
            description="App1 description",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo.",
                    },
                },
                "required": ["message"],
                "additionalProperties": False,
            },
        ),
    }

    unroll_application_routes(openapi_schema, applications)

    desc = "Zip archive containing somerequiredfile.txt, file2.txt file(s)."
    expected_request_body = {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "properties": {
                        "upload": {
                            "type": "string",
                            "format": "binary",
                            "title": "Upload",
                            "description": desc,
                        },
                        "message": {
                            "type": "string",
                            "description": "Message to echo.",
                        },
                    },
                    "type": "object",
                    "required": ["upload", "message"],
                    "title": "Upload app1",
                    "additionalProperties": False,
                },
                "encoding": {
                    "upload": {
                        "contentType": "application/zip, application/x-zip-compressed",
                    },
                },
            },
        },
        "required": True,
    }
    expected = {
        "paths": {
            "/api/application/app1": {
                "put": {
                    "tags": ["application"],
                    "operationId": "application_app1",
                    "summary": "Run app1",
                    "description": "App1 description",
                    "requestBody": expected_request_body,
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
        "components": {
            "schemas": {},
        },
    }
    assert openapi_schema == expected


def test_unroll_interactive_app_routes() -> None:
    openapi_schema = {
        "paths": {
            "/api/job/{jobid}/interactive/{application}": {
                "post": {
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
    }
    input_schema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    interactive_applications = {
        "iapp1": InteractiveApplicationConfiguration(
            command_template="echo {{ message }}",
            input_schema=input_schema,
        ),
    }

    unroll_interactive_app_routes(openapi_schema, interactive_applications)

    expected = {
        "paths": {
            "/api/job/{jobid}/interactive/iapp1": {
                "post": {
                    "tags": ["interactive"],
                    "operationId": "interactive_application_iapp1",
                    "summary": "Run iapp1 interactive application",
                    "parameters": [
                        {
                            "name": "jobid",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "number"},
                        },
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": input_schema,
                            },
                        },
                    },
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
    }
    assert openapi_schema == expected
