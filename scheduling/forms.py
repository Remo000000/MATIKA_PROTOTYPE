from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class TeacherPreferencesForm(forms.Form):
    """
    Teacher preference form:
    - preferred_days: weekdays 1..6
    - preferred_periods: class periods 1..8
    """

    DAY_CHOICES = [
        (1, _("Mon")),
        (2, _("Tue")),
        (3, _("Wed")),
        (4, _("Thu")),
        (5, _("Fri")),
        (6, _("Sat")),
    ]

    PERIOD_CHOICES = [(i, str(i)) for i in range(1, 9)]

    preferred_days = forms.MultipleChoiceField(
        label=_("Preferred days"),
        required=False,
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    preferred_periods = forms.MultipleChoiceField(
        label=_("Preferred periods"),
        required=False,
        choices=PERIOD_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    avoid_early = forms.BooleanField(
        label=_("Avoid very early classes"),
        required=False,
    )

    def __init__(self, *args, teacher_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_profile = teacher_profile
        if teacher_profile:
            self.initial["preferred_days"] = [str(d) for d in (teacher_profile.preferred_days or [])]
            self.initial["preferred_periods"] = [str(p) for p in (teacher_profile.preferred_periods or [])]
            self.initial["avoid_early"] = "1" not in self.initial["preferred_periods"]

    def normalized_days_periods(self) -> tuple[list[int], list[int]]:
        """Preferred days and periods after applying \"avoid early\" rule (for saving or approval requests)."""
        days = [int(x) for x in self.cleaned_data.get("preferred_days", [])]
        periods = [int(x) for x in self.cleaned_data.get("preferred_periods", [])]
        if self.cleaned_data.get("avoid_early") and 1 in periods:
            periods = [p for p in periods if p != 1]
        return days, periods

    def save(self):
        if not self.teacher_profile:
            return
        days, periods = self.normalized_days_periods()
        self.teacher_profile.preferred_days = days
        self.teacher_profile.preferred_periods = periods
        self.teacher_profile.save(update_fields=["preferred_days", "preferred_periods"])

