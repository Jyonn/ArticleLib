import json
from functools import wraps

from django.http import HttpResponse

from SmartDjango.error import BaseError, ETemplate, EInstance, ErrorCenter


class Packing:
    """
    函数返回类（规范）
    用于模型方法、路由控制方法等几乎所有函数中
    """

    def __init__(self, *args, **kwargs):
        """
        函数返回类构造器，根据变量个数判断
        """
        if not args:
            self.error = BaseError.OK
        else:
            arg = args[0]
            if isinstance(arg, ETemplate):
                self.error = arg()
            elif isinstance(arg, EInstance):
                self.error = arg
            elif isinstance(arg, Packing):
                self.error = arg.error
                self.body = arg.body
                self.extend = arg.extend
            else:
                self.error = BaseError.OK()
                self.body = args[0]
        self.extend = self.extend or kwargs

    def __getattribute__(self, item):
        if item == 'ok':
            return object.__getattribute__(self, '_ok')()
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            return None

    def __str__(self):
        return 'Ret(error=%s, body=%s, extend=%s)' % (self.error, self.body, self.extend)

    def _ok(self):
        return self.error.e.eid == BaseError.OK.eid

    def erroris(self, e):
        return self.error.e.eid == e.eid

    @staticmethod
    def pack(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return Packing(func(*args, **kwargs))
        return wrapper

    @staticmethod
    def http_pack(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ret = Packing(func(*args, **kwargs))
            error = ret.error
            if error.append_msg:
                if error.e.ph == ETemplate.PH_NONE:
                    msg = error.e.msg + '，%s' % error.append_msg
                elif error.e.ph == ETemplate.PH_FORMAT:
                    msg = error.e.msg.format(*error.append_msg)
                else:
                    msg = error.e.msg % error.append_msg
            else:
                msg = error.e.msg
            resp = dict(
                identifier=ErrorCenter.r_get(error.e.eid),
                statusCode=error.e.eid,
                msg=msg,
                body=ret.body,
            )
            return HttpResponse(
                json.dumps(resp, ensure_ascii=False),
                status=error.e.hc,
                # status=200,
                content_type="application/json; encoding=utf-8",
            )

        return wrapper

    @staticmethod
    def safe_unpack(ret, default=None):
        return ret.body if ret.ok else default
