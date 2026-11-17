import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Smart Study & Pomodoro Focus App")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "pomodoro.db")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            task_title TEXT,
            completed_at DATE DEFAULT CURRENT_DATE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            estimated_pomodoros INTEGER DEFAULT 2,
            completed_pomodoros INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Демо-данные за текущую неделю для красивого недельного графика
    cur.execute("SELECT COUNT(*) FROM focus_sessions")
    if cur.fetchone()[0] == 0:
        today = datetime.now().date()
        demo_sessions = [
            ("focus", 25, "Подготовка к экзамену по алгоритмам", (today - timedelta(days=6)).isoformat()),
            ("focus", 25, "Чтение конспекта по физике", (today - timedelta(days=6)).isoformat()),
            ("focus", 25, "Лабораторная по базам данных", (today - timedelta(days=5)).isoformat()),
            ("focus", 25, "Лабораторная по базам данных", (today - timedelta(days=5)).isoformat()),
            ("focus", 25, "Практика Python & FastAPI", (today - timedelta(days=4)).isoformat()),
            ("focus", 25, "Практика Python & FastAPI", (today - timedelta(days=4)).isoformat()),
            ("focus", 25, "Решение задач по математике", (today - timedelta(days=3)).isoformat()),
            ("focus", 25, "Решение задач по математике", (today - timedelta(days=3)).isoformat()),
            ("focus", 25, "Изучение английского (Technical Reading)", (today - timedelta(days=2)).isoformat()),
            ("focus", 25, "Разработка курсового проекта", (today - timedelta(days=1)).isoformat()),
            ("focus", 25, "Разработка курсового проекта", (today - timedelta(days=1)).isoformat()),
            ("focus", 25, "Разработка курсового проекта", (today - timedelta(days=1)).isoformat()),
            ("focus", 25, "Итоговое тестирование и код-ревью", today.isoformat()),
            ("focus", 25, "Итоговое тестирование и код-ревью", today.isoformat())
        ]
        cur.executemany("""
            INSERT INTO focus_sessions (mode, duration_minutes, task_title, completed_at)
            VALUES (?, ?, ?, ?)
        """, demo_sessions)

    cur.execute("SELECT COUNT(*) FROM study_tasks")
    if cur.fetchone()[0] == 0:
        cur.executemany("""
            INSERT INTO study_tasks (title, estimated_pomodoros, completed_pomodoros, is_completed)
            VALUES (?, ?, ?, ?)
        """, [
            ("Повторить теорию алгоритмов сортировки", 2, 2, 1),
            ("Закончить проект серверного мониторинга", 4, 3, 0),
            ("Прочитать 20 страниц учебника по сетям", 2, 1, 0),
            ("Вечерняя разминка и тренировка пресса", 1, 1, 1)
        ])

    conn.commit()
    conn.close()


init_db()


class CompleteSessionRequest(BaseModel):
    mode: str
    duration_minutes: int
    task_title: Optional[str] = "Свободный фокус"


class NewStudyTaskRequest(BaseModel):
    title: str
    estimated_pomodoros: int = 2


@app.get("/", response_class=HTMLResponse)
async def pomodoro_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


@app.get("/api/stats")
async def get_pomodoro_stats():
    conn = get_db()
    cur = conn.cursor()

    today = datetime.now().date()
    days_map = {}
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        days_map[d.isoformat()] = {"day": day_names[d.weekday()], "minutes": 0}

    cur.execute("""
        SELECT completed_at, SUM(duration_minutes) as total_min
        FROM focus_sessions
        WHERE completed_at >= ?
        GROUP BY completed_at
    """, ((today - timedelta(days=6)).isoformat(),))

    for row in cur.fetchall():
        d_str = row["completed_at"]
        if d_str in days_map:
            days_map[d_str]["minutes"] = row["total_min"]

    # All-time stats
    cur.execute("SELECT COUNT(*), SUM(duration_minutes) FROM focus_sessions WHERE mode = 'focus'")
    tot_row = cur.fetchone()
    total_sessions = tot_row[0] or 0
    total_minutes = tot_row[1] or 0

    conn.close()
    return {
        "weekly_chart": list(days_map.values()),
        "total_sessions": total_sessions,
        "total_hours": round(total_minutes / 60, 1),
        "streak_days": 7
    }


@app.post("/api/sessions/complete")
async def complete_session(data: CompleteSessionRequest):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO focus_sessions (mode, duration_minutes, task_title, completed_at)
        VALUES (?, ?, ?, CURRENT_DATE)
    """, (data.mode, data.duration_minutes, data.task_title))
    conn.commit()
    conn.close()
    return {"status": "recorded"}


@app.get("/api/tasks")
async def list_study_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM study_tasks ORDER BY is_completed ASC, id DESC")
    tasks = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"tasks": tasks}


@app.post("/api/tasks")
async def add_study_task(data: NewStudyTaskRequest):
    if not data.title.strip():
        raise HTTPException(status_code=400, detail="Название задачи обязательно")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO study_tasks (title, estimated_pomodoros, completed_pomodoros, is_completed)
        VALUES (?, ?, 0, 0)
    """, (data.title, data.estimated_pomodoros))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"status": "ok", "id": new_id}


@app.patch("/api/tasks/{task_id}/toggle")
async def toggle_study_task(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE study_tasks SET is_completed = 1 - is_completed WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "toggled"}


@app.delete("/api/tasks/{task_id}")
async def delete_study_task(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM study_tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8007, reload=False)
