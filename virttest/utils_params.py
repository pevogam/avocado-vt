from threading import Lock

try:
    from collections import UserDict as IterableUserDict
except ImportError:
    from UserDict import IterableUserDict

from collections import OrderedDict

from avocado.core import exceptions
from six.moves import xrange


class ParamNotFound(exceptions.TestSkipError):
    pass


class Params(IterableUserDict):

    """
    A dict-like object passed to every test.
    """

    lock = Lock()

    def __getitem__(self, key):
        """overrides the error messages of missing params[$key]"""
        try:
            return IterableUserDict.__getitem__(self, key)
        except KeyError:
            raise ParamNotFound(
                "Mandatory parameter '%s' is missing. "
                "Check your cfg files for typos/mistakes" % key
            )

    def get(self, key, default=None):
        """overrides the behavior to catch ParamNotFound error"""
        try:
            return self[key]
        except ParamNotFound:
            return default

    def setdefault(self, key, failobj=None):
        if key not in self:
            self[key] = failobj
        return self[key]

    def objects(self, key):
        """
        Return the names of objects defined using a given key.

        :param key: The name of the key whose value lists the objects
                (e.g. 'nics').
        """
        lst = self.get(key, "").split()
        # remove duplicate elements
        objs = list({}.fromkeys(lst).keys())
        # sort list to keep origin order
        objs.sort(key=lst.index)
        del lst
        return objs

    def object_params(self, obj_name):
        """
        Return a dict-like object containing the parameters of an individual
        object.

        This method behaves as follows: the suffix '_' + obj_name is removed
        from all key names that have it.  Other key names are left unchanged.
        The values of keys with the suffix overwrite the values of their
        suffixless versions.

        :param obj_name: The name of the object (objects are listed by the
                objects() method).
        """
        suffix = "_" + obj_name
        self.lock.acquire()
        new_dict = self.copy()
        self.lock.release()
        for key in list(new_dict.keys()):
            if key.endswith(suffix):
                new_key = key.split(suffix)[0]
                new_dict[new_key] = new_dict[key]
        return new_dict

    def object_counts(self, count_key, base_name):
        """
        This is a generator method: to give it the name of a count key and a
        base_name, and it returns an iterator over all the values from params
        """
        count = self.get(count_key, 1)
        # Protect in case original is modified for some reason
        cpy = self.copy()
        for number in xrange(1, int(count) + 1):
            key = "%s%s" % (base_name, number)
            yield (key, cpy.get(key))

    def copy_from_keys(self, keys):
        """
        Return sub dict-like object by keys

        :param keys: white lists of key
        :return: dict-like object
        """
        new_dict = self.copy()
        new_dict.clear()
        for key in keys:
            if self.get(key):
                new_dict[key] = self.get(key)
        return new_dict

    def get_boolean(self, key, default=False):
        """
        Check if a config option is set to a default affirmation or not.

        :param key: config option key
        :type key: str
        :param bool default: whether to assume "yes" or "no" if param
                             does not exist (defaults to False/"no").
        :return whether option is set to 'yes'
        :rtype: bool
        """
        value = self.get(key, "yes" if default else "no")
        if value in ("yes", "on", "true"):
            return True
        if value in ("no", "off", "false"):
            return False
        raise ValueError("Cannot get boolean parameter value for %s: %s", key, value)

    def get_numeric(self, key, default=0, target_type=int):
        """
        Get numeric value converting to integer if necessary.

        :param str key: config option key
        :param int default: default numeric value
        :param type target_type: numeric type to return like int or float
        :return numerical type `target_type` converted parameter value
        :rtype: int or float
        """
        return target_type(self.get(key, default))

    def get_list(self, key, default="", delimiter=None, target_type=str):
        """
        Get a parameter value that is a character delimited list.

        :param str key: parameter whose value is list
        :param str default: default list value
        :param delimiter: character to split list items
        :type delimiter: str or None
        :param type target_type: type of each item, default is string
        :returns: empty list if if the key is not in the parameters
        :rtype: [str]

        .. note:: This an extension to the :py:func:`Params.objects` method as
          it allows for delimiters other than white space.
        .. seealso:: :py:func:`param_dict`
        """
        param_string = self.get(key, default)
        if not param_string:
            return []
        else:
            return [target_type(entry) for entry in param_string.split(delimiter)]

    def get_dict(self, key, default="", delimiter=None, need_order=False):
        """
        Get a param value that has the form 'name1=value1 name2=value2 ...'.

        :param str key: parameter whose value is dict
        :param str default: default dict value
        :param str delimiter: character to split list items
        :type delimiter: str or None
        :param bool need_order: whether to return an OrderedDict instead of
                                a regular dict
        :returns: empty dict if if the key is not in the parameters, a dict
                  or an ordered dictionary if the item order is important
        :rtype: {str: str}

        This uses :py:meth:`get_list` to convert the list entries to dict.
        """
        if need_order:
            result = OrderedDict()
        else:
            result = dict()
        for entry in self.get_list(key, default, delimiter):
            index = entry.find("=")
            if index == -1:
                raise ValueError(
                    'failed to find "=" in "{0}" (value for {1})'.format(entry, key)
                )
            result[entry[:index].strip()] = entry[index + 1 :].strip()
        return result

    def drop_dict_internals(self):
        """
        Drop internal keys which are not of our concern and
        return the modified params.

        :returns: parameters without the internal keys
        :rtype: {str, str}
        """
        return Params(
            {key: value for key, value in self.items() if not key.startswith("_")}
        )


