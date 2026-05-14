import logging
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import viewsets, status
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from departments.models import Department
from departments.serializers import EmployeeSerializer, DepartmentTreeSerializer, DepartmentSerializer
from departments.services import validate_parent_change, delete_department_by_mode


logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(exclude=True),
    create=extend_schema(
        tags=["departments"],
        summary="Создать подразделение",
        description="Создает новое подразделение, можно указать родительский отдел через parent_id",
    ),
    retrieve=extend_schema(
        tags=["departments"],
        summary="Получить подразделение (детали + сотрудники + поддерево)",
        description="Возвращает детальную информацию о конкретном подразделении, "
        "включая его сотрудников и иерархическую структуру вложенных отделов",
    ),
    partial_update=extend_schema(
        tags=["departments"],
        summary="Переместить подразделение в другое (изменить parent)",
        description="Редактирование данных подразделения,"
        "можно сменить название через name или родительский отдел через parent_id",
    ),
    destroy=extend_schema(
        tags=["departments"],
        summary="Удалить подразделение",
        description="Удаление подразделения с выбором стратегии: "
        "cascade - полное удаление данных подразделения, отделов, сотрудников; "
        "reassign - удаление подразделения, отделов и перенос сотрудников в другой отдел",
    ),
    create_employee=extend_schema(
        tags=["employees"],
        summary="Создать сотрудника в подразделении",
        description="Создает сотрудника в подразделении, можно указать дату найма через hired_at",
    ),
)
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def create(self, request: Request, *args, **kwargs) -> Response:
        response = super().create(request, *args, **kwargs)

        if response.status_code == 201:
            logger.info("POST /departments/ - создано подразделение: %s", request.data)

        return response

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Глубина вложенности (0-5)",
                default=1,
            ),
            OpenApiParameter(
                name="include_employees",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Включать ли список сотрудников в ответ",
                default=True,
            ),
        ]
    )
    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        depth_param = request.query_params.get("depth", "1")
        try:
            depth = min(max(int(depth_param), 0), 5)
        except ValueError:
            depth = 1

        include_employees = (
            request.query_params.get("include_employees", "true").lower() == "true"
        )
        serializer = DepartmentTreeSerializer(
            instance,
            context={
                "request": request,
                "max_depth": depth,
                "include_employees": include_employees,
                "current_depth": 0,
            },
        )
        return Response(serializer.data)

    @extend_schema(
        request=EmployeeSerializer,
        responses={201: EmployeeSerializer},
    )
    @action(detail=True, methods=["post"], url_path="employees")
    def create_employee(self, request: Request, pk: int | None = None) -> Response:
        department = get_object_or_404(Department, pk=pk)
        serializer = EmployeeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(department=department)
            logger.info(
                "POST /departments/{id}/employees/ - создан сотрудник: %s",
                request.data,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        logger.info(
            "PATCH /departments/{id}/ - old: %s, new: %s",
            DepartmentSerializer(instance).data,
            request.data,
        )
        new_parent_id = request.data.get("parent_id")

        if new_parent_id is not None:
            new_parent = get_object_or_404(Department, pk=new_parent_id)
            try:
                validate_parent_change(instance, new_parent)
            except ValueError as e:
                msg = str(e)
                if "own parent" in msg:
                    return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": msg}, status=status.HTTP_409_CONFLICT)

        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="ID отдела",
            ),
            OpenApiParameter(
                name="mode",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="cascade - удалить всё; reassign - перенести сотрудников",
                default="cascade",
            ),
            OpenApiParameter(
                name="reassign_to_department_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="ID отдела для переноса сотрудников (обязателен при mode=reassign)",
            ),
        ]
    )
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        instance = self.get_object()
        mode = request.query_params.get("mode", "cascade")
        reassign_to_id = request.query_params.get("reassign_to_department_id")
        reassign_to = (
            get_object_or_404(Department, pk=reassign_to_id) if reassign_to_id else None
        )

        department_id = instance.id
        reassign_id = reassign_to.id if reassign_to else None

        try:
            delete_department_by_mode(instance, mode, reassign_to)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if mode == "reassign":
            logger.info(
                "DELETE /departments/{id}/ - Подразделение %s удалено (reassign); сотрудники перенесены в %s",
                department_id,
                reassign_id,
            )
        else:
            logger.info(
                "DELETE /departments/{id}/ - Подразделение %s удалено (cascade)",
                department_id,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
