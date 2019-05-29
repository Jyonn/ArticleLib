import datetime

from django.db import models
from django.db.models import Q

from SmartDjango.error import BaseError
from SmartDjango.packing import Packing


class Constraint:
    def __init__(self, field, _type, boundary=True, compare=None, template=None, max_min_fit=None):
        self.field = field
        self.type = _type
        self.boundary = boundary
        self.compare = compare or (lambda x: x)
        self.error_template = template or '{0} should %s than {1}'
        self.max_min_fit = max_min_fit or ('less', 'more')


CONSTRAINTS = [
    Constraint(
        models.CharField, str,
        template='{0}长度不应%s{1}字符',
        compare=lambda x: len(x),
        max_min_fit=('超过', '少于')
    ),
    Constraint(
        models.IntegerField, int,
        template='{0}不应%s{1}',
        max_min_fit=('大于', '小于')
    ),
    Constraint(models.DateTimeField, datetime.datetime, boundary=False),
    Constraint(models.DateField, datetime.date, boundary=False),
    Constraint(models.BooleanField, bool, boundary=False),
]


class SmartModel(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def get_fields(cls, field_names):
        field_dict = {}
        for o_field in cls._meta.fields:
            field_dict[o_field.name] = o_field

        fields = []
        for field_name in field_names:
            fields.append(field_dict.get(field_name))

        return tuple(fields)

    @classmethod
    def get_field(cls, field_name):
        return cls.get_fields([field_name])[0]

    @staticmethod
    def d_self(self):
        return self

    @classmethod
    def field_validator(cls, field):
        attr = field.name
        verbose = field.verbose_name
        cls_ = field.model

        @Packing.pack
        def _validator(value):
            for constraint in CONSTRAINTS:
                if isinstance(field, constraint.field):
                    if not isinstance(value, constraint.type):
                        return BaseError.FIELD_FORMAT('%s类型错误' % verbose)
                    if constraint.boundary:
                        max_l = getattr(cls_, 'MAX_L', None)
                        if max_l and attr in max_l and max_l[attr] < constraint.compare(value):
                            return BaseError.FIELD_FORMAT(
                                (constraint.error_template % constraint.max_min_fit[0]).format(
                                    verbose, max_l[attr]))
                        min_l = getattr(cls_, 'MIN_L', None)
                        if min_l and attr in min_l and constraint.compare(value) < min_l[attr]:
                            return BaseError.FIELD_FORMAT(
                                (constraint.error_template % constraint.max_min_fit[1]).format(
                                    verbose, min_l[attr]))
                    break

            if field.choices:
                choice_match = False
                for choice in field.choices:
                    if value == choice[0]:
                        choice_match = True
                        break
                if not choice_match:
                    return BaseError.FIELD_FORMAT('{0}不在可选择范围之内'.format(verbose))
        return _validator

    @classmethod
    @Packing.pack
    def validator(cls, attr_dict):
        if not isinstance(attr_dict, dict):
            return BaseError.FIELD_VALIDATOR
        if not isinstance(cls(), SmartModel):
            return BaseError.FIELD_VALIDATOR

        # 获取字段字典
        field_dict = dict()
        for o_field in cls._meta.fields:
            field_dict[o_field.name] = o_field

        # 遍历传入的参数
        for attr in attr_dict:
            attr_value = attr_dict[attr]
            if attr in field_dict:
                # 参数名为字段名
                attr_field = field_dict[attr]
            else:
                attr_field = None

            if isinstance(attr_field, models.Field):
                if attr_field.null and attr_value is None:
                    return
                if not attr_field.null and attr_value is None:
                    return BaseError.FIELD_FORMAT('%s不允许为空' % attr_field.verbose_name)
                ret = cls.field_validator(attr_field)(attr_value)
                if not ret.ok:
                    return ret

            # 自定义函数
            valid_func = getattr(cls, '_valid_%s' % attr, None)
            if valid_func and callable(valid_func):
                try:
                    ret = valid_func(attr_value)
                    if not ret.ok:
                        return ret
                except Exception:
                    return BaseError.FIELD_VALIDATOR(
                        '%s校验函数崩溃',
                        attr_field.verbose_name if isinstance(attr_field, models.Field) else attr)

    # @staticmethod
    def dictor(self, field_list):
        field_dict = dict()
        for o_field in self._meta.fields:
            field_dict[o_field.name] = o_field

        d = dict()
        for field in field_list:
            readable_func = getattr(self, '_readable_%s' % field, None)
            if readable_func and callable(readable_func):
                value = readable_func()
                d[field] = value
                continue

            if field not in field_dict:
                continue

            value = getattr(self, field, None)
            d[field] = value
        return d

    @classmethod
    def filtering(cls, *args, dictor=None, **kwargs):
        object_list = cls.objects.filter(*args, **kwargs)
        if callable(dictor):
            object_list = [dictor(o) for o in object_list]
        return object_list

    @classmethod
    def filter(cls, *args, dictor=None, **kwargs):
        if not isinstance(cls(), SmartModel):
            return BaseError.FIELD_VALIDATOR

        objects = cls.objects.all()

        field_dict = dict()
        for o_field in cls._meta.fields:
            field_dict[o_field.name] = o_field

        for q in args:
            if isinstance(q, Q):
                objects = objects.filter(q)

        for attr in kwargs:
            attr_value = kwargs[attr]

            if attr.endswith('__null'):
                attr = attr[:-6]
            elif attr_value is None:
                continue

            full = attr.endswith('__full')
            if full:
                attr = attr[:-6]

            filter_func = getattr(cls, '_filter_%s' % attr, None)
            if filter_func and callable(filter_func):
                o_filter = filter_func(attr_value)
                if isinstance(o_filter, dict):
                    objects = objects.filter(**o_filter)
                elif isinstance(o_filter, Q):
                    objects = objects.filter(o_filter)
                continue

            if attr in field_dict:
                attr_field = field_dict[attr]
            else:
                attr_field = None

            filter_dict = dict()
            if not full and \
                    (isinstance(attr_field, models.CharField) or
                     isinstance(attr_field, models.TextField)):
                filter_dict.setdefault('%s__contains' % attr, attr_value)
            else:
                filter_dict.setdefault(attr, attr_value)

            objects = objects.filter(**filter_dict)

        if dictor is not None:
            objects = [dictor(o) for o in objects]
        return objects
