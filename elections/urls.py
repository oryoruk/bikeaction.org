from django.urls import path

from elections import views

urlpatterns = [
    # Public election pages
    path("", views.election_list, name="election_list"),
    # Nominee search (HTMX endpoint) - must come before election_slug pattern
    path("nominee-search/", views.nominee_search, name="nominee_search"),
    path("<slug:election_slug>/", views.election_detail, name="election_detail"),
    path("<slug:election_slug>/nominees/", views.election_nominees, name="election_nominees"),
    path(
        "<slug:election_slug>/nominees/<slug:nominee_slug>/",
        views.nominee_detail,
        name="nominee_detail",
    ),
    # Nomination management (accessed via profile links)
    path(
        "<slug:election_slug>/nominate/",
        views.nomination_form,
        name="nomination_form",
    ),
    path(
        "<slug:election_slug>/nominate/<uuid:pk>/edit/",
        views.nomination_form,
        name="nomination_edit",
    ),
    path(
        "<slug:election_slug>/nominations/<uuid:pk>/respond/",
        views.nomination_respond,
        name="nomination_respond",
    ),
    # Public nomination view
    path(
        "<slug:election_slug>/nominations/<uuid:pk>/",
        views.nomination_view,
        name="nomination_view",
    ),
    # Nominee profile management
    path(
        "<slug:election_slug>/nominee/<uuid:nominee_id>/profile/edit/",
        views.nominee_profile_edit,
        name="nominee_profile_edit",
    ),
]
