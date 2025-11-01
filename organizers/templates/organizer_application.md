{% load bleach_tags %}
# {{ application.submitter.first_name|bleach }} {{ application.submitter.last_name|bleach }}

## Applicant

**Name**:
```
{{ application.submitter.first_name|bleach }} {{ application.submitter.last_name|bleach }}
```

**District**:
```
{{ application.submitter.profile.district }}
```

**Discord username**:
```
{{ application.submitter.profile.discord.extra_data.username|bleach }}
```

**{{ application.data.preferred_contact_method.label|bleach }}**:
```
{{ application.data.preferred_contact_method.value|bleach }}
```

## Nominating Organizer/Board Member
```
{{ application.data.nominator.value|bleach }}
```

## Desired role

**{{ application.data.primary_role.label|bleach }}**:
```
{{ application.data.primary_role.value|bleach }}
```

{% if application.data.primary_role_other.value == "other" %}
**{{ application.data.primary_other_role.label|bleach }}**:
```
{{ application.data.primary_otherrole.value|bleach }}
```
{% endif %}

**{{ application.data.regular_duties.label|bleach }}**
```
{{ application.data.regular_duties.value|bleach }}
```

**{{ application.data.teams.label|bleach }}**
```{% for team in application.data.teams.value %}
- {{ team|bleach }}{% endfor %}
```

## Past Involvement

**{{ application.data.involvement.label|bleach }}**
```
{{ application.data.involvement.value|bleach }}
```

**{{ application.data.past_experience.label|bleach }}**
```
{{ application.data.past_experience.value|bleach }}
```

**{{ application.data.current_contribution.label|bleach }}**
```
{{ application.data.current_contribution.value|bleach }}
```

{% if application.data.current_contribution_info.value %}
**{{ application.data.current_contribution_info.label|bleach }}**
```
{{ application.data.current_contribution_info.value|bleach }}
```
{% endif %}

## Availability

**{{ application.data.online_availability.label|bleach }}**
```
{{ application.data.online_availability.value|bleach }}
```

**{{ application.data.inperson_availability.label|bleach }}**
```
{{ application.data.inperson_availability.value|bleach }}
```

## Additional info

**{{ application.data.public_speaking.label|bleach }}**:
```
{{ application.data.public_speaking.value|default:"no response"|bleach }}
```

**{{ application.data.support_needed.label|bleach }}**:
```
{{ application.data.support_needed.value|default:"no response"|bleach }}
```

**{{ application.data.anything_else.label|bleach }}**:
```
{{ application.data.anything_else.value|default:"no response"|bleach }}
```

## Conduct

**Code of Conduct agreed**:
```
True
```

**{{ application.data.not_gonna_try_to_name_this.label|bleach }}**:
```
{{ application.data.not_gonna_try_to_name_this.value|bleach }}
```

{% if application.data.not_gonna_try_to_name_this_info.value %}
**{{ application.data.not_gonna_try_to_name_this_info.label|bleach }}**:
```
Response redacted by default. Only select PBA Admins can access this via bikeaction.org/admin/
```
{% endif %}
