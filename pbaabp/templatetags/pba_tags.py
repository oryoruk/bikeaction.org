from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def clean_url(context, path):
    request = context["request"]
    return request.build_absolute_uri(path)


@register.filter(name="splitlines")
def splitlines_filter(value):
    return value.splitlines()
