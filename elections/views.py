from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from elections.forms import NominationForm, NomineeProfileForm
from elections.models import Election, Nomination, Nominee, get_user_display_name


@login_required
def nomination_form(request, election_slug, pk=None):
    """Create or edit a nomination for an election."""
    election = get_object_or_404(Election, slug=election_slug)

    # Check if user profile is complete
    if not request.user.profile.complete:
        messages.error(
            request,
            "Your profile must be complete to submit a nomination. Please complete your profile.",
        )
        return redirect("profile")

    # Check if user was a member in good standing at the cutoff
    eligibility = request.user.profile.eligible_as_of(election.membership_eligibility_deadline)
    if not eligibility["eligible"]:
        messages.error(
            request,
            f"You must have been a member in good standing as of "
            f"{election.membership_eligibility_deadline.strftime('%B %d, %Y')} "
            f"to submit nominations.",
        )
        return redirect("election_detail", election_slug=election.slug)

    # Check if nominations are open
    if not election.is_nominations_open():
        if timezone.now() < election.nominations_open:
            messages.error(request, "Nominations are not yet open for this election.")
        else:
            messages.error(request, "Nominations have closed for this election.")
        return redirect("election_detail", election_slug=election.slug)

    # If editing, load the existing nomination
    nomination = None
    if pk:
        nomination = get_object_or_404(
            Nomination, id=pk, nominator=request.user, nominee__election=election
        )
        # Can only edit drafts or self-nominations (while nominations are still open)
        # Self-nominations can be edited even if accepted
        if not nomination.draft:
            is_self_nomination = nomination.nominator == nomination.nominee.user
            if not is_self_nomination:
                messages.error(request, "You cannot edit a submitted nomination.")
                return redirect("nomination_view", election_slug=election.slug, pk=nomination.id)
            # Self-nominations that are declined (withdrawn) cannot be edited
            if nomination.acceptance_status == Nomination.AcceptanceStatus.DECLINED:
                messages.error(request, "You cannot edit a withdrawn nomination.")
                return redirect("nomination_view", election_slug=election.slug, pk=nomination.id)

    # Handle form submission
    if request.method == "POST":
        form = NominationForm(
            request.POST,
            instance=nomination,
            election=election,
            nominator=request.user,
            nomination_id=nomination.id if nomination else None,
            label_suffix="",
        )

        # Save draft
        if "save-draft" in request.POST:
            # Get nominee user if provided
            nominee_user_id = request.POST.get("nominee")
            nominee_user = None
            if nominee_user_id:
                try:
                    nominee_user = User.objects.get(id=nominee_user_id)
                except (User.DoesNotExist, ValueError):
                    pass

            if not nominee_user:
                messages.error(request, "Please select a nominee before saving draft.")
                return redirect("nomination_form", election_slug=election.slug)

            # Get or create nominee record
            nominee_record, _ = Nominee.objects.get_or_create(election=election, user=nominee_user)

            if nomination:
                nomination.nominee = nominee_record
                nomination.nomination_statement = request.POST.get("nomination_statement", "")
                nomination.save()
            else:
                nomination = Nomination(
                    nominee=nominee_record,
                    nominator=request.user,
                    draft=True,
                    nomination_statement=request.POST.get("nomination_statement", ""),
                )
                nomination.save()
            messages.success(request, "Nomination draft saved.")
            return redirect("profile")

        # Submit nomination
        elif "submit-nomination" in request.POST:
            if form.is_valid():
                nominee_user = form.cleaned_data["nominee"]
                is_self_nomination = nominee_user == request.user

                # Get or create nominee record
                nominee_record, _ = Nominee.objects.get_or_create(
                    election=election, user=nominee_user
                )

                # Check if nominee profile is complete for self-nominations
                if is_self_nomination and not nominee_record.is_profile_complete():
                    # Save as draft first
                    if nomination:
                        nomination.nominee = nominee_record
                        nomination.nomination_statement = form.cleaned_data["nomination_statement"]
                        nomination.draft = True
                        nomination.save()
                    else:
                        nomination = Nomination(
                            nominee=nominee_record,
                            nominator=request.user,
                            draft=True,
                            nomination_statement=form.cleaned_data["nomination_statement"],
                        )
                        nomination.save()

                    messages.info(
                        request,
                        "Please complete your nominee profile before submitting "
                        "your self-nomination.",
                    )
                    profile_url = reverse(
                        "nominee_profile_edit",
                        kwargs={
                            "election_slug": election.slug,
                            "nominee_id": nominee_record.id,
                        },
                    )
                    return redirect(f"{profile_url}?self_nomination_id={nomination.id}")

                if nomination:
                    # Update existing nomination (could be draft or submitted self-nomination)
                    nomination.nominee = nominee_record
                    nomination.nomination_statement = form.cleaned_data["nomination_statement"]
                    nomination.draft = False
                    nomination.save()
                else:
                    # Create new nomination
                    nomination = Nomination(
                        nominee=nominee_record,
                        nominator=request.user,
                        draft=False,
                        nomination_statement=form.cleaned_data["nomination_statement"],
                    )
                    nomination.save()

                display_name = get_user_display_name(nominee_user)
                messages.success(
                    request,
                    (
                        f"Nomination updated for {display_name}!"
                        if pk
                        else f"Nomination submitted for {display_name}!"
                    ),
                )
                return redirect("profile")
    else:
        # Load form with initial data if editing
        if nomination:
            form = NominationForm(
                instance=nomination,
                initial={"nominee": nomination.nominee.user.id},
                election=election,
                nominator=request.user,
                nomination_id=nomination.id,
                label_suffix="",
            )
        else:
            form = NominationForm(election=election, nominator=request.user, label_suffix="")

    return render(
        request,
        "elections/nomination_form.html",
        {"form": form, "election": election, "nomination": nomination},
    )


@login_required
def nomination_view(request, election_slug, pk):
    """View a submitted nomination."""
    election = get_object_or_404(Election, slug=election_slug)
    nomination = get_object_or_404(Nomination, id=pk, nominee__election=election)

    # Only allow viewing if user is the nominator, nominee, or staff
    if not (
        request.user == nomination.nominator
        or request.user == nomination.nominee.user
        or request.user.is_staff
    ):
        messages.error(request, "You do not have permission to view this nomination.")
        return redirect("election_detail", election_slug=election.slug)

    return render(
        request,
        "elections/nomination_view.html",
        {"nomination": nomination, "election": election},
    )


def election_detail(request, election_slug):
    """View election details and nomination status."""
    election = get_object_or_404(Election, slug=election_slug)

    # Get user's nominations if logged in
    user_nominations = []
    if request.user.is_authenticated:
        user_nominations = Nomination.objects.filter(
            nominee__election=election, nominator=request.user
        ).select_related("nominee")

    return render(
        request,
        "elections/election_detail.html",
        {
            "election": election,
            "user_nominations": user_nominations,
            "can_nominate": request.user.is_authenticated and election.is_nominations_open(),
        },
    )


def election_nominees(request, election_slug):
    """Public view of all nominees who have accepted at least one nomination."""
    election = get_object_or_404(Election, slug=election_slug)

    # Don't show nominees until nominations have closed
    if not election.is_nominations_closed():
        messages.info(request, "Nominees will be visible after nominations close.")
        return redirect("election_detail", election_slug=election.slug)

    # Get nominee IDs who have accepted at least one nomination
    nominee_ids = (
        Nominee.objects.filter(
            election=election,
            nominations__acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
            nominations__draft=False,
        )
        .values_list("id", flat=True)
        .distinct()
    )

    # Fetch the nominees in random order
    nominees = (
        Nominee.objects.filter(id__in=nominee_ids)
        .select_related("user", "user__profile")
        .prefetch_related("nominations__nominator")
        .order_by("?")  # Random order
    )

    # Filter to get only accepted nominations for each nominee
    # Sort so self-nominations appear first
    for nominee in nominees:
        accepted = nominee.nominations.filter(
            acceptance_status=Nomination.AcceptanceStatus.ACCEPTED, draft=False
        ).select_related("nominator")

        # Separate self-nominations and other nominations
        self_noms = [n for n in accepted if n.nominator == nominee.user]
        other_noms = [n for n in accepted if n.nominator != nominee.user]

        # Combine with self-nominations first
        nominee.accepted_nominations = self_noms + other_noms

    return render(
        request,
        "elections/election_nominees.html",
        {"election": election, "nominees": nominees},
    )


