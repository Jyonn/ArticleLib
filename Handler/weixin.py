import datetime

from bs4 import BeautifulSoup as Bs
from django.utils.crypto import get_random_string

from Base.grab import abstract_grab
from Base.qn_manager import qn_manager


class Weixin:
    def __init__(self, url):
        aid = get_random_string(length=6)
        crt_time = datetime.datetime.now().timestamp()
        html = abstract_grab(url)
        content = Bs(html, 'html.parser').find(id='img-content')
        images = content.find_all('img')
        for index, image in enumerate(images):
            if image.has_attr('data-src'):
                key = 'alib/%s/%s/%s' % (aid, crt_time, index)
                qn_manager.upload_url(image['data-src'], key)
                image['src'] = qn_manager.get_resource_url(key)
                del image['data-src']
        self.content = content

    def get_html(self):
        return str(self.content)
