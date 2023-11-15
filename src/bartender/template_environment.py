from shlex import quote

from jinja2 import Environment

template_environment = (
    Environment(  # noqa: S701 -- used to generate shell commands not HTML
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
)
# TODO find way to always quote variables without having to use q filter
template_environment.filters["q"] = lambda variable: quote(str(variable))
