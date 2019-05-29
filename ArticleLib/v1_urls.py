from django.urls import path, include

from Handler.views import WeixinView

urlpatterns = [
    path('weixin', WeixinView.as_view()),
]
