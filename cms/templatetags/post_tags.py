from django import template

register = template.Library()


@register.simple_tag()
def post_url(post_page):
    return post_page.canonical_url()
