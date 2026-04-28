from fastapi.testclient import TestClient
from backend.app.main import app
c = TestClient(app)
r = c.post('/api/login', json={'username':'teacher001','password':'123456','role':'teacher'})
t = r.json().get('token')
h = {'Authorization': 'Bearer ' + t}
g = c.get('/api/teacher/growth_archive', headers=h)
print(r.status_code, g.status_code)
print(sorted(list(g.json().keys())))
