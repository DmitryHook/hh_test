from rest_framework import serializers

from departments.models import Employee, Department


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "department", "full_name", "position", "hired_at", "created_at"]
        read_only_fields = ["id", "created_at", "department"]

    def validate_full_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name cannot be empty")
        return value

    def validate_position(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Position cannot be empty")
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        queryset=Department.objects.all(),
        allow_null=True,
        required=False,
        default=None,
    )

    class Meta:
        model = Department
        fields = ["id", "name", "parent_id", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Department name cannot be empty")
        return value

    def validate(self, attrs: dict) -> dict:
        name = attrs.get("name", getattr(self.instance, "name", ""))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        instance = self.instance

        qs = Department.objects.filter(name=name, parent=parent)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            location = f"parent id={parent.pk}" if parent else "root level"
            raise serializers.ValidationError(
                {"name": f"Department with this name already exists at {location}."}
            )
        return attrs


class DepartmentTreeSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        queryset=Department.objects.all(),
        allow_null=True,
        required=False,
        default=None,
    )
    children = serializers.SerializerMethodField()
    employees = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["id", "name", "parent_id", "created_at", "children", "employees"]
        read_only_fields = ["id", "created_at"]

    def get_children(self, obj: Department) -> list:
        current_depth: int = self.context.get("current_depth", 0)
        max_depth: int = self.context.get("max_depth", 1)

        if current_depth >= max_depth:
            return []

        children = obj.children.all()
        serializer = DepartmentTreeSerializer(
            children,
            many=True,
            context={**self.context, "current_depth": current_depth + 1},
        )
        return serializer.data

    def get_employees(self, obj: Department) -> list:
        include_employees: bool = self.context.get("include_employees", True)
        if not include_employees:
            return []
        employees = obj.employees.all().order_by("created_at")
        return EmployeeSerializer(employees, many=True).data
