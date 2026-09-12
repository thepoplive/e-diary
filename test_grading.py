import urllib.request, http.cookiejar, urllib.parse, sqlite3, re, os, datetime, sys
import test_helpers

BASE = "http://127.0.0.1:8077"
DB = os.path.join(os.path.dirname(__file__), "college_diary.db")
ADMIN = "admin"
PW = test_helpers.admin_password()

okn = 0
failn = []
def ok(label):
    global okn
    okn += 1
    print("  [OK]", label)
def fail(label, detail=""):
    failn.append(label)
    print("  [FAIL]", label, detail)

def login(login, password):
    return test_helpers.login(login, password)

def GET(op, path):
    status, _, body = test_helpers.GET(op, path)
    return status, body

def POST(op, path, data):
    status, loc, body = test_helpers.POST(op, path, data)
    return status, loc, body

today = datetime.date.today()
wd = today.weekday()

# Track initial grade/remarks counts
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# idempotency: clear test artifacts from any previous run (keep settings, users, schedule)
con.execute("DELETE FROM grade_change_requests")
con.execute("DELETE FROM grades")
con.execute("DELETE FROM attendance")
con.execute("DELETE FROM lessons")
con.execute("DELETE FROM pinned_notifications")
con.commit()

# --- 1. Admin: add schedule for today ---
print("=== Setup schedule for today ===")
op = login(ADMIN, PW)
s, loc, _ = POST(op, "/admin/schedule/add", {
    "day": str(wd),
    "group_id": "1",
    "subjects": ["Математика", "Физика", "История"],
    "teacher_ids": ["2", "2", "2"],
    "rooms": ["101", "102", "103"],
})
ok(f"Schedule added for today ({wd})") if "/admin/schedule" in loc else fail("add schedule", loc)

# verify entries exist
entries = con.execute("SELECT id FROM schedule_entries WHERE day_of_week=? AND group_id=1 ORDER BY lesson_number", (wd,)).fetchall()
entry_ids = [e["id"] for e in entries]
ok(f"{len(entry_ids)} schedule entries created") if len(entry_ids) >= 2 else fail("entries count", str(entry_ids))
first_entry = entry_ids[0]

# --- 2. Teacher: open today, find lesson, grade students ---
print("\n=== Teacher grades today's lesson ===")
top = login("teacher_sidorova", "newpass")
s, html = GET(top, "/teacher/today")
m = re.search(r"/teacher/lesson/(\d+)", html)
ok("Today lesson link found") if m else fail("no lesson link", html[:200])
lesson_id = int(m.group(1)) if m else 0

s, loc, _ = POST(top, f"/teacher/lesson/{lesson_id}", {
    "student_ids": ["3", "4", "5"],
    "attendance": ["present", "sick", "skip"],
    "grades": ["5", "!", "3"],
    "comments": ["", "справка от врача", "опоздал без причины"],
})
ok("Lesson saved") if "/teacher/lesson" in loc else fail("save lesson", loc)

# verify DB
grades = con.execute("SELECT student_id, value FROM grades WHERE lesson_id=?", (lesson_id,)).fetchall()
ok(f"Grades saved ({len(grades)})") if len(grades) == 3 else fail("grades count", str(grades))
att = con.execute("SELECT student_id, status FROM attendance WHERE lesson_id=?", (lesson_id,)).fetchall()
ok(f"Attendance saved ({len(att)})") if len(att) == 3 else fail("att leaves", str(att))

# --- 3. Student sees grades ---
print("\n=== Student view ===")
sop = login("petrov", "pass123")
s, html = GET(sop, "/student/today")
ok("Student today has grade 5") if "grade-5" in html else fail("student grade", "no grade-5")
s, html = GET(sop, "/student/grades")
ok("Student grades page ok") if s == 200 else fail("student grades 500")

# --- 4. Parent sees child grades ---
# Fix parent linkage: e2e test set child_id=2 (teacher), fix to petrov (student id=3)
con.execute("UPDATE users SET child_id=3 WHERE login='petrova_mama'")
con.commit()
print("\n=== Parent view ===")
pop = login("petrova_mama", "pass123")
s, html = GET(pop, "/parent/today")
ok("Parent today has grade") if "grade-5" in html else fail("parent grade")
s, html = GET(pop, "/parent/grades")
ok("Parent grades ok") if s == 200 else fail("parent grades 500")