def nominee_detail(request, election_slug, nominee_slug):
    """Public view of an individual nominee with their nomination statements."""
    election = get_object_or_404(Election, slug=election_slug)

    # Don't show nominees until nominations have closed
    if not election.is_nominations_closed():
        messages.info(request, "Nominees will be visible after nominations close.")
        return redirect("election_detail", election_slug=election.slug)

    # Find the nominee by matching the slug
    # We need to check all nominees with accepted nominations
    nominees = (
        Nominee.objects.filter(
            election=election,
            nominations__acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
            nominations__draft=False,
        )
        .distinct()
        .select_related("user", "user__profile")
        .prefetch_related("nominations__nominator")
    )

    nominee = None
    for n in nominees:
        if n.get_slug() == nominee_slug:
            nominee = n
            break

    if not nominee:
        messages.error(request, "Nominee not found.")
        return redirect("election_nominees", election_slug=election.slug)

    # Get accepted nominations, sorted with self-nominations first
    accepted = nominee.nominations.filter(
        acceptance_status=Nomination.AcceptanceStatus.ACCEPTED, draft=False
    ).select_related("nominator")

    self_noms = [n for n in accepted if n.nominator == nominee.user]
    other_noms = [n for n in accepted if n.nominator != nominee.user]
    nominee.accepted_nominations = self_noms + other_noms

    return render(
        request,
        "elections/nominee_detail.html",
        {"election": election, "nominee": nominee},
    )


def election_list(request):
    """List all elections."""
    elections = Election.objects.all().order_by("-created_at")
    upcoming_election = Election.get_upcoming()

    return render(
        request,
        "elections/election_list.html",
        {"elections": elections, "upcoming_election": upcoming_election},
    )


@login_required
def nomination_respond(request, election_slug, pk):
    """Accept or decline a nomination."""
    election = get_object_or_404(Election, slug=election_slug)
    nomination = get_object_or_404(
        Nomination, id=pk, nominee__election=election, nominee__user=request.user, draft=False
    )

    is_self_nomination = nomination.nominator == nomination.nominee.user

    # Check if acceptance period has closed (7 days after nominations close)
    if election.is_acceptance_period_closed():
        messages.error(
            request,
            "The acceptance period has closed. You can no longer change your response.",
        )
        return redirect("profile")

    # Check if nominee profile is complete before allowing acceptance
    if request.method == "POST" and request.POST.get("action") == "accept":
        if not nomination.nominee.is_profile_complete():
            messages.info(
                request,
                "Please complete your nominee profile before accepting this nomination.",
            )
            profile_url = reverse(
                "nominee_profile_edit",
                kwargs={
                    "election_slug": election.slug,
                    "nominee_id": nomination.nominee.id,
                },
            )
            respond_url = reverse(
                "nomination_respond",
                kwargs={"election_slug": election.slug, "pk": nomination.id},
            )
            return redirect(f"{profile_url}?next={respond_url}")

    if request.method == "POST":
        action = request.POST.get("action")
        note = request.POST.get("acceptance_note", "").strip()

        if is_self_nomination:
            # For self-nominations, only allow withdrawal (decline)
            if action == "withdraw":
                nomination.acceptance_status = Nomination.AcceptanceStatus.DECLINED
                nomination.acceptance_date = timezone.now()
                nomination.save()
                messages.success(
                    request, f"You have withdrawn your nomination for {election.title}."
                )
            else:
                messages.error(request, "Invalid action.")
        else:
            # For nominations from others
            if action == "accept":
                nomination.acceptance_status = Nomination.AcceptanceStatus.ACCEPTED
                nomination.acceptance_date = timezone.now()
                nomination.acceptance_note = note
                nomination.save()
                nominator_name = get_user_display_name(nomination.nominator)
                messages.success(
                    request,
                    f"You have accepted the nomination from {nominator_name} "
                    f"for {election.title}. Good luck!",
                )
            elif action == "decline":
                nomination.acceptance_status = Nomination.AcceptanceStatus.DECLINED
                nomination.acceptance_date = timezone.now()
                nomination.acceptance_note = note
                nomination.save()
                nominator_name = get_user_display_name(nomination.nominator)
                messages.success(
                    request,
                    f"You have declined the nomination from {nominator_name} "
                    f"for {election.title}.",
                )
            else:
                messages.error(request, "Invalid action.")

        return redirect("profile")

    return render(
        request,
        "elections/nomination_respond.html",
        {"nomination": nomination, "election": election, "is_self_nomination": is_self_nomination},
    )


@login_required
def nominee_search(request):
    """HTMX endpoint for typeahead search of eligible nominees."""
    query = request.GET.get("q", "").strip()

    # Strip @ from the beginning if present (for Discord handle searches)
    if query.startswith("@"):
        query = query[1:]

    if not query or len(query) < 2:
        return render(request, "elections/nominee_search_results.html", {"users": []})

    # Search by name or Discord username (not email for privacy)
    users = (
        User.objects.filter(profile__isnull=False)
        .filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(socialaccount__extra_data__username__icontains=query)
        )
        .distinct()
        .select_related("profile")[:10]
    )

    # Filter to only members and create sanitized data structure
    eligible_users = []
    for user in users:
        if user.profile.membership():
            # Include Discord handle if available (OK in authenticated context)
            discord = user.socialaccount_set.filter(provider="discord").first()
            discord_handle = discord.extra_data.get("username") if discord else None

            # Only send necessary data to frontend (no email, first name + last initial + discord)
            eligible_users.append(
                {
                    "id": user.id,
                    "display_name": get_user_display_name(user),
                    "discord_handle": discord_handle,
                }
            )

    return render(request, "elections/nominee_search_results.html", {"users": eligible_users})


@login_required
def nominee_profile_edit(request, election_slug, nominee_id):
    """Allow nominees to update their public profile information."""
    election = get_object_or_404(Election, slug=election_slug)
    nominee = get_object_or_404(Nominee, id=nominee_id, election=election, user=request.user)

    # Check if acceptance period has closed (allow profile edits during acceptance period)
    if election.is_acceptance_period_closed():
        messages.error(
            request,
            "The acceptance period has closed. You can no longer update your profile.",
        )
        return redirect("profile")

    # Get the next URL from query params (for redirecting back after completion)
    next_url = request.GET.get("next") or request.POST.get("next")
    # Get self-nomination ID if this profile edit is part of a self-nomination flow
    self_nomination_id = request.GET.get("self_nomination_id") or request.POST.get(
        "self_nomination_id"
    )

    if request.method == "POST":
        form = NomineeProfileForm(request.POST, request.FILES, instance=nominee, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your nominee profile has been updated.")

            # If this was part of a self-nomination flow, auto-submit the draft nomination
            if self_nomination_id:
                try:
                    nomination = Nomination.objects.get(
                        id=self_nomination_id, nominee=nominee, nominator=request.user, draft=True
                    )
                    # Submit the nomination (this will auto-accept it via the model's save method)
                    nomination.draft = False
                    nomination.save()
                    messages.success(request, "Your self-nomination has been submitted!")
                except Nomination.DoesNotExist:
                    # Nomination not found or already submitted, just continue
                    pass

            # Redirect back to the nomination response page if next_url is provided
            if next_url:
                return redirect(next_url)
            return redirect("profile")
    else:
        form = NomineeProfileForm(instance=nominee, user=request.user)

    return render(
        request,
        "elections/nominee_profile_edit.html",
        {
            "form": form,
            "nominee": nominee,
            "election": election,
            "next_url": next_url,
            "self_nomination_id": self_nomination_id,
        },
    )
