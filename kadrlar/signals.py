from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    """
    kadrlar app migratsiyasi bajarilganda avtomatik guruhlarni yaratish:
    - kafedra: add_employee
    - kadr: change_employee, view_employee, add_order, change_order, view_order
    """
    if sender.name != 'kadrlar':
        return

    Employee = apps.get_model('kadrlar', 'Employee')
    Order = apps.get_model('kadrlar', 'Order')
    ct_emp = ContentType.objects.get_for_model(Employee)
    ct_order = ContentType.objects.get_for_model(Order)

    kafedra_group, _ = Group.objects.get_or_create(name='kafedra')
    perm_add_emp = Permission.objects.filter(content_type=ct_emp, codename='add_employee').first()
    if perm_add_emp:
        kafedra_group.permissions.add(perm_add_emp)

    hr_group, _ = Group.objects.get_or_create(name='kadr')
    perms_to_add = []
    for (ct, code) in [
        (ct_emp, 'change_employee'), (ct_emp, 'view_employee'),
        (ct_order, 'add_order'), (ct_order, 'change_order'), (ct_order, 'view_order')
    ]:
        p = Permission.objects.filter(content_type=ct, codename=code).first()
        if p:
            perms_to_add.append(p)
    for p in perms_to_add:
        hr_group.permissions.add(p)