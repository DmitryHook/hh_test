from django.contrib import admin
from departments.models import Department, Employee

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'created_at')
    search_fields = ('name',)
    list_filter = ('parent',)
    autocomplete_fields = ('parent',)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'department', 'position', 'hired_at')
    list_filter = ('department', 'hired_at')
    search_fields = ('full_name', 'position')
    date_hierarchy = 'hired_at'
    autocomplete_fields = ('department',)
