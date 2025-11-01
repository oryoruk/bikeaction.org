from django import template
from django.db.models import Model
from django.template.defaultfilters import urlencode
from django.utils.safestring import mark_safe

register = template.Library()


TWITTER_ENDPOINT = "https://twitter.com/intent/tweet?text=%s"
BLUESKY_ENDPOINT = "https://bsky.app/intent/compose?text=%s"
REDDIT_ENDPOINT = "https://www.reddit.com/submit?title=%s&url=%s"


def compile_text(context, text):
    ctx = template.context.Context(context)
    return template.Template(text).render(ctx)


def _build_url(request, obj_or_url):
    if obj_or_url is not None:
        if isinstance(obj_or_url, Model):
            return request.build_absolute_uri(obj_or_url.get_absolute_url())
        else:
            return request.build_absolute_uri(obj_or_url)
    return ""


def _compose_tweet(text, url=None):
    TWITTER_MAX_NUMBER_OF_CHARACTERS = 140
    # "A URL of any length will be altered to 23 characters,
    # even if the link itself is less than 23 characters long.
    TWITTER_LINK_LENGTH = 23

    # Compute length of the tweet
    url_length = len(" ") + TWITTER_LINK_LENGTH if url else 0
    total_length = len(text) + url_length

    # Check that the text respects the max number of characters for a tweet
    if total_length > TWITTER_MAX_NUMBER_OF_CHARACTERS:
        text = text[: (TWITTER_MAX_NUMBER_OF_CHARACTERS - url_length - 1)] + "…"  # len("…") == 1

    return "%s %s" % (text, url) if url else text


@register.simple_tag(takes_context=True)
def post_to_twitter_url(context, text, obj_or_url=None):
    text = compile_text(context, text)
    request = context["request"]

    url = _build_url(request, obj_or_url)

    tweet = _compose_tweet(text, url)
    context["tweet_url"] = TWITTER_ENDPOINT % urlencode(tweet)
    return context


@register.inclusion_tag("templatetags/post_to_twitter.html", takes_context=True)
def post_to_twitter(context, text, obj_or_url=None, link_text="", link_class=""):
    context = post_to_twitter_url(context, text, obj_or_url)

    request = context["request"]
    url = _build_url(request, obj_or_url)
    tweet = _compose_tweet(text, url)

    context["link_class"] = link_class
    context["link_text"] = link_text or "Post to Twitter"
    context["full_text"] = tweet
    return context


@register.simple_tag(takes_context=True)
def post_to_bluesky_url(context, text, obj_or_url=None):
    text = compile_text(context, text)
    request = context["request"]

    url = _build_url(request, obj_or_url)

    skeet = _compose_tweet(text, url)
    context["skeet_url"] = BLUESKY_ENDPOINT % urlencode(skeet)
    return context


@register.inclusion_tag("templatetags/post_to_bluesky.html", takes_context=True)
def post_to_bluesky(context, text, obj_or_url=None, link_text="", link_class=""):
    context = post_to_bluesky_url(context, text, obj_or_url)

    request = context["request"]
    url = _build_url(request, obj_or_url)
    skeet = _compose_tweet(text, url)

    context["link_class"] = link_class
    context["link_text"] = link_text or "Post to Blusky"
    context["full_text"] = skeet
    return context


@register.simple_tag(takes_context=True)
def post_to_reddit_url(context, title, obj_or_url=None):
    request = context["request"]
    title = compile_text(context, title)
    url = _build_url(request, obj_or_url)
    context["reddit_url"] = mark_safe(REDDIT_ENDPOINT % (urlencode(title), urlencode(url)))
    return context


@register.inclusion_tag("templatetags/post_to_reddit.html", takes_context=True)
def post_to_reddit(context, title, obj_or_url=None, link_text="", link_class=""):
    context = post_to_reddit_url(context, title, obj_or_url)
    context["link_class"] = link_class
    context["link_text"] = link_text or "Post to Reddit"
    return context


@register.simple_tag(takes_context=True)
def copy_to_clipboard_url(context, obj_or_url=None):
    request = context["request"]
    url = _build_url(request, obj_or_url)
    context["copy_url"] = url
    return context


@register.inclusion_tag("templatetags/copy_to_clipboard.html", takes_context=True)
def copy_to_clipboard(context, obj_or_url, link_text="", link_class=""):
    context = copy_to_clipboard_url(context, obj_or_url)

    context["link_class"] = link_class
    context["link_text"] = link_text or "Copy to clipboard"
    return context


@register.inclusion_tag("templatetags/copy_script.html", takes_context=False)
def add_copy_script():
    pass
