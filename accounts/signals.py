from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Notification, User


@receiver(post_save, sender=Notification)
def mirror_teacher_student_notifications_to_admins(
    sender, instance: Notification, created: bool, **kwargs
) -> None:
    """Copy notifications addressed to teachers or students to all org admins."""
    if not created:
        return
    user = instance.user
    if user.role not in (User.Role.TEACHER, User.Role.STUDENT):
        return
    org_id = getattr(user, "organization_id", None)
    if not org_id:
        return
    admins = User.objects.filter(organization_id=org_id, role=User.Role.ADMIN).exclude(pk=user.pk)
    for admin in admins:
        Notification.objects.create(
            user=admin,
            kind=instance.kind,
            payload=instance.payload or {},
            title=instance.title,
            body=instance.body,
            is_read=False,
            profile_change_request_id=instance.profile_change_request_id,
            teacher_preference_request_id=instance.teacher_preference_request_id,
        )
