from collections import Counter, defaultdict

from django.contrib import admin
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from elections.models import (
    Ballot,
    Election,
    Nomination,
    Nominee,
    Question,
    QuestionVote,
    Vote,
)


class NominationInline(admin.TabularInline):
    model = Nomination
    extra = 0
    fields = ("nominator", "draft", "acceptance_status", "created_at")
    readonly_fields = ("nominator", "created_at")
    can_delete = False
    show_change_link = True


@admin.action(description="Close election (anonymize all ballots)")
def close_election(modeladmin, request, queryset):
    """
    Close an election by anonymizing all ballots.
    First aggregates and stores final vote counts, then deletes all Vote and QuestionVote
    records, removing the association between voters and their choices, while keeping
    Ballot records to track participation.
    """

    elections_closed = 0
    total_votes_deleted = 0
    total_question_votes_deleted = 0

    with transaction.atomic():
        for election in queryset:
            # Get all ballots for this election
            ballots = (
                Ballot.objects.filter(election=election)
                .select_related("voter__profile")
                .prefetch_related("candidate_votes__nominee", "question_votes")
                .annotate(
                    num_candidate_votes=Count("candidate_votes"),
                    num_question_votes=Count("question_votes"),
                )
            )

            # Calculate vote counts for each nominee
            nominee_votes = Counter()
            # Track votes by district for each nominee
            nominee_district_votes = defaultdict(lambda: defaultdict(int))

            for ballot in ballots:
                voter_profile = ballot.voter.profile
                voter_district = voter_profile.district

                # Get district number (extract from "District 5" -> 5)
                voter_district_num = None
                if voter_district:
                    import re

                    match = re.search(r"\d+", voter_district.name)
                    if match:
                        voter_district_num = int(match.group())

                # Count votes for each nominee
                for vote in ballot.candidate_votes.all():
                    nominee = vote.nominee
                    nominee_votes[nominee] += 1

                    # Track district-specific votes if voter has a district
                    if voter_district_num:
                        nominee_district_votes[nominee][voter_district_num] += 1

                # Mark ballots that had at least one vote
                had_any_votes = ballot.num_candidate_votes > 0 or ballot.num_question_votes > 0
                ballot.had_votes = had_any_votes
                ballot.save(update_fields=["had_votes"])

            # Store final vote counts for each nominee
            for nominee in Nominee.objects.filter(election=election):
                nominee.final_vote_count = nominee_votes.get(nominee, 0)

                # Get nominee's district to find their district votes
                nominee_district = nominee.user.profile.district
                nominee_district_num = None
                if nominee_district:
                    import re

                    match = re.search(r"\d+", nominee_district.name)
                    if match:
                        nominee_district_num = int(match.group())

                if nominee_district_num:
                    nominee.final_district_vote_count = nominee_district_votes[nominee].get(
                        nominee_district_num, 0
                    )
                else:
                    nominee.final_district_vote_count = 0

                nominee.save(update_fields=["final_vote_count", "final_district_vote_count"])

            # Store final question vote counts
            for question in Question.objects.filter(election=election):
                yes_count = QuestionVote.objects.filter(question=question, answer=True).count()
                no_count = QuestionVote.objects.filter(question=question, answer=False).count()
                question.final_yes_votes = yes_count
                question.final_no_votes = no_count
                question.save(update_fields=["final_yes_votes", "final_no_votes"])

            # Now delete all votes to anonymize
            ballot_ids = list(ballots.values_list("id", flat=True))

            # Count and delete all candidate votes
            votes_deleted = Vote.objects.filter(ballot__in=ballot_ids).delete()[0]

            # Count and delete all question votes
            question_votes_deleted = QuestionVote.objects.filter(ballot__in=ballot_ids).delete()[0]

            total_votes_deleted += votes_deleted
            total_question_votes_deleted += question_votes_deleted
            elections_closed += 1

            modeladmin.message_user(
                request,
                f"Closed {election.title}: Stored final results and anonymized "
                f"{ballots.count()} ballots ({votes_deleted} candidate votes, "
                f"{question_votes_deleted} question votes deleted)",
            )

    if elections_closed > 1:
        modeladmin.message_user(
            request,
            f"Successfully closed {elections_closed} elections. "
            f"Total: {total_votes_deleted} candidate votes and "
            f"{total_question_votes_deleted} question votes anonymized.",
        )


class ElectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "eligibility_closed",
        "nominations_open_status",
        "nominations_closed_status",
        "voting_open_status",
        "voting_closed_status",
        "nominee_count",
        "preview_voting_booth",
    )
    search_fields = ("title", "description")
    ordering = ("-membership_eligibility_deadline",)
    actions = [close_election]

    def eligibility_closed(self, obj):
        return timezone.now() >= obj.membership_eligibility_deadline

    eligibility_closed.boolean = True
    eligibility_closed.short_description = "Eligibility Closed"

    def nominations_open_status(self, obj):
        now = timezone.now()
        return obj.nominations_open <= now < obj.nominations_close

    nominations_open_status.boolean = True
    nominations_open_status.short_description = "Nominations Open"

    def nominations_closed_status(self, obj):
        return timezone.now() >= obj.nominations_close

    nominations_closed_status.boolean = True
    nominations_closed_status.short_description = "Nominations Closed"

    def voting_open_status(self, obj):
        now = timezone.now()
        return obj.voting_opens <= now < obj.voting_closes

    voting_open_status.boolean = True
    voting_open_status.short_description = "Voting Open"

    def voting_closed_status(self, obj):
        return timezone.now() >= obj.voting_closes

    voting_closed_status.boolean = True
    voting_closed_status.short_description = "Voting Closed"

    def nominee_count(self, obj):
        count = obj.nominees.count()
        return format_html(
            '<a href="/admin/elections/nominee/?election__id__exact={}">{} nominee{}</a>',
            obj.id,
            count,
            "s" if count != 1 else "",
        )

    nominee_count.short_description = "Nominees"

    def preview_voting_booth(self, obj):
        from django.urls import reverse

        url = reverse("election_vote", args=[obj.slug]) + "?preview=true"
        return format_html('<a href="{}" target="_blank">Preview</a>', url)

    preview_voting_booth.short_description = "Preview Voting"


class NomineeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "election",
        "nomination_count",
        "accepted_nomination_count",
        "created_at",
    )
    list_filter = ("election", "created_at")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "nomination_count",
        "accepted_nomination_count",
    )
    ordering = ("-created_at",)
    inlines = [NominationInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "election",
                    "user",
                    "nomination_count",
                    "accepted_nomination_count",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Profile Information",
            {
                "fields": (
                    "photo",
                    "public_display_name",
                    "board_responsibilities_acknowledged",
                )
            },
        ),
    )


class NominationAdmin(admin.ModelAdmin):
    list_display = (
        "nominee",
        "nominator",
        "get_election",
        "draft",
        "created_at",
    )
    list_filter = ("nominee__election", "draft", "created_at")
    search_fields = (
        "nominee__user__first_name",
        "nominee__user__last_name",
        "nominee__user__email",
        "nominator__first_name",
        "nominator__last_name",
        "nominator__email",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_election(self, obj):
        return obj.nominee.election

    get_election.short_description = "Election"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "nominee",
                    "nominator",
                    "draft",
                    "acceptance_status",
                    "acceptance_date",
                    "acceptance_note",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        ("Nomination Content", {"fields": ("nomination_statement",)}),
    )


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ("question_text", "description", "order")
    ordering = ("order",)


class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0
    fields = ("nominee", "created_at")
    readonly_fields = ("nominee", "created_at")
    can_delete = False


class QuestionVoteInline(admin.TabularInline):
    model = QuestionVote
    extra = 0
    fields = ("question", "answer", "created_at")
    readonly_fields = ("question", "answer", "created_at")
    can_delete = False


class BallotAdmin(admin.ModelAdmin):
    list_display = (
        "voter",
        "election",
        "submitted_at",
        "candidate_vote_count",
        "question_vote_count",
    )
    list_filter = ("election", "submitted_at")
    search_fields = ("voter__first_name", "voter__last_name", "voter__email")
    readonly_fields = ("id", "submitted_at", "updated_at")
    ordering = ("-submitted_at",)
    inlines = [VoteInline, QuestionVoteInline]

    def candidate_vote_count(self, obj):
        return obj.candidate_votes.count()

    candidate_vote_count.short_description = "Candidate Votes"

    def question_vote_count(self, obj):
        return obj.question_votes.count()

    question_vote_count.short_description = "Question Votes"


class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_text", "election", "order", "vote_count")
    list_filter = ("election",)
    search_fields = ("question_text",)
    ordering = ("election", "order")

    def vote_count(self, obj):
        return obj.votes.count()

    vote_count.short_description = "Votes"


class VoteAdmin(admin.ModelAdmin):
    list_display = ("ballot", "nominee", "created_at")
    list_filter = ("ballot__election", "created_at")
    search_fields = (
        "ballot__voter__first_name",
        "ballot__voter__last_name",
        "nominee__user__first_name",
        "nominee__user__last_name",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


class QuestionVoteAdmin(admin.ModelAdmin):
    list_display = ("ballot", "question", "answer", "created_at")
    list_filter = ("ballot__election", "answer", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


# Update ElectionAdmin to include Questions inline
ElectionAdmin.inlines = [QuestionInline]

admin.site.register(Election, ElectionAdmin)
admin.site.register(Nominee, NomineeAdmin)
admin.site.register(Nomination, NominationAdmin)
admin.site.register(Ballot, BallotAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Vote, VoteAdmin)
admin.site.register(QuestionVote, QuestionVoteAdmin)
