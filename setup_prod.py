from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
u, _ = User.objects.get_or_create(username='admin')
u.set_password('admin123')
u.is_staff = True
u.is_superuser = True
u.save()
t, _ = Token.objects.get_or_create(user=u)
print('PRODUCTION TOKEN:', t.key)