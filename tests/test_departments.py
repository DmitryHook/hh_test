import pytest
from rest_framework.test import APIClient

from departments.models import Department, Employee


@pytest.fixture
def client():
    return APIClient()

# ========================= POST =========================


@pytest.mark.django_db
def test_create_root_department(client):
    response = client.post('/departments/', {'name': 'Engineering'})
    assert response.status_code == 201
    assert response.data['name'] == 'Engineering'
    assert response.data['parent_id'] is None


@pytest.mark.django_db
def test_create_child_department(client):
    parent = client.post('/departments/', {'name': 'Parent'}).data
    response = client.post('/departments/', {'name': 'Child', 'parent_id': parent['id']})
    assert response.status_code == 201
    assert response.data['parent_id'] == parent['id']


@pytest.mark.django_db
def test_department_name_trimmed(client):
    response = client.post('/departments/', {'name': '  Engineering  '})
    assert response.status_code == 201
    assert response.data['name'] == 'Engineering'


@pytest.mark.django_db
def test_department_name_empty_rejected(client):
    response = client.post('/departments/', {'name': '   '})
    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_name_same_parent_rejected(client):
    parent = client.post('/departments/', {'name': 'Parent'}).data
    client.post('/departments/', {'name': 'Backend', 'parent_id': parent['id']})
    response = client.post('/departments/', {'name': 'Backend', 'parent_id': parent['id']})
    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_name_root_rejected(client):
    client.post('/departments/', {'name': 'Root'})
    response = client.post('/departments/', {'name': 'Root'})
    assert response.status_code == 400


@pytest.mark.django_db
def test_same_name_different_parents_allowed(client):
    parent_a = client.post('/departments/', {'name': 'ParentA'}).data
    parent_b = client.post('/departments/', {'name': 'ParentB'}).data
    r1 = client.post('/departments/', {'name': 'Backend', 'parent_id': parent_a['id']})
    r2 = client.post('/departments/', {'name': 'Backend', 'parent_id': parent_b['id']})
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.django_db
def test_create_department_nonexistent_parent(client):
    response = client.post('/departments/', {'name': 'Orphan', 'parent_id': 9999})
    assert response.status_code == 400


# ========================= GET =========================


@pytest.mark.django_db
def test_retrieve_department_structure(client):
    dept = client.post('/departments/', {'name': 'Engineering'}).data
    response = client.get(f'/departments/{dept["id"]}/')
    assert response.status_code == 200
    assert response.data['name'] == 'Engineering'
    assert 'children' in response.data
    assert 'employees' in response.data


@pytest.mark.django_db
def test_retrieve_depth_one(client):
    root = client.post('/departments/', {'name': 'Root'}).data
    level1 = client.post('/departments/', {'name': 'L1', 'parent_id': root['id']}).data
    client.post('/departments/', {'name': 'L2', 'parent_id': level1['id']})

    response = client.get(f'/departments/{root["id"]}/?depth=1')
    assert response.status_code == 200
    assert len(response.data['children']) == 1
    assert response.data['children'][0]['children'] == []


@pytest.mark.django_db
def test_retrieve_depth_two(client):
    root = client.post('/departments/', {'name': 'Root'}).data
    level1 = client.post('/departments/', {'name': 'L1', 'parent_id': root['id']}).data
    client.post('/departments/', {'name': 'L2', 'parent_id': level1['id']})

    response = client.get(f'/departments/{root["id"]}/?depth=2')
    assert response.status_code == 200
    assert len(response.data['children'][0]['children']) == 1


@pytest.mark.django_db
def test_retrieve_depth_capped_at_5(client):
    prev_id = None
    for i in range(10):
        res = client.post('/departments/', {'name': f'L{i}', 'parent_id': prev_id}, content_type='application/json').data
        if i == 0: root_id = res['id']
        prev_id = res['id']

    response = client.get(f'/departments/{root_id}/?depth=99')
    
    assert response.status_code == 200
    
    curr = response.data
    for _ in range(5):
        assert len(curr['children']) > 0
        curr = curr['children'][0]
    
    assert curr['children'] == [], "Сериализатор провалился глубже установленного лимита в 5 уровней"


@pytest.mark.django_db
def test_retrieve_exclude_employees(client):
    dept = client.post('/departments/', {'name': 'Dept'}).data
    client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': 'Alice', 'position': 'Dev'
    })
    response = client.get(f'/departments/{dept["id"]}/?include_employees=false')
    assert response.status_code == 200
    assert response.data['employees'] == []


@pytest.mark.django_db
def test_retrieve_nonexistent(client):
    response = client.get('/departments/9999/')
    assert response.status_code == 404


# ========================= PATCH =========================


@pytest.mark.django_db
def test_patch_rename(client):
    dept = client.post('/departments/', {'name': 'Old Name'}).data
    response = client.patch(f'/departments/{dept["id"]}/', {'name': 'New Name'})
    assert response.status_code == 200
    assert response.data['name'] == 'New Name'


@pytest.mark.django_db
def test_patch_move_to_new_parent(client):
    parent = client.post('/departments/', {'name': 'Parent'}).data
    child = client.post('/departments/', {'name': 'Child'}).data
    response = client.patch(f'/departments/{child["id"]}/', {'parent_id': parent['id']})
    assert response.status_code == 200
    assert response.data['parent_id'] == parent['id']


@pytest.mark.django_db
def test_cycle_detection(client):
    parent = client.post('/departments/', {'name': 'Parent'}).data
    child = client.post('/departments/', {'name': 'Child', 'parent_id': parent['id']}).data
    response = client.patch(f'/departments/{parent["id"]}/', {'parent_id': child['id']})
    assert response.status_code == 409


@pytest.mark.django_db
def test_deep_cycle_detection(client):
    a = client.post('/departments/', {'name': 'A'}).data
    b = client.post('/departments/', {'name': 'B', 'parent_id': a['id']}).data
    c = client.post('/departments/', {'name': 'C', 'parent_id': b['id']}).data
    response = client.patch(f'/departments/{a["id"]}/', {'parent_id': c['id']})
    assert response.status_code == 409


@pytest.mark.django_db
def test_self_parent_rejected(client):
    dept = client.post('/departments/', {'name': 'Solo'}).data
    response = client.patch(f'/departments/{dept["id"]}/', {'parent_id': dept['id']})
    assert response.status_code == 400


# ========================= DELETE =========================


@pytest.mark.django_db
def test_delete_cascade_removes_children(client):
    root = client.post('/departments/', {'name': 'Root'}).data
    client.post('/departments/', {'name': 'Child', 'parent_id': root['id']})
    response = client.delete(f'/departments/{root["id"]}/?mode=cascade')
    assert response.status_code == 204
    assert Department.objects.count() == 0


@pytest.mark.django_db
def test_delete_cascade_removes_employees(client):
    dept = client.post('/departments/', {'name': 'Dept'}).data
    client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': 'Alice', 'position': 'Dev'
    })
    client.delete(f'/departments/{dept["id"]}/?mode=cascade')
    assert Employee.objects.count() == 0


@pytest.mark.django_db
def test_delete_reassign_moves_employees(client):
    source = client.post('/departments/', {'name': 'Source'}).data
    target = client.post('/departments/', {'name': 'Target'}).data
    client.post(f'/departments/{source["id"]}/employees/', {
        'full_name': 'John Doe', 'position': 'Dev'
    })
    response = client.delete(
        f'/departments/{source["id"]}/?mode=reassign'
        f'&reassign_to_department_id={target["id"]}'
    )
    assert response.status_code == 204
    assert Department.objects.filter(id=source['id']).count() == 0
    assert Employee.objects.filter(department_id=target['id']).count() == 1


@pytest.mark.django_db
def test_delete_reassign_removes_children_cascade(client):
    source = client.post('/departments/', {'name': 'Source'}).data
    target = client.post('/departments/', {'name': 'Target'}).data
    client.post('/departments/', {'name': 'Child of Source', 'parent_id': source['id']})

    client.delete(
        f'/departments/{source["id"]}/?mode=reassign'
        f'&reassign_to_department_id={target["id"]}'
    )
    assert Department.objects.count() == 1
    assert Department.objects.filter(name='Target').exists()


@pytest.mark.django_db
def test_delete_reassign_missing_target(client):
    dept = client.post('/departments/', {'name': 'Dept'}).data
    response = client.delete(f'/departments/{dept["id"]}/?mode=reassign')
    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_reassign_same_department(client):
    dept = client.post('/departments/', {'name': 'Dept'}).data
    response = client.delete(
        f'/departments/{dept["id"]}/?mode=reassign'
        f'&reassign_to_department_id={dept["id"]}'
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_invalid_mode(client):
    dept = client.post('/departments/', {'name': 'Dept'}).data
    response = client.delete(f'/departments/{dept["id"]}/?mode=invalid')
    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_nonexistent(client):
    response = client.delete('/departments/9999/?mode=cascade')
    assert response.status_code == 404


# ========================= Employees =========================


@pytest.mark.django_db
def test_create_employee(client):
    dept = client.post('/departments/', {'name': 'HR'}).data
    response = client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': 'Alice Smith',
        'position': 'Manager',
        'hired_at': '2023-01-15',
    })
    assert response.status_code == 201
    assert response.data['full_name'] == 'Alice Smith'
    assert response.data['position'] == 'Manager'


@pytest.mark.django_db
def test_create_employee_without_hired_at(client):
    dept = client.post('/departments/', {'name': 'HR'}).data
    response = client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': 'Bob', 'position': 'Dev'
    })
    assert response.status_code == 201
    assert response.data['hired_at'] is None


@pytest.mark.django_db
def test_create_employee_nonexistent_department(client):
    response = client.post('/departments/9999/employees/', {
        'full_name': 'Ghost', 'position': 'Dev'
    })
    assert response.status_code == 404


@pytest.mark.django_db
def test_employee_name_trimmed(client):
    dept = client.post('/departments/', {'name': 'HR'}).data
    response = client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': '  Alice  ',
        'position': '  Manager  ',
    })
    assert response.status_code == 201
    assert response.data['full_name'] == 'Alice'
    assert response.data['position'] == 'Manager'


@pytest.mark.django_db
def test_employee_empty_name_rejected(client):
    dept = client.post('/departments/', {'name': 'HR'}).data
    response = client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': '', 'position': 'Dev'
    })
    assert response.status_code == 400


@pytest.mark.django_db
def test_employee_empty_position_rejected(client):
    dept = client.post('/departments/', {'name': 'HR'}).data
    response = client.post(f'/departments/{dept["id"]}/employees/', {
        'full_name': 'Alice', 'position': ''
    })
    assert response.status_code == 400