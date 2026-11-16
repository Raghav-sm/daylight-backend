def test_project_summaries_include_zero_and_avoid_multiplication(client):
    empty = client.post("/projects", json={"name": "Empty", "color": "blue"}).json()
    busy = client.post("/projects", json={"name": "Busy", "color": "teal"}).json()

    client.post(
        f"/projects/{busy['id']}/tasks",
        json={"title": "One", "stageId": busy["stages"][0]["id"]},
    )
    completed_stage = next(stage for stage in busy["stages"] if stage["name"] == "Completed")
    client.post(
        f"/projects/{busy['id']}/tasks",
        json={"title": "Two", "stageId": completed_stage["id"]},
    )
    client.post(
        f"/projects/{busy['id']}/stages",
        json={"name": "Review", "color": "violet"},
    )

    summaries = {item["id"]: item for item in client.get("/projects/summary").json()}

    assert summaries[empty["id"]]["taskCount"] == 0
    assert summaries[empty["id"]]["incompleteTaskCount"] == 0
    assert summaries[empty["id"]]["stageCount"] == 3

    assert summaries[busy["id"]]["taskCount"] == 2
    assert summaries[busy["id"]]["incompleteTaskCount"] == 1
    assert summaries[busy["id"]]["stageCount"] == 4


def test_delete_project_blocked_when_tasks_exist(client):
    project = client.post("/projects", json={"name": "Keep", "color": "blue"}).json()
    client.post(
        f"/projects/{project['id']}/tasks",
        json={"title": "Block delete"},
    )

    blocked = client.delete(f"/projects/{project['id']}")
    assert blocked.status_code == 409

    tasks = client.get(f"/projects/{project['id']}/tasks").json()
    for task in tasks:
        client.delete(f"/tasks/{task['id']}")

    deleted = client.delete(f"/projects/{project['id']}")
    assert deleted.status_code == 204