# --- 5. Dashboard counts ---
print("\n=== Dashboard counters ===")
s, html = GET(login(ADMIN, PW), "/admin")
ok("Dashboard renders") if s == 200 else fail("dash")
gcount = con.execute("SELECT COUNT(*) c FROM grades").fetchone()["c"]
rcount = con.execute("SELECT COUNT(*) c FROM grades WHERE value='!'").fetchone()["c"]
ok("Dashboard shows grades count") if f'>{gcount}<' in html.replace(" ", "") or f">{gcount}</" in html else fail("grades count on dashboard", f"grades={gcount}")

# --- 6. Grade-change request flow (old lesson) ---
print("\n=== Grade change with admin approval ===")
# set short windows
POST(login(ADMIN, PW), "/admin/settings/save", {"grade_edit_days": "1", "grade_admin_edit_days": "3"})

# create an "old" lesson (3 days ago) on the first entry and a grade
old_date = (today - datetime.timedelta(days=3)).isoformat()
lesson_old_id = con.execute(
    "INSERT INTO lessons (schedule_entry_id, date) VALUES (?, ?)",
    (first_entry, old_date),
).lastrowid
con.execute(
    "INSERT INTO grades (lesson_id, student_id, value, comment, teacher_id) VALUES (?, ?, '4', 'старая оценка', 2)",
    (lesson_old_id, 3),
)
con.commit()

# teacher tries to change it with a comment
top2 = login("teacher_sidorova", "newpass")
s, html = GET(top2, f"/teacher/edit_grades/lesson/{lesson_old_id}")
ok("Edit grades page modal shows warning") if "требуют подтверждения" in html or "подтверждение" in html else fail("warning text", html[:300])

s, loc, _ = POST(top2, f"/teacher/edit_grades/lesson/{lesson_old_id}", {
    "student_ids": ["3", "4", "5"],
    "attendance": [""],
    "grades": ["5", "", ""],
    "comments": ["принесла домашнее задание"],
})
# The message says assessment sent to approval
req = con.execute("SELECT * FROM grade_change_requests").fetchall()
ok("GradeChangeRequest created") if len(req) == 1 else fail("no request", str(req))

# admin approves
aop = login(ADMIN, PW)
s, loc, _ = POST(aop, "/admin/grade_changes/approve", {"change_id": str(req[0]["id"])})
# verify grade updated
g = con.execute("SELECT value FROM grades WHERE id=? AND lesson_id=?", (req[0]["grade_id"], lesson_old_id)).fetchone()
ok("Grade value updated after approval") if g and g["value"] == "5" else fail("grade not updated", str(g))
st = con.execute("SELECT status FROM grade_change_requests WHERE id=?", (req[0]["id"],)).fetchone()
ok("Request marked approved") if st and st["status"] == "approved" else fail("status", str(st))

# --- 7. Pin limit (3 max) ---
print("\n=== Pin limit 3 ===")
for i in range(2, 5):
    POST(login(ADMIN, PW), "/admin/notifications/send", {
        "topic": f"Объявление {i}", "message": f"Сообщение номер {i}", "targets": ["student", "parent", "teacher"]
    })
for i in range(1, 5):
    POST(login(ADMIN, PW), "/admin/notifications/pin", {"notification_id": str(i)})
# user student petrov should have max 3 pins
sop = login("petrov", "pass123")
con2 = sqlite3.connect(DB)
con2.row_factory = sqlite3.Row
cnt = con2.execute("SELECT COUNT(*) c FROM pinned_notifications WHERE user_id=3").fetchone()["c"]
ok("Pinned notifications capped at 3") if cnt <= 3 else fail("pin cap", f"count={cnt}")

# --- 8. Admin pin list page ---
print("\n=== Admin notifications page renders pins ===")
s, html = GET(login(ADMIN, PW), "/admin/notifications")
ok("Notifications page ok") if s == 200 else fail("notif page")
ok("Pinned list shown") if "Закреплённые сообщения" in html else fail("pinned block", html[:200])

# --- 9. Holidays edit / schedule edit pencil ---
print("\n=== Edits ===")
h = con.execute("SELECT id FROM holidays LIMIT 1").fetchone()
s, loc, _ = POST(login(ADMIN, PW), "/admin/holidays/edit", {"holiday_id": str(h["id"]), "start_date": "2026-10-29", "end_date": "2026-11-07"})
ok("Holiday edited") if "/admin/holidays" in loc else fail("holiday edit")
s, loc, _ = POST(login(ADMIN, PW), "/admin/schedule/edit", {"entry_id": str(entry_ids[0]), "subject": "Алгебра", "teacher_id": "2", "room": "200"})
ok("Schedule entry edited") if "/admin/schedule" in loc else fail("schedule edit")

print("\n" + "=" * 50)
print(f"PASSED: {okn}/{okn + len(failn)}")
if failn:
    print("FAILED:", failn)
else:
    print("ALL DEEPER TESTS PASSED!")