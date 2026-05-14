from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent"],
                name="unique_name_per_parent",
                condition=models.Q(parent__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["name"],
                name="unique_name_root",
                condition=models.Q(parent__isnull=True),
            ),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="employees"
    )
    full_name = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    hired_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.full_name