def is_object_specific(key, param_objects):
    """
    Check if a parameter key is object specific.

    :param str key: key to be checked
    :param param_objects: parameter objects to compare against
    :type param_objects: [str]
    :returns: whether the parameter key is object specific
    :rtype: bool
    """
    for any_object_name in param_objects:
        if re.match(".+_%s$" % any_object_name, key):
            return True
    return False


def object_params(params, name, param_objects):
    """
    Prune all "_objname" params in the parameter dictionary,
    converting to general params for a preferred parameters object.

    :param params: parameters to be 'unobjectified'
    :type params: {str, str}
    :param str name: name of the parameters object whose parameters will be kept
    :param param_objects: the parameter objects to compare against
    :type param_objects: [str]
    :returns: general object-specific parameters
    :rtype: Params object
    """
    params = Params(params)
    object_params = params.object_params(name)
    for key in params.keys():
        if is_object_specific(key, param_objects):
            object_params.pop(key)
    return object_params


def objectify_params(params, name, param_objects):
    """
    Leave only "_objname" params in the parameter dictionary,
    converting general params and pruning params of different objects.

    :param params: parameters to be 'objectified'
    :type params: {str, str}
    :param str name: name of the parameters object whose parameters will be kept
    :param param_objects: the parameter objects to compare against
    :type param_objects: [str]
    :returns: specialized object-specific parameters
    :rtype: Params object

    This method is the opposite of the :py:func:`object_params` one.
    """
    objectified_params = Params(params)
    for key in params.keys():
        if not is_object_specific(key, param_objects):
            if objectified_params.get("%s_%s" % (key, name), None) is None:
                objectified_params["%s_%s" % (key, name)] = objectified_params[key]
            objectified_params.pop(key)
        elif not re.match(".+_%s$" % name, key):
            objectified_params.pop(key)
    return objectified_params


def merge_object_params(param_objects, param_dicts, objects_key="", main_object="", objectify=True):
    """
    Produce a single dictionary of parameters from multiple versions with possibly
    overlapping and conflicting parameters using object identifier.

    :param param_objects: parameter objects whose configurations will be combined
    :type param_objects: [str]
    :param param_dicts: parameter dictionaries for each parameter object
    :type param_dicts: [{str, str}]
    :param str objects_key: key for the merged parameter objects (usually vms)
    :param str main_object: the main parameter objects whose parameters will also be the default ones
    :param bool objectify: whether to objecctify the separate parameter dictionaries as preprocessing
    :returns: merged object-specific parameters
    :rtype: Params object

    The parameter containing the objects should also be specified so that it is
    preserved during the dictionary merge.

    Overlapping and conflicting parameters will be resolved if the objectify flag
    is set to True, otherwise we will assume all the parameters are objectified.
    """
    if main_object == "":
        main_object = param_objects[0]
    assert len(param_objects) == len(param_dicts), "Every parameter dictionary needs an object identifier"
    # turn into object appended parameters to make fully accessible in the end
    if objectify:
        for i in range(len(param_objects)):
            param_dicts[i] = objectify_params(param_dicts[i], param_objects[i], param_objects)
    merged_params = Params({})
    for param_dict in param_dicts:
        merged_params.update(param_dict)

    # collapse back identical parameters
    assert len(param_objects) >= 2, "At least two object dictionaries are needed for merge"
    main_index = param_objects.index(main_object)
    universal_params = object_params(param_dicts[main_index], param_objects[main_index], param_objects)
    # NOTE: remove internal parameters which don't concern us to avoid any side effects
    universal_params = universal_params.drop_dict_internals()
    for key in universal_params.keys():
        merged_params[key] = universal_params[key]
        for i in range(len(param_objects)):
            vm_key = "%s_%s" % (key, param_objects[i])
            objects_vm_key = "%s_%s" % (objects_key, param_objects[i])
            if merged_params[key] == merged_params.get(vm_key, None):
                merged_params.pop(vm_key)
            if vm_key == objects_vm_key and merged_params.get(vm_key, None) is not None:
                merged_params.pop(vm_key)

    merged_params[objects_key] = " ".join(param_objects)
    return merged_params


def multiply_params_per_object(params, param_objects):
    """
    Generate unique parameter values for each listed parameter object
    using its name.

    :param params: parameters to be extended per parameter object
    :type params: {str, str}
    :param param_objects: the parameter objects to multiply with
    :type param_objects: [str]
    :returns: multiplied object-specific parameters
    :rtype: Params object

    .. note:: If a `PREFIX` environment variable is set, the multiplied
        paramers will also be prefixed with its value. This is useful for
        performing multiple test runs in parallel.
    .. note:: Currently only implemented for vm objects.
    """
    multipled_params = Params(params)
    unique_keys = multipled_params.objects("vm_unique_keys")
    prefix = os.environ['PREFIX'] if 'PREFIX' in os.environ else 'at'
    for key in unique_keys:
        for name in param_objects:
            vmkey = "%s_%s" % (key, name)
            value = multipled_params.get(vmkey, multipled_params.get(key, ""))
            if value != "":
                # TODO: still need to handle better cases where a unique directory
                # is required (e.g. due to mount locations) like this one
                if key == "image_name" and ".lvm." in multipled_params["name"]:
                    multipled_params[vmkey] = "%s_%s/%s" % (prefix, name, value)
                else:
                    multipled_params[vmkey] = "%s_%s_%s" % (prefix, name, value)
    return multipled_params
