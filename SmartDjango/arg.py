import inspect


def get_arg_dict(func, args, kwargs):
    arg_dict = dict()
    for parameter in inspect.signature(func).parameters:
        o_param = inspect.signature(func).parameters[parameter]
        arg_dict[parameter] = o_param.default
    args_name = list(inspect.signature(func).parameters.keys()) + list(kwargs.keys())
    arg_dict.update(dict(zip(args_name, args)))
    arg_dict.update(kwargs)
    return arg_dict
