import urllib.request, http.cookiejar, urllib.parse, json
import test_helpers

BASE = "http://127.0.0.1:8077"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

ADMIN = "admin"
PW = test_helpers.admin_password()

passed = []
failed = []

def ok(label):
    passed.append(label)
    print("  [OK]", label)

def fail(label, detail=""):
    failed.append(label)
    print("  [FAIL]", label, detail)


def GET(path):
    r = opener.open(BASE + path)
    return r.status, r.read()

def POST(path, data):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        r = opener.open(req)
        return r.status, r.geturl(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("location", ""), e.read()


# --- Login flow ---
print("=== Login ===")
s, _ = GET("/login")
ok("GET /login -> 200") if s == 200 else fail("GET /login")

s, loc, _ = POST("/login", {"login": ADMIN, "password": "wrong"})
ok("Wrong password -> 401") if s == 401 else fail("Wrong password")

s, loc, _ = POST("/login", {"login": ADMIN, "password": PW})
ok("Login OK -> redirect /setup/bells") if "/setup/bells" in loc else fail("Login redirect", loc)


# --- Bell setup ---
print("\n=== Bell setup ===")
s, _ = GET("/setup/bells")
ok("GET /setup/bells -> 200") if s == 200 else fail("GET /setup/bells")

s, loc, _ = POST("/setup/bells", {
    "lesson_number": ["1","2","3","4","5","6"],
    "start_time": ["08:00","09:00","10:00","11:00","12:00","13:00"],
    "end_time": ["08:45","09:45","10:45","11:45","12:45","13:45"],
})
ok("Bells saved -> redirect /admin") if "/admin" in loc else fail("Bells redirect", loc)


# --- Dashboard ---
print("\n=== Dashboard ===")
s, body = GET("/admin")
ok("Dashboard renders") if s == 200 else fail("Dashboard")


# --- Create teacher ---
print("\n=== Create users ===")
s, loc, body = POST("/admin/users/create", {
    "role": "teacher",
    "full_name": "Сидорова Анна Михайловна",
    "phone": "+79001112233",
    "birth_date": "1992-01-15",
    "login": "teacher_sidorova",
    "password": "pass123",
    "group_name": "9Б",
})
ok("Teacher created") if s == 200 else fail("Create teacher")

# Create students
students = [("Петров Пётр Алексеевич", "petrov", "2008-03-10"), ("Сидоров Дмитрий Игоревич", "sidorov", "2008-07-22"), ("Козлова Мария Сергеевна", "kozlova", "2008-12-05")]
for name, login, bd in students:
    s, loc, body = POST("/admin/users/create", {
        "role": "student", "full_name": name, "phone": "+7900" + login[:4] + "0000",
        "birth_date": bd, "login": login, "password": "pass123", "group_name": "9Б"
    })
    ok(f"Student {login} created") if s == 200 else fail(f"Create student {login}")

# Create parent
s, loc, body = POST("/admin/users/create", {
    "role": "parent", "full_name": "Петрова Елена Владимировна",
    "phone": "+79005556677", "birth_date": "1980-06-01",
    "login": "petrova_mama", "password": "pass123",
    "group_name": "9Б", "child_id": "2"
})
ok("Parent created and linked") if s == 200 else fail("Create parent")


# --- Users list ---
print("\n=== Users list ===")
s, body = GET("/admin/users")
ok("Users page renders") if s == 200 else fail("Users page")


# --- Edit user ---
print("\n=== Edit user ===")
s, loc, body = POST("/admin/users/edit", {
    "user_id": "2", "login": "teacher_sidorova", "password": "newpass",
    "group_name": "9Б", "all_groups_access": "1"
})
ok("Teacher edited (all_groups_access)") if "/admin/users" in loc else fail("Edit teacher", loc)


# --- Notifications ---
print("\n=== Notifications ===")
s, loc, body = POST("/admin/notifications/send", {
    "topic": "Родительское собрание",
    "message": "20 сентября состоится собрание. Начало в 18:00. Ждём всех родителей.",
    "targets": ["teacher", "student", "parent"]
})
ok("Notification sent") if "/admin/notifications" in loc else fail("Send notification")

s, loc, body = POST("/admin/notifications/pin", {"notification_id": "1"})
ok("Notification pinned") if "/admin/notifications" in loc else fail("Pin notification")


# --- Schedule ---
print("\n=== Schedule ===")
s, loc, body = POST("/admin/schedule/add", {
    "day": "0",  # Monday
    "group_id": "1",
    "subjects": ["Математика", "Русский язык", "Физика"],
    "teacher_ids": ["2", "2", "2"],
    "rooms": ["301", "302", "303"]
})
ok("Schedule added for Monday 9Б") if "/admin/schedule" in loc else fail("Add schedule")

s, body = GET("/admin/schedule?day=0")
ok("Schedule page renders") if s == 200 else fail("Schedule page")


# --- Holidays ---
print("\n=== Holidays ===")
s, loc, body = POST("/admin/holidays/add", {"start_date": "2026-10-28", "end_date": "2026-11-06"})
ok("Holiday added") if "/admin/holidays" in loc else fail("Add holiday")


# --- Settings ---
print("\n=== Settings ===")
s, loc, body = POST("/admin/settings/save", {"grade_edit_days": "7", "grade_admin_edit_days": "14"})
ok("Settings saved") if "/admin/settings" in loc else fail("Save settings")


# --- Login as teacher ---
print("\n=== Teacher portal ===")
# logout
cj.clear()
s, loc, _ = POST("/login", {"login": "teacher_sidorova", "password": "newpass"})
ok("Teacher login OK") if "/teacher" in loc or s == 200 else fail("Teacher login", loc)

s, body = GET("/teacher")
ok("Teacher main") if s == 200 else fail("Teacher main")

s, body = GET("/teacher/today")
ok("Teacher today") if s == 200 else fail("Teacher today")

s, body = GET("/teacher/week")
ok("Teacher week schedule") if s == 200 else fail("Teacher week")

s, body = GET("/teacher/bells")
ok("Teacher bells") if s == 200 else fail("Teacher bells")

s, body = GET("/teacher/students")
ok("Teacher students list") if s == 200 else fail("Teacher students")

s, body = GET("/teacher/parents")
ok("Teacher parents") if s == 200 else fail("Teacher parents")

s, body = GET("/teacher/edit_grades")
ok("Teacher edit grades page") if s == 200 else fail("Teacher edit grades")


# --- Login as student ---
print("\n=== Student portal ===")
cj.clear()
s, loc, _ = POST("/login", {"login": "petrov", "password": "pass123"})
ok("Student login OK") if "/student" in loc else fail("Student login", loc)

s, body = GET("/student")
ok("Student main") if s == 200 else fail("Student main")

s, body = GET("/student/today")
ok("Student today") if s == 200 else fail("Student today")

s, body = GET("/student/week")
ok("Student week") if s == 200 else fail("Student week")

s, body = GET("/student/bells")
ok("Student bells") if s == 200 else fail("Student bells")

s, body = GET("/student/grades")
ok("Student grades") if s == 200 else fail("Student grades")


# --- Login as parent ---
print("\n=== Parent portal ===")
cj.clear()
s, loc, _ = POST("/login", {"login": "petrova_mama", "password": "pass123"})
ok("Parent login OK") if "/parent" in loc else fail("Parent login", loc)

s, body = GET("/parent")
ok("Parent main") if s == 200 else fail("Parent main")

s, body = GET("/parent/today")
ok("Parent today") if s == 200 else fail("Parent today")

s, body = GET("/parent/week")
ok("Parent week") if s == 200 else fail("Parent week")

s, body = GET("/parent/bells")
ok("Parent bells") if s == 200 else fail("Parent bells")

s, body = GET("/parent/grades")
ok("Parent grades") if s == 200 else fail("Parent grades")


# --- Summary ---
print("\n" + "=" * 50)
print(f"PASSED: {len(passed)}/{len(passed)+len(failed)}")
if failed:
    print(f"FAILED: {failed}")
else:
    print("ALL TESTS PASSED!")


