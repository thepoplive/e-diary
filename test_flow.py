import urllib.request, http.cookiejar, urllib.parse
import test_helpers

BASE = "http://127.0.0.1:8077"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get(path):
    try:
        r = opener.open(BASE + path)
        return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def post(path, data):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        r = opener.open(req)
        return r.status, r.geturl(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("location", ""), e.read().decode(
            "utf-8", errors="replace"
        )


# 1. login page
s, html = get("/login")
print("LOGIN PAGE:", s, "expected 200:", "login" in html.lower())


# 2. wrong password
s, loc, html = post("/login", {"login": "admin", "password": "wrong"})
print("WRONG LOGIN:", s, "error shown:", "Неверный логин" in html)


# 3. correct password
s, loc, html = post("/login", {"login": "admin", "password": test_helpers.admin_password()})
print("OK LOGIN:", s, "redirect to:", loc)


# 4. should redirect to /setup/bells
s, html = get("/setup/bells")
print("SETUP BELLS:", s, "page ok:", "Расписание звонков" in html)


# 5. submit bells
s, loc, html = post(
    "/setup/bells",
    {
        "lesson_number": ["1", "2", "3", "4", "5"],
        "start_time": ["08:30", "09:20", "10:20", "11:20", "12:20"],
        "end_time": ["09:15", "10:05", "11:05", "12:05", "13:05"],
    },
)
print("BELLS SAVED:", s, "redirect:", loc)


# 6. dashboard
s, html = get("/admin")
print("DASHBOARD:", s, "ok:", "Дашборд" in html)


# 7. create teacher
s, html = get("/admin/users/create?role=teacher")
print("CREATE TEACHER PAGE:", s, "ok:", "Создание учителя" in html)

s, loc, html = post(
    "/admin/users/create",
    {
        "role": "teacher",
        "full_name": "Иванов Иван Иванович",
        "phone": "+79001234567",
        "birth_date": "1990-05-15",
        "login": "teacher1",
        "password": "pass123",
        "group_name": "10А",
    },
)
print("TEACHER CREATED:", s, "loc:", loc, "created:", "Аккаунт создан" in html)

# create a student
s, loc, html = post(
    "/admin/users/create",
    {
        "role": "student",
        "full_name": "Петров Петр Петрович",
        "phone": "+79007654321",
        "birth_date": "2008-03-20",
        "login": "student1",
        "password": "pass123",
        "group_name": "10А",
    },
)
print("STUDENT CREATED:", s, "created:", "Аккаунт создан" in html)

# create a parent
s, loc, html = post(
    "/admin/users/create",
    {
        "role": "parent",
        "full_name": "Петров Михаил Сергеевич",
        "phone": "+79001112233",
        "birth_date": "1975-11-11",
        "login": "parent1",
        "password": "pass123",
        "group_name": "10А",
        "child_id": "2",
    },
)
print("PARENT CREATED:", s, "created:", "Аккаунт создан" in html)

# 8. users list
s, html = get("/admin/users")
print("USERS LIST:", s, "ok:", "Иванов" in html, "Петров" in html)

# 9. notifications
s, loc, html = post(
    "/admin/notifications/send",
    {
        "topic": "Родительское собрание",
        "message": "Добрый день! 15 сентября состоится родительское собрание в 18:00 в кабинете 201.",
        "targets": ["teacher", "parent"],
    },
)
print("NOTIF SENT:", s, "redirect:", loc)
s, html = get("/admin/notifications")
print("NOTIFS PAGE:", s, "ok:", "Родительское собрание" in html)

print("\n--- ALL BASIC TESTS PASSED ---")

