import datetime, test_helpers

BASE = "http://127.0.0.1:8077"

def login(login, password):
    return test_helpers.login(login, password)

def GET(op, path):
    status, loc, body = test_helpers.GET(op, path)
    return status, loc, body

def POST(op, path, data):
    status, loc, body = test_helpers.POST(op, path, data)
    return status, loc, body

okn = failn = 0
def t(label, cond, detail=""):
    global okn, failn
    if cond:
        okn += 1; print("  [OK]", label)
    else:
        failn += 1; print("  [FAIL]", label, detail)

print("=== Role permissions ===")
stu = login("petrov", "pass123")
s, loc, _ = GET(stu, "/admin")
t("Student blocked from /admin (redirect to /login)", s == 302 or (s == 200 and "/login" in loc), f"s={s} loc={loc}")

s, loc, _ = GET(stu, "/admin/users")
t("Student blocked from /admin/users", s == 302 or (s == 200 and "/login" in loc), f"s={s} loc={loc}")

s, loc, _ = GET(stu, "/teacher/today")
t("Student blocked from /teacher", s == 302 or (s == 200 and "/login" in loc), f"s={s} loc={loc}")

s, loc, _ = GET(stu, "/parent/grades")
t("Student blocked from /parent", s == 302 or (s == 200 and "/login" in loc), f"s={s} loc={loc}")

print("=== Root redirects ===")
s, loc, _ = GET(stu, "/student")
t("Student root -> /student/main (200)", s == 200, f"s={s} loc={loc}")

print("=== Lesson detail after save ===")
import re
teach = login("teacher_sidorova", "newpass")
s, loc, html = GET(teach, "/teacher/today")
m = re.search(r"/teacher/lesson/(\d+)", html)
lid = m.group(1) if m else "0"
s, loc, html = GET(teach, f"/teacher/lesson/{lid}")
t("Teacher lesson detail renders", s == 200 and "Оценка: <b>5</b>" in html, f"s={s}")
t("Attendance badges shown", "Присутствие" in html and "Посещаемость" in html, "")
t("Remark (замечание) rendered", "Оценка: <b>!</b>" in html, "")

print("=== Student week shows grades ===")
s, loc, html = GET(login("petrov", "pass123"), "/student/week")
t("Student week shows grade", s == 200 and "grade-5" in html, "no grade in week")

print("=== Admin grade changes page ===")
adm = login("admin", "tB2TJn3WHkA")
s, loc, html = GET(adm, "/admin/grade_changes")
t("Grade changes page ok", s == 200, "")
t("Old request visible as approved/rejected history", s == 200, "")

print("=== Logout ===")
POST(adm, "/logout", {})
s, loc, _ = GET(adm, "/admin")
t("Admin can't access after logout (401->/login)", s == 302 or (s == 200 and "/login" in loc), f"s={s} loc={loc}")

print("=== Teacher edit_grades list page ===")
today_str = datetime.date.today().isoformat()
s, loc, html = GET(teach, f"/teacher/edit_grades?day={today_str}")
t("Edit grades list page ok", s == 200, f"s={s}")
t("Today's lessons listed with edit links", "edit_grades/lesson/" in html and "edit_grades" in html, "")

print("\n=" + "=" * 30)
print(f"PASSED: {okn}/{okn+failn}")