"""Methods to rewrite the OpenAPI schema generated by FastAPI."""
from typing import Any

from fastapi import FastAPI

from bartender.config import (
    ApplicatonConfiguration,
    ApplicatonConfigurations,
    InteractiveApplicationConfigurations,
)


def unroll_openapi(app: FastAPI) -> None:
    """Convert dynamic application routes to static routes.

    Args:
        app: FastAPI app

    Raises:
        RuntimeError: If OpenAPI schema is not generated.
    """
    # If the schema has already been generated, don't do it again
    if not app.openapi_schema:
        app.openapi()
        if app.openapi_schema is None:
            raise RuntimeError(
                "OpenAPI schema should be generated at this point",
            )
        unroll_application_routes(app.openapi_schema, app.state.config.applications)
        unroll_interactive_app_routes(
            app.openapi_schema,
            app.state.config.interactive_applications,
        )


def unroll_application_routes(
    openapi_schema: dict[str, Any],
    applications: ApplicatonConfigurations,
) -> None:
    """Unroll application routes.

    In openapi spec replaces `/api/application/{application}`
    with paths without `{application}`.
    Loops over config.applications and adds a put route for each.

    Args:
        openapi_schema: OpenAPI schema
        applications: Application configurations
    """
    existing_put_path = openapi_schema["paths"].pop(
        "/api/application/{application}",
    )["put"]

    for aname, config in applications.items():
        # each application has different request due to config file
        # so instead of reusing the same schema for all applications
        # we need to generate a new one for each application
        openapi_schema["paths"][f"/api/application/{aname}"] = {
            "put": unroll_application_route(aname, config, existing_put_path),
        }

    # Drop schema for /api/application/{application} put request
    # as it is no longer used
    ref = existing_put_path["requestBody"]["content"][  # noqa: WPS219
        "multipart/form-data"
    ]["schema"]["$ref"]
    del openapi_schema["components"]["schemas"][  # noqa: WPS420
        ref.replace("#/components/schemas/", "")
    ]


def unroll_application_route(
    aname: str,
    config: ApplicatonConfiguration,
    existing_put_path: Any,
) -> dict[str, Any]:
    """Unroll an application route.

    Args:
        aname: Application name
        config: Application configuration
        existing_put_path: Existing PUT path

    Returns:
        Unrolled PUT path
    """
    schema = unroll_application_request_schema(aname, config)

    request_body = {
        "content": {
            "multipart/form-data": {
                "schema": schema,
                # Enfore uploaded file is a certain content type
                # See https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.0.3.md#encoding-object  # noqa: E501
                # does not seem supported by Swagger UI or FastAPI or generated clients
                "encoding": {
                    "upload": {
                        "contentType": "application/zip, application/x-zip-compressed",
                    },
                },
            },
        },
        "required": True,
    }
    route = {
        "tags": ["application"],
        "operationId": f"application_{aname}",
        "summary": f"Upload job to {aname}",
        "requestBody": request_body,
        "responses": existing_put_path["responses"],
        "security": existing_put_path["security"],
    }
    if config.summary is not None:
        route["summary"] = config.summary

    if config.description is not None:
        route["description"] = config.description

    return route


def unroll_application_request_schema(
    aname: str,
    config: ApplicatonConfiguration,
) -> dict[str, Any]:
    """
    Generate the request schema for unrolling an application.

    Args:
        aname: The name of the application.
        config: The configuration for the application.

    Returns:
        The generated request schema.
    """
    desc = "Zip archive."
    if config.upload_needs:
        needed_files = ", ".join(config.upload_needs)
        desc = f"Zip archive containing {needed_files} file(s)."
    properties = {
        "upload": {
            "type": "string",
            "format": "binary",
            "title": "Upload",
            "description": desc,
        },
    }
    required = ["upload"]
    if config.input_schema is not None:
        properties.update(config.input_schema.get("properties", {}))
        required.extend(config.input_schema.get("required", []))
    return {
        "type": "object",
        "title": f"Upload {aname}",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def unroll_interactive_app_routes(
    openapi_schema: dict[str, Any],
    interactive_applications: InteractiveApplicationConfigurations,
) -> None:
    """Unroll interactive app routes.

    Replaces `/api/job/{jobid}/interactive/{application}`
    with paths without `{application}`.
    Loops over config.interactive_applications and adds a post route for each.

    Args:
        openapi_schema: OpenAPI schema
        interactive_applications: Interactive application configurations
    """
    path = "/api/job/{jobid}/interactive/{application}"
    existing_post_path = openapi_schema["paths"].pop(path)["post"]
    for iname, config in interactive_applications.items():
        path = f"/api/job/{{jobid}}/interactive/{iname}"
        post = {
            "tags": ["interactive"],
            "operationId": f"interactive_application_{iname}",
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
                        "schema": config.input_schema,
                    },
                },
            },
            "responses": existing_post_path["responses"],
            "security": existing_post_path["security"],
        }
        if config.summary is not None:
            post["summary"] = config.summary
        else:
            post["summary"] = f"Run {iname} interactive application"
        if config.description is not None:
            post["description"] = config.description
        openapi_schema["paths"][path] = {"post": post}