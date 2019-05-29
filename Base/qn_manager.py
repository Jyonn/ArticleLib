"""171203 Adel Liu

即将使用web前端直接上传到七牛 而无需通过服务器 减小服务器压力
"""
import qiniu
import requests
from django.http import HttpRequest
from qiniu import urlsafe_base64_encode, put_data, put_file, BucketManager

from Config.models import Config, CI
from SmartDjango import BaseError, ErrorCenter, Packing, E, Param

ACCESS_KEY = Config.get_value_by_key(CI.QINIU_ACCESS_KEY, 'YOUR-ACCESS-KEY')
SECRET_KEY = Config.get_value_by_key(CI.QINIU_SECRET_KEY, 'YOUR-SECRET-KEY')
PUBLIC_BUCKET = Config.get_value_by_key(CI.QINIU_PUBLIC_BUCKET, 'YOUR-PUBLIC-BUCKET')
PUBLIC_HOST = Config.get_value_by_key(CI.QINIU_PUBLIC_HOST, 'YOUR-PUBLIC-HOST')

_AUTH = qiniu.Auth(access_key=ACCESS_KEY, secret_key=SECRET_KEY)
_KEY_PREFIX = ''

QINIU_MANAGE_HOST = "https://rs.qiniu.com"


class QNError(ErrorCenter):
    UPLOAD_FAIL = E("上传出错", hc=500)
    REQUEST_QINIU = E("七牛请求错误", hc=500)
    QINIU_UNAUTHORIZED = E("七牛端身份验证错误", hc=403)
    FAIL_QINIU = E("未知原因导致的七牛端操作错误", hc=500)
    UNAUTH_CALLBACK = E("未经授权的回调函数", hc=403)


QNError.register()


class QnManager:
    def __init__(self, auth, bucket, cdn_host, public):
        self.auth = auth
        self.bucket = bucket
        self.cdn_host = cdn_host
        self.public = public
        self.bm = BucketManager(auth)

    def get_upload_token(self, key, policy):
        """
        获取七牛上传token
        :param policy: 上传策略
        :param key: 规定的键
        """
        key = _KEY_PREFIX + key
        return self.auth.upload_token(bucket=self.bucket, key=key, expires=3600, policy=policy), key

    @Packing.pack
    def auth_callback(self, request):
        """七牛callback认证校验"""
        if not isinstance(request, HttpRequest):
            return BaseError.STRANGE
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header is None:
            return QNError.UNAUTH_CALLBACK
        url = request.get_full_path()
        body = request.body
        verified = self.auth.verify_callback(auth_header, url, body,
                                             content_type='application/json')
        if not verified:
            return QNError.UNAUTH_CALLBACK

    def get_resource_url(self, key, expires=3600):
        """获取资源链接"""
        url = '%s/%s' % (self.cdn_host, key)
        if self.public:
            return '%s/%s' % (self.cdn_host, key)
        else:
            return self.auth.private_download_url(url, expires=expires)

    @staticmethod
    @Packing.pack
    def deal_manage_res(target, access_token):
        url = '%s%s' % (QINIU_MANAGE_HOST, target)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'QBox %s' % access_token,
        }

        try:
            r = requests.post(url, headers=headers)
        except requests.exceptions.RequestException:
            return QNError.REQUEST_QINIU
        status = r.status_code
        r.close()
        if status == 200:
            return
        elif status == 401:
            return QNError.QINIU_UNAUTHORIZED
        else:
            return QNError.FAIL_QINIU('状态错误%s' % status)

    def delete_res(self, key):
        entry = '%s:%s' % (self.bucket, key)
        encoded_entry = urlsafe_base64_encode(entry)
        target = '/delete/%s' % encoded_entry
        access_token = self.auth.token_of_request(target, content_type='application/json')
        return self.deal_manage_res(target, access_token)

    def move_res(self, key, new_key):
        entry = '%s:%s' % (self.bucket, key)
        encoded_entry = urlsafe_base64_encode(entry)
        new_entry = '%s:%s' % (self.bucket, new_key)
        encoded_new_entry = urlsafe_base64_encode(new_entry)
        target = '/move/%s/%s' % (encoded_entry, encoded_new_entry)
        access_token = self.auth.token_of_request(target, content_type='application/json')
        return self.deal_manage_res(target, access_token)

    @Packing.pack
    def upload_data(self, data, key):
        upload_token = self.auth.upload_token(bucket=self.bucket)
        try:
            ret = put_data(upload_token, key, data)
        except Exception as err:
            return QNError.UPLOAD_FAIL

    @Packing.pack
    def upload_file(self, filepath, key):
        upload_token = self.auth.upload_token(bucket=self.bucket)
        try:
            print(put_file(upload_token, key, filepath))
        except Exception as err:
            return QNError.UPLOAD_FAIL

    @Packing.pack
    def upload_url(self, url, key):
        try:
            self.bm.fetch(url, self.bucket, key)
        except Exception as err:
            return QNError.UPLOAD_FAIL


qn_manager = QnManager(_AUTH, PUBLIC_BUCKET, PUBLIC_HOST, public=True)
PM_KEY = Param('key', '七牛存储ID')
