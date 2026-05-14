from django.db import transaction

from departments.models import Department


def would_create_cycle(department: Department, new_parent: Department) -> bool:
    current = new_parent
    while current is not None:
        if current.id == department.id:
            return True
        current = current.parent
    return False


def validate_parent_change(department: Department, new_parent: Department) -> None:
    if str(new_parent.id) == str(department.id):
        raise ValueError("A department cannot be its own parent.")
    if would_create_cycle(department, new_parent):
        raise ValueError(
            "Moving this department would create a cycle in the hierarchy."
        )


def delete_department_by_mode(
    department: Department, mode: str, reassign_to: Department | None = None
) -> None:
    if mode == "reassign":
        if reassign_to is None:
            raise ValueError(
                "reassign_to_department_id is required when mode is 'reassign'."
            )
        if reassign_to.id == department.id:
            raise ValueError("Cannot reassign to the same department being deleted.")
        with transaction.atomic():
            department.employees.all().update(department=reassign_to)
            department.delete()
    elif mode == "cascade":
        department.delete()
    else:
        raise ValueError("Invalid mode. Choose 'cascade' or 'reassign'.")
