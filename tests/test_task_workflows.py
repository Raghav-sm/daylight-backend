def test_task_summaries_use_subtask_aggregates(client):
    project = client.post("/projects", json={"name": "Board", "color": "blue"}).json()
    stage_id = project["stages"][0]["id"]
    task = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Card", "stageId": stage_id},
    ).json()

    client.patch(
        f"/tasks/{task['id']}",
        json={
            "subtasks": [
                {"title": "A", "completed": True},
                {"title": "B", "completed": False},
            ]
        },
    )

    bare = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Bare", "stageId": stage_id},
    ).json()

    summaries = {item["id"]: item for item in client.get(f"/projects/{project['id']}/tasks/summary").json()}

    assert "notes" not in summaries[task["id"]]
    assert "subtasks" not in summaries[task["id"]]
    assert summaries[task["id"]]["subtaskCount"] == 2
    assert summaries[task["id"]]["completedSubtaskCount"] == 1
    assert summaries[bare["id"]]["subtaskCount"] == 0
    assert summaries[bare["id"]]["completedSubtaskCount"] == 0


def test_create_in_completed_stage_sets_completion(client):
    project = client.post("/projects", json={"name": "Done", "color": "green"}).json()
    completed_stage = next(stage for stage in project["stages"] if stage["name"] == "Completed")

    task = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Finish", "stageId": completed_stage["id"]},
    ).json()

    assert task["completed"] is True
    assert task["completedAt"] is not None


def test_contradictory_stage_and_completed_rejected(client):
    project = client.post("/projects", json={"name": "Conflict", "color": "red"}).json()
    todo = project["stages"][0]["id"]
    task = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Move", "stageId": todo},
    ).json()

    response = client.patch(
        f"/tasks/{task['id']}",
        json={"stageId": todo, "completed": True},
    )
    assert response.status_code == 422


def test_clearing_due_date_clears_time(client):
    project = client.post("/projects", json={"name": "Dates", "color": "amber"}).json()
    task = client.post(
        f"/projects/{project['id']}/tasks",
        json={
            "title": "Timed",
            "dueDate": "2026-11-13",
            "dueTime": "10:30:00",
            "stageId": project["stages"][0]["id"],
        },
    ).json()

    updated = client.patch(f"/tasks/{task['id']}", json={"dueDate": None}).json()
    assert updated["dueDate"] is None
    assert updated["dueTime"] is None


def test_subtask_ownership_and_duplicates_rejected(client):
    project = client.post("/projects", json={"name": "Subs", "color": "blue"}).json()
    first = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "One", "stageId": project["stages"][0]["id"]},
    ).json()
    second = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Two", "stageId": project["stages"][0]["id"]},
    ).json()

    with_sub = client.patch(
        f"/tasks/{first['id']}",
        json={"subtasks": [{"title": "Owned", "completed": False}]},
    ).json()
    owned_id = with_sub["subtasks"][0]["id"]

    stolen = client.patch(
        f"/tasks/{second['id']}",
        json={"subtasks": [{"id": owned_id, "title": "Stolen", "completed": False}]},
    )
    assert stolen.status_code == 422

    duplicate = client.patch(
        f"/tasks/{first['id']}",
        json={
            "subtasks": [
                {"id": owned_id, "title": "Owned", "completed": False},
                {"id": owned_id, "title": "Dup", "completed": False},
            ]
        },
    )
    assert duplicate.status_code == 422


def test_complete_uses_named_completed_not_last_stage(client):
    project = client.post("/projects", json={"name": "Custom order", "color": "blue"}).json()
    completed = next(stage for stage in project["stages"] if stage["name"] == "Completed")
    todo = next(stage for stage in project["stages"] if stage["name"] == "To Do")
    after = client.post(
        f"/projects/{project['id']}/stages",
        json={"name": "Archive", "color": "violet"},
    ).json()

    task = client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Finish me", "stageId": todo["id"]},
    ).json()

    updated = client.patch(f"/tasks/{task['id']}", json={"completed": True}).json()
    assert updated["completed"] is True
    assert updated["completedAt"] is not None
    assert updated["stageId"] == completed["id"]
    assert updated["stageId"] != after["id"]

    reopened = client.patch(f"/tasks/{task['id']}", json={"completed": False}).json()
    assert reopened["completed"] is False
    assert reopened["completedAt"] is None
    assert reopened["stageId"] == todo["id"]


def test_project_transfer_omitting_stage_assigns_destination(client):
    source = client.post("/projects", json={"name": "Source", "color": "red"}).json()
    destination = client.post("/projects", json={"name": "Dest", "color": "green"}).json()
    source_todo = next(stage for stage in source["stages"] if stage["name"] == "To Do")
    dest_todo = next(stage for stage in destination["stages"] if stage["name"] == "To Do")
    dest_completed = next(stage for stage in destination["stages"] if stage["name"] == "Completed")

    incomplete = client.post(
        f"/projects/{source['id']}/tasks",
        json={"title": "Move incomplete", "stageId": source_todo["id"]},
    ).json()
    moved = client.patch(
        f"/tasks/{incomplete['id']}",
        json={"projectId": destination["id"]},
    ).json()
    assert moved["projectId"] == destination["id"]
    assert moved["stageId"] == dest_todo["id"]
    assert moved["completed"] is False

    completed_task = client.post(
        f"/projects/{source['id']}/tasks",
        json={"title": "Move complete", "stageId": source_todo["id"]},
    ).json()
    completed_task = client.patch(
        f"/tasks/{completed_task['id']}",
        json={"completed": True},
    ).json()
    moved_done = client.patch(
        f"/tasks/{completed_task['id']}",
        json={"projectId": destination["id"]},
    ).json()
    assert moved_done["projectId"] == destination["id"]
    assert moved_done["stageId"] == dest_completed["id"]
    assert moved_done["completed"] is True
    assert moved_done["completedAt"] is not None


def test_project_transfer_explicit_null_stage_stays_unassigned(client):
    source = client.post("/projects", json={"name": "From", "color": "amber"}).json()
    destination = client.post("/projects", json={"name": "To", "color": "teal"}).json()
    source_todo = next(stage for stage in source["stages"] if stage["name"] == "To Do")

    task = client.post(
        f"/projects/{source['id']}/tasks",
        json={"title": "Unassign on transfer", "stageId": source_todo["id"]},
    ).json()
    moved = client.patch(
        f"/tasks/{task['id']}",
        json={"projectId": destination["id"], "stageId": None},
    ).json()
    assert moved["projectId"] == destination["id"]
    assert moved["stageId"] is None
