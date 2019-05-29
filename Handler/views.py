from django.views import View

from Handler.weixin import Weixin
from SmartDjango import Param, Packing


class WeixinView(View):
    @staticmethod
    @Packing.http_pack
    @Param.require([Param('url', '微信公众号文章链接')])
    def post(request):
        url = request.d.url
        content = Weixin(url).get_html()
        return dict(content=content)
