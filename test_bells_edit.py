import test_helpers as H

AD = H.admin_password()
op = H.login("admin", AD)
s, loc, body = H.GET(op, "/admin/bells")
print("GET /admin/bells:", s)
print("has form:", 'action="/admin/bells"' in body)
print("has existing rows:", "bell-input-row" in body)
s, loc, _ = H.POST(
    op,
    "/admin/bells",
    {"lesson_number": ["1", "2"], "start_time": ["09:00", "10:00"], "end_time": ["09:45", "10:45"]},
)
print("POST /admin/bells ->", s, loc)
top = H.login("teacher_sidorova", "newpass")
s, loc, body = H.GET(top, "/teacher/bells")
print("bells visible to teacher:", s, "09:00" in body, "10:45" in body)