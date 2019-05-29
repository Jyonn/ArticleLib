import json
import re
from functools import wraps

from django.db import models
from django.http import HttpRequest

from SmartDjango.arg import get_arg_dict
from SmartDjango.error import BaseError, ErrorCenter, E
from SmartDjango.packing import Packing
from SmartDjango.model import SmartModel


class RequestError(ErrorCenter):
    METHOD_NOT_MATCH = E("请求方法错误", hc=400)
    REQUEST_TYPE = E('请求体类型错误', hc=400)


RequestError.register()


class Param:
    class __NoDefault:
        pass

    class Classify:
        def dict(self):
            return self._dict

        def __init__(self, d):
            if not isinstance(d, dict):
                return
            self._dict = d

        def __getattr__(self, item):
            return self._dict.get(item)

    def __init__(self, name, verbose_name=None):
        self.name = name
        self._null = False
        self.verbose_name = verbose_name or name
        self.valid_func = []
        self.default = Param.__NoDefault()
        self.process_func = []

    def __str__(self):
        return 'Param %s(%s), default=%s' % (self.name, self.verbose_name, self.default)

    @staticmethod
    def dictor(o, field_list, string=True):
        d = dict()
        for field_name in field_list:
            value = getattr(o, field_name, None)
            if string:
                readable_func = getattr(o, '_readable_%s' % field_name, None)
                if readable_func and callable(readable_func):
                    value = readable_func()
            d[field_name] = value
        return d

    @staticmethod
    def from_fields(fields):
        params = []
        for field in fields:
            param = Param.from_field(field)
            params.append(param)
        return tuple(params)

    @staticmethod
    def from_field(field):
        param = Param(field.name, field.verbose_name)
        param._null = field.null
        param.valid_func.append(SmartModel.field_validator(field))
        class_ = field.model
        valid_func = getattr(class_, '_valid_%s' % field.name, None)
        if valid_func and callable(valid_func):
            param.valid_func.append(valid_func)
        return param

    @staticmethod
    def from_param(copied_param):
        param = Param(copied_param.name, copied_param.verbose_name)
        param.dft(copied_param.default)
        param._null = copied_param._null
        for valid_func in copied_param.valid_func:
            param.valid_func.append(valid_func)
        for process_func in copied_param.process_func:
            param.process_func.append(process_func)
        return param

    def base(self):
        return Param(self.name, self.verbose_name)

    @Packing.pack
    def do(self, value):
        if value is None:
            if self._null:
                return None
            if self.has_default():
                value = self.default
            else:
                return BaseError.MISS_PARAM((self.name, self.verbose_name))

        for func in self.valid_func:
            if isinstance(func, str):
                if not re.match(func, str(value)):
                    return BaseError.FIELD_FORMAT(self.verbose_name)
            elif callable(func):
                try:
                    ret = func(value)
                    if not ret.ok:
                        return ret
                except Exception:
                    return BaseError.FIELD_VALIDATOR

        for process in self.process_func:
            if callable(process):
                try:
                    ret = process(value)
                except Exception:
                    return BaseError.FIELD_PROCESSOR
                if isinstance(ret, Packing):
                    if not ret.ok:
                        return ret
                    value = ret.body
                else:
                    value = ret

        return value

    def valid(self, func):
        self.valid_func.append(func)
        return self

    def clear_valid(self):
        self.valid_func = []
        return self

    def process(self, func):
        self.process_func.append(func)
        return self

    def clear_process(self):
        self.process_func = []
        return self

    def dft(self, default):
        self.default = default
        return self

    def null(self):
        self._null = True
        return self

    def has_default(self):
        return not isinstance(self.default, Param.__NoDefault)

    @staticmethod
    @Packing.pack
    def _validator(param_list, param_dict):
        if not param_list:
            return
        for param in param_list:
            if isinstance(param, Param):
                value = param_dict.get(param.name)
                ret = param.do(value)
                if not ret.ok:
                    return ret
                param_dict[param.name] = ret.body
        return param_dict

    @staticmethod
    def require(b=None, q=None, a=None, method=None):
        """
        请求预先包装
        :param b: request.body
        :param q: request.query
        :param a: args and kwargs
        :param method: 请求方法
        :return: 在request.d中存放参数字典
        """

        def decorator(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                if not isinstance(request, HttpRequest):
                    return RequestError.REQUEST_TYPE
                if method and method != request.method:
                    return RequestError.METHOD_NOT_MATCH
                param_dict = dict()

                request.a_dict = get_arg_dict(func, args, kwargs)
                ret = Param._validator(a, request.a_dict)
                if not ret.ok:
                    return ret
                param_dict.update(ret.body or {})

                request.q_dict = request.GET.dict() or {}
                for q_key in request.q_dict:
                    try:
                        request.q_dict[q_key] = int(request.q_dict[q_key])
                    except Exception as err:
                        pass
                ret = Param._validator(q, request.q_dict)
                if not ret.ok:
                    return ret
                param_dict.update(ret.body or {})

                try:
                    request.b_dict = json.loads(request.body.decode())
                except json.JSONDecodeError:
                    request.b_dict = {}
                ret = Param._validator(b, request.b_dict)
                if not ret.ok:
                    return ret
                param_dict.update(ret.body or {})
                request.d = Param.Classify(param_dict)
                return func(request, *args, **kwargs)

            return wrapper

        return decorator
