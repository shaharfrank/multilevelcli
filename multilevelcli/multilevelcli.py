#!/usr/bin/env python3
import sys
import textwrap
import traceback

debugfn = None      # Set to a fn(str) to enable the internal debugging.

# Use the debug function if set.
def debug(str):
    if debugfn:
        debugfn(str)

unicode=type(str)

class Namespace(object):
    """
    Generic namespace, similar to dict but enables also field references (e.g. ns.x = 4).
    """
    def __init__(self):
        pass

    def __iter__(self):
        for t in self.__dict__:
            yield t

    def next(self):
        for t in self.__dict__:
            yield t

    def __getitem__(self, item, default=None):
        '''
        Lookup for item with support for nested '.' notation.
        :param item:
        :param default:
        :return:
        '''
        if item in self.__dict__:
            return self.__dict__.get(item)
        # generate a sub ns
        ns = Namespace()
        item += "."
        for k in self.__dict__:
            if k.startswith(item):
                ns[k[len(item):]] = self.__dict__[k]
        if not ns:
            return None
        return ns

    def __setitem__(self, item, value):
        return self.__dict__.__setitem__(item, value)

    def __getattr__(self, item):
        return self.__getitem__(item)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)

class CliResult(object):
    """
    CLI parsing results object.
    3 main sub entities are maintained:
    - The unified parsed name space with all options and arguments as flat namespace, where each argument is a
      full name (i.e. class.subclass.command...).
    - A seperated namespace for each level
    - A group, command, args, option accessor for the command/last level.
    """
    def __init__(self):
        self.__command = None
        self.__command_arguments = []
        self.__command_options = {}
        self.__group = None
        self.__ns = Namespace()
        self.__args_ns = Namespace()
        self.__levels_ns = [Namespace()]
        self.__max_level = 0
        self.__left_tokens = []
        self.__ctx = None   # user defined command level context
        pass

    def set_group(self, group):
        """
        Set the active group (last level) during the parsing.
        :param group:
        :return:
        """
        assert isinstance(group, MultiLevelCliBase.GroupType)
        self.__group = group

    def set_command(self, cmd, ctx=None):
        """
        Set the active command during the parsing
        :param cmd:
        :return:
        """
        assert isinstance(cmd, MultiLevelCliBase.CommandType)
        self.__command = cmd
        self.__ctx = ctx

    def command_ctx(self):
        return self.__ctx

    def add_command_arg(self, arg, val):
        assert isinstance(arg, MultiLevelCliBase.ArgType)
        self.__command_arguments.append(arg)
        self.__args_ns[arg.name] = val

    def init_level(self, level):
        """
        Check that the level of the command/group is sane.
        :param level: the level of the checked entity. It must be <= max level + 1
        :return:
        """
        if level > self.__max_level + 1:
            raise ParseExecption("validate_level at level %s has bad level (max %d)" % (level, self.__max_level))
        if level > self.__max_level:
            ns = Namespace()
            self.__levels_ns.append(Namespace())
            self.__max_level += 1

    def set_command_options(self, level, name, opt, val):
        """
        Record the command options found during the parsing the the given level.
        init_level() must be called before any call to this function for every level.
        :param level: The target level. must be <= max level + 1
        :param name: Name of the options (See MultiLevelCliBase.OptionType)
        :param opt: The option structure
        :param val: The option value.
        :return:
        """
        assert isinstance(opt, MultiLevelCliBase.OptionType)
        assert isinstance(name, (str,unicode))
        if level > self.__max_level:
            raise ParseExecption("set_command_options at level %s name %s has bad level (max %d)" % (level, name, self.__max_level))
        self.__command_options[name] = opt
        self.__levels_ns[level][name] = val

    def __setitem__(self, item, value):
        return self.__ns.__setitem__(item, value)

    def __getitem__(self, item, default=None):
        return self.__ns.__getitem__(item, default)

    def __getattr__(self, item):
        return self.__ns[item]

    def levels(self):
        """
        Return all levels namespaces.
        :return: array of namespaces, one per each level.
        """
        return self.__levels_ns

    def ns(self, level=None):
        """
        Return the last level (command or group) namespace or the specified level namespace.
        :param level: optional level. Default - the unified namespace.
        :return: Namespace.
        """
        if level is None:
            return self.__ns
        else:
            return self.__levels_ns[level]

    def group(self):
        """
        Returns the last level group.
        :return: Group object.
        """
        return self.__group

    def command(self):
        """
        Returns the last level command (if any).
        :return: Command object or None of no command is parsed.
        """
        return self.__command

    def command_name(self):
        return self.__command.full_name(".") if self.__command else ""

    def args(self):
        """
        Returns the arguments of the command if any.
        :return: Namespace. Empty if no command is found.
        """
        return self.__args_ns

    def opt(self):
        """
        Returns the options of the last level (command or otherwise).
        :return:
        """
        return self.__levels_ns[self.__max_level]

    def set_unparsed_tokens(self, tokens):
        """
        Set the tokens that can't be parsed.
        :param tokens:
        :return:
        """
        self.__left_tokens = tokens

    def unparsed_tokens(self):
        return self.__left_tokens

    def __str__(self):
        """
        Returns a string describing the command, command group and the arguments/options if any.
        :return:
        """
        return "[%s] [Group '%s'] %s" % (self.__command.full_name(".") if self.__command else "",
                                         str(self.__group) if self.__group else "", str(self.__ns))


class ParseExecption(Exception):
    def __init__(self, description):
        Exception.__init__(self)
        self.description = description
        self.trace = traceback.format_exc()

    def __str__(self):
        return "%s. Use --help to get usage." % (self.description)


class OptionNotFound(ParseExecption):
    pass


class OptionNoParam(ParseExecption):
    pass


class ArgumentTypeError(ParseExecption):
    pass


class ArgumentKeyError(ParseExecption):
    pass


class NoCommand(ParseExecption):
    pass


class CommandMissingArguments(ParseExecption):
    pass


class HelpRquired(ParseExecption):
    pass


class UnknownToken(ParseExecption):
    pass


def usage_and_exit(ent):
    assert isinstance(ent, MultiLevelCliBase.ParseBase)
    print (ent.usage())
    sys.exit(1)


def usage_and_raise_help(ent):
    assert isinstance(ent, MultiLevelCliBase.ParseBase)
    print (ent.usage())
    raise HelpRquired("Help requested for entity %s" % str(ent.full_name(".")))


def usage_help_and_raise_nocommand(ent):
    assert isinstance(ent, MultiLevelCliBase.ParseBase)
    print (ent.usage())
    raise NoCommand("Help requested, no command. Entity %s" % str(ent.full_name(".")))


def raise_no_command(grp):
    assert isinstance(grp, MultiLevelCliBase.GroupType)
    raise NoCommand("no command is specified after parsing group '%s'" % (grp.full_name(".")))


def usage_and_raise_no_command(grp):
    assert isinstance(grp, MultiLevelCliBase.GroupType)
    print (grp.usage())
    raise NoCommand("no command is specified after parsing group '%s'" % (grp.full_name(".")))


# The module's default help function. Can be set to make all cli objects to use a user function.
# The function should be fn(MultiLevelCliBase.ParseBase)
defhelpfn=usage_and_exit

# utility function wrapper for defhelpfn - used for class time initialization defaults
def _defhelpfn(ent):
    assert isinstance(ent, MultiLevelCliBase.ParseBase)
    defhelpfn(ent)


class MultiLevelCliBase(object):
    helpwidth = 80
    prog = ""

    @staticmethod
    def tokenize(s, sep = None, grouping = ['[', '{'], escaping = ['\\'], quoting= ['"', '\'']):
        '''
        Split the given string to tokens with grouping, escaping and quoting support.
        :param s: The string to parse.
        :param sep: arrays of seperator chars. None means use isspace().
        :param grouping: array of grouping chars. Groups and nested gropus are always one token.
                The default grouping chars are [ {
        :param escaping: array of escape chars. The character after the escape char is always treated as normal char.
                The default escaping char is:  \
        :param quoting: array of quoting chars. Quoted text is always parse an one token. Special chars are ignored,
                short of the escape char that can be used to escape the quoting char itself.
                The default quoting chars are ' "
        :return: array of sting tokens.
        '''
        ends = { '[' : ']', '{' :'}'}
        tokens = []
        groups = [] # items: tne end marker of the group. Each nested group will lead to another item.
        quoted = None
        cur = ""
        escape = False
        for c in s:
            if escape:
                cur += c
                escape = False
                continue
            if c in escaping:
                cur += c
                escape = True
                continue

            # if we start or end quating, remove the quote marker, else just add it
            if c in quoting and not groups:
                if quoted and quoted == c:
                    quoted = None
                elif not quoted:
                    quoted = c
                cur += c
                continue

            if quoted:
                cur += c
                continue

            if c in grouping and (not c in groups):
                groups.append(ends[c])
                cur += c
                continue

            if groups and c == groups[-1]:
                del groups[-1]
                cur += c
                continue

            if not groups and (str(c).isspace() if sep is None else c in sep):
                token = cur.strip()
                if not token:
                    continue
                tokens.append(token)
                cur = ""
                continue

            cur += c

        if cur:
            token = cur.strip()
            if token:
                tokens.append(token)
        if groups:
            raise ParseExecption("'%s' - the following groups are unbalanced '%s'" % (s, str(groups)))
        if quoted:
            raise ParseExecption("'%s' - the following quoting is not balanced '%s'" % (s, str(quoted)))
        return tokens

    class ParseBase(object):
        """
        Base object for comamnds and groups. Shouldn't be used directly.
        """
        def __init__(self, name, parent, description, helpfn):
            debug("Add name '%s' parent '%s' description '%s', defhelpfn '%s'" % (name, parent, description, helpfn))
            assert parent is None or self.valid_name(name)
            assert parent is None or isinstance(parent, MultiLevelCliBase.ParseBase)
            assert description is None or isinstance(description, (str,unicode))
            assert helpfn is None or callable(helpfn)
            self.name = name
            self.parent = parent
            self.level = self.__level(0)    # must be set after self.parent
            self.description = description
            self.options = {}
            self.longoptions = {}
            self.helpfn = helpfn
            if helpfn:
                self.add_option("h", "help", description="help screen (this screen)")

        def __level(self, level):
            if self.parent is None:
                return level
            return self.parent.__level(level+1)

        def __str__(self):
            return self.name

        def urlvalid(self, s):
            for c in s:
                if not c.isalnum() and not c in ["-"]:
                    return False
            if not s:
                return False
            return True

        def valid_name(self, name):
            """ checks if the given name string is a valid name """
            assert isinstance(name, (str,unicode))
            name = name.replace("_","")
            # "_" are allowed, but at least the first non _ char must be alpha
            valid = name and self.urlvalid(name)
            debug("NON valid '%s'" % name)
            if not valid:
                debug("NON valid '%s'" % name)
            return valid


        def full_name(self, sep = " ", lastsep=False):
            """
            Returns full qualified name of the object e.g. "class<sep>subclass<sep>command"
            :param sep: The seperator to be used between levels.
            :param lastsep: Should add a seperator at the end of the name?
            :return: the name string
            """
            if not self.parent:
                return ""
            return self.parent.full_name(sep, lastsep=True) + self.name + (sep if lastsep else "")

        def add_option(self, short, long = None, name=None, type=None, description=None, default=None):
            """
            Add an option to the current command/group. Options may have short name and/or long name. In addition if
            'name' is provided it is used as the target name. If name is not given then the long name is used,
            and if this is also not provided, the short name is used.
            :param short: the optional short name.
            :param long: the optional long name.
            :param name: the optional target (namespace variable) name. See above for the name resolution.
            :param type: the python type of the argument or None if the option is a flag. The type must be one that
                    supports conversion from string to it.
            :param description: an optional description to be used in the help/usage screens.
            :param default: an optional value to be used if the option is not provided. The default must be of the same
                    type of the opttype.
            :return: the new option object.
            """
            if not name:
                name = long if long else short
            return self.__add_option(MultiLevelCliBase.OptionType(short, long, self, name=name, opttype=type, description=description, default=default))

        def __add_option(self, opt):
            assert isinstance(opt, MultiLevelCliBase.OptionType)
            assert not opt.short or not opt.short in [x.short for x in self.options.values()]
            assert not opt.long or not opt.long in [x.long for x in self.longoptions.values()]
            if opt.short:
                self.options[opt.short] = opt
            if opt.long:
                self.longoptions[opt.long] = opt
            return opt

        def parse_option(self, cli, optname, tokens, long=False):
            """
            Parse the given option 'optname' using the 'tokens' in the current (command/group) context.
            :param cli: the CLI result object.
            :param optname: the option name as it is provided in the command line
            :param tokens: the command line tokens starting from optname.
            :param long: If true the option is looked up as long option, otherwise it is assumed to be short.
            :return: The number of tokens consumed.
            """
            try:
                opt = self.longoptions[optname] if long else self.options[optname]
            except Exception:
                raise OptionNotFound("Option %s%s not found" % (self.parent.full_name(".", lastsep=True) if self.parent else "",optname))
            assert isinstance(opt, MultiLevelCliBase.OptionType)
            if opt.argtype is not None and not tokens:
                raise OptionNoParam("Option %s requires a parameter" % optname)
            tokens = opt._parse(cli, self.full_name(".", lastsep=True), tokens[1:])
            if self.helpfn and cli.ns(self.level)["help"]:
                self.helpfn(self)
            return tokens

        def set_defaults(self, cli):
            """
            Set the options defaults for this level.
            :param cli:
            :return:
            """
            assert isinstance(cli, CliResult)
            cli.init_level(self.level)
            # if set, use longname as var name
            for o in self.longoptions.values():
                val = o.default if (o.argtype is not None or o.default is not None) else False
                cli[self.full_name(".", lastsep=True) + o.name] = val
                cli.set_command_options(self.level, o.name, o, val)
            # process options that have only short version
            for o in self.options.values():
                if o not in self.longoptions.values():
                    val = o.default if (o.argtype is not None or o.default is not None) else False
                    if o.default is not None:
                        cli[self.full_name(".", lastsep=True) + o.name] = val
                        cli.set_command_options(self.level, o.name, o, val)

    class ArgType(object):
        """
        An object representing a single command argument.
        In most cases this shouldn't be used directly.
        argtype is either a terminal type: int, str, float, etc., array [], or struct {}.
        Nested types are supported. For example [ { key1 : int, key2 : str, key2 : [int] } ]
        """

        def check_type(self, argtype):
            assert isinstance(argtype, (type, list, dict, MultiLevelCliBase.ArgType))

        def __init__(self, name, parent, type=str, description=None):
            assert isinstance(name, (str, unicode))
            #print ("ArgType: %s" % argtype)
            assert isinstance(parent, (MultiLevelCliBase.ParseBase, MultiLevelCliBase.ArgType, MultiLevelCliBase.OptionType))
            self.name = name
            self.argtype = type
            self.check_type(self.argtype)
            self.description = description
            self.parent = parent

        def _parse(self, cli, arg):
            assert isinstance(cli, CliResult)
            try:
                if isinstance(self.argtype, MultiLevelCliBase.ArgType):
                    nested = CliResult()
                    self.argtype._parse(nested, arg)
                    val = nested.args()[self.argtype.name]
                else:
                    val = (self.argtype)(MultiLevelCliBase.strip(arg))
                cli[self.full_name(".", lastsep=True) + self.name] = val
                cli.add_command_arg(self, val)
            except Exception:
                raise ArgumentTypeError("Parse error at token '%s' [arg %s], can't convert to type %s" % (
                    arg, self.full_name(".", lastsep=True) + self.name, self.argtype))
            return 1  # consume only optname

        def full_name(self, sep, lastsep=True):
            return self.parent.full_name(sep, lastsep)

        def type_name(self):
            if isinstance(self.argtype, MultiLevelCliBase.ArgType):
                return self.argtype.type_name()
            if self.argtype is not None:
                return " <%s>" % self.argtype.__name__
            return ""


    @staticmethod
    def nested_type(name, parent, argtype):
        if type(argtype) == list:
            return MultiLevelCliBase.ListType(name + ".array", parent, argtype)
        if type(argtype) == dict:
            return MultiLevelCliBase.StructType(name + ".struct", parent, argtype)
        else:
            return argtype

    class ListType(ArgType):
        """
        An object representing a list command argument.
        In most cases this shouldn't be used directly.
        """
        def __init__(self, name, parent, argtype, description=None):
            assert isinstance(argtype, list)
            if not argtype:
                argtype = str   # arrays of sting
            elif len(argtype) > 1:
                raise ArgumentTypeError("ListType: multiple types in array are not supported for token '%s' - '%s'" % (name, argtype))
            argtype = MultiLevelCliBase.nested_type(name, self, argtype[0])
            MultiLevelCliBase.ArgType.__init__(self, name, parent, argtype, description)

        def _parse(self, cli, arglist):
            assert isinstance(cli, CliResult)
            arglist = str(arglist).strip()
            #print ("-> '" + arglist + "'")
            if not arglist.startswith('[') or not arglist.endswith(']'):
                raise ArgumentTypeError("ListType: Parse error at token '%s' arg [arg %s] must conform to '[v1, v2,...]' format" % (
                    arglist, self.full_name(".", lastsep=True) + self.name))
            arglist = arglist[1:-1] # remove  [ ]

            args = MultiLevelCliBase.tokenize(arglist, sep=[','])
            array = []
            for arg in args:
                try:
                    if isinstance(self.argtype, MultiLevelCliBase.ArgType):
                        nested = CliResult()
                        self.argtype._parse(nested, arg)
                        val = nested.args()[self.argtype.name]
                    else:
                        val = (self.argtype)(MultiLevelCliBase.strip(arg))
                    array.append(val)
                except Exception as e:
                    if isinstance(e, ParseExecption):
                        raise
                    raise ArgumentTypeError("ListType: Parse error at token '%s' [arg %s], can't convert to type %s" % (
                        arg, self.full_name(".", lastsep=True) + self.name, self.argtype))
            # update the result cli structures only if I am not neseted arg
            cli[self.full_name(".", lastsep=True) + self.name] = array
            cli.add_command_arg(self, array)
            return 1  # consume only optname

        def type_name(self):
            if isinstance(self.argtype, MultiLevelCliBase.ArgType):
                return "[ %s ]" % self.argtype.type_name()
            if self.argtype is not None and type(self.argtype) == type:
                return " [ %s ]" % self.argtype.__name__
            return ""

    class StructType(ArgType):
        """
        An object representing a struct (dict) command argument.
        In most cases this shouldn't be used directly.
        """
        def __init__(self, name, parent, argtype, description=None):
            assert isinstance(argtype, dict)
            if not type(argtype) == dict:
                raise ArgumentTypeError("StructType: '%s' argtype '%s' must be { 'key1' : type1, 'key2' : type2, ...}'" % (name, argtype))
            # handle nested types
            for k in argtype:
                argtype[k] = MultiLevelCliBase.nested_type(name, self, argtype[k])
            MultiLevelCliBase.ArgType.__init__(self, name, parent, argtype, description)

        def _parse(self, cli, arglist):
            assert isinstance(cli, CliResult)
            arglist = str(arglist).strip()
            #print ("-> '" + arglist + "'")
            if not arglist.startswith('{') or not arglist.endswith('}'):
                raise ArgumentTypeError("ListType: Parse error at token '%s' arg [arg %s] must conform to '{k1=v1, k2=v2,...}' format" % (
                    arglist, self.parent.full_name(".", lastsep=True) + self.name))
            arglist = arglist[1:-1] # remove  { }

            args = MultiLevelCliBase.tokenize(arglist, sep=[','])
            struct = Namespace()
            for arg in args:
                try:
                    keyval = MultiLevelCliBase.tokenize(arg, sep=['='])
                    if len(keyval) != 2:
                        raise ArgumentTypeError(
                            "ListType: Parse error at token '%s' [arg %s], can not parse 'key = value' (%s)" % (
                                arg, self.parent.full_name(".", lastsep=True) + self.name, keyval))
                    k = MultiLevelCliBase.strip(keyval[0])
                    if not k in self.argtype:
                        raise ArgumentKeyError(
                            "ListType: Parse error at token '%s' [arg %s], unknown key '%s' " % (
                                arg, self.parent.full_name(".", lastsep=True) + self.name, k))
                    arg = MultiLevelCliBase.strip(keyval[1])
                    if isinstance(self.argtype[k], MultiLevelCliBase.ArgType):
                        nested = CliResult()
                        self.argtype[k]._parse(nested, arg)
                        val = nested.args()[self.argtype[k].name]
                    else:
                        val = (self.argtype[k])(str(arg).strip())
                    struct[k] = (val)
                except Exception as e:
                    if isinstance(e, ParseExecption):
                        raise
                    raise ArgumentTypeError("ListType: Parse error at token '%s' [arg %s], can't parse to type %s" % (
                        arg, self.parent.full_name(".", lastsep=True) + self.name, self.argtype))
            cli[self.full_name(".", lastsep=True) + self.name] = struct
            cli.add_command_arg(self, struct)
            return 1  # consume only optname

        def type_name(self):
            assert type(self.argtype) == dict
            s = ""
            for k in self.argtype:
                if isinstance(self.argtype[k], MultiLevelCliBase.ArgType):
                    s += " %s : %s," % (k, self.argtype[k].type_name())
                elif self.argtype is not None and type(self.argtype[k]) == type:
                    s += " %s : %s," % (k, self.argtype[k].__name__)
            if s:
                s = s[:-1]
            return '{' + s + " }"

    @staticmethod
    def strip(s):
        return s.strip("\"'").strip()

    class OptionType(object):
        """
        An object representing a single (command/group) option.
        In most cases this shouldn't be used directly.
        @see MultiLevelCliBase.ParseBase.add_option()
        """
        def __init__(self, short, long, parent, name=None, default=None, opttype=None, description=None):
            assert not short or isinstance(short, (str,unicode))
            assert not long or isinstance(long, (str,unicode))
            assert short or long
            #assert not opttype or isinstance(opttype, type)
            assert default is None or type(default) == opttype
            assert isinstance(name, (str,unicode))
            assert isinstance(parent, MultiLevelCliBase.ParseBase)
            self.parent = parent
            self.name = name
            self.short = short
            self.long = long
            self.argtype = MultiLevelCliBase.nested_type(self.name, self, opttype)
            self.description = description
            self.default = default

        def _parse(self, cli, path, tokens):
            var = path + self.name
            assert isinstance(cli, CliResult)
            if self.argtype != None:
                if isinstance(self.argtype, MultiLevelCliBase.ArgType):
                    nested = CliResult()
                    self.argtype._parse(nested, tokens[0])
                    val = nested.args()[self.argtype.name]
                else:
                    val = (self.argtype)(MultiLevelCliBase.strip(tokens[0]))
                #debug("name %s - arg %s" % (var, tokens[0]))
                cli[var] = val
                cli.set_command_options(self.parent.level, self.name, self, val)
                return 2 # consume 2 tokens - optname and arg
            val = not self.default
            cli[var] = val
            cli.set_command_options(self.parent.level, self.name, self, val)
            return 1 # consume only optname

        def full_name(self, sep, lastsep=True):
            return self.parent.full_name(sep, lastsep)


    class GroupType(ParseBase):
        def __init__(self, name, parent=None, description=None, defaultfn=None, helpfn=None):
            """
            Base CLI group class.
            :param name: the name of the group - used as parse token
            :param parent: the parent class of the group or None if root
            :param description:  description of the group
            :param defaultfn: function to call if no command is triggered. Fn must be fn(MultiLevelCliBase.GroupType).
            :param help: insert help options by default? If not set, the -h/--help are not added and the help flags are
                    not handled. The user can still define it and handle it manually.
            """
            assert isinstance(name, (str,unicode))
            self.commands = {}
            self.groups = {}
            self.defaultfn = defaultfn
            MultiLevelCliBase.ParseBase.__init__(self, name, parent, description, helpfn=helpfn)

        def __contains__(self, name):
            return name in self.groups or name in self.commands

        def __getitem__(self, item):
            if item in self.groups:
                return self.groups[item]
            else:
                return self.commands[item]

        def add_option(self, short, long = None, name=None, type=None, description=None, default=None):
            assert not short or not short in self.groups
            assert not long or not long in self.groups
            assert not short or not short in self.commands
            assert not long or not long in self.commands
            MultiLevelCliBase.ParseBase.add_option(self, short, long = long, name=name, type=type, description=description, default=default)
            assert not self.name in self.groups
            assert not self.name in self.commands

        def usage(self):
            """
            Generate a default usage text.
            :return: formatted text.
            """
            def option_str(o):
                assert isinstance(o, MultiLevelCliBase.OptionType)
                if o.long and o.short:
                    return "-%s/--%s" % (o.short, o.long)
                if o.long:
                    return "--" + o.long
                return "-" + o.short
            def type_str(o):
                if o.argtype is not None:
                    return " <%s>" % o.argtype.__name__
                return ""
            def desc_str(d):
                if d:
                    return "- %s" % d
                return ""
            def default_str(d):
                if not d:
                    return ""
                return ". Default '%s'" % str(d)

            width = MultiLevelCliBase.helpwidth
            s = "Usage: %s %s" % (MultiLevelCliBase.prog, self.full_name())
            for o in self.options.values():
                s += " [%s%s]" % (option_str(o), type_str(o))

            first = True
            for a in self.commands.values():
                if first:
                    s += " %s" % a.name
                    first = False
                else:
                    s += "|%s" % a.name
            out = textwrap.fill(s, width=width, subsequent_indent="\t\t")
            out += "\n"

            if self.description:
                out += "\nDescription:\n"
                out += textwrap.fill(self.description, width=width, initial_indent = "\t", subsequent_indent="\t")
                out += "\n"

            options1 = [ v for v in self.options.values() ]
            options2 = [ v for v in self.longoptions.values() ]
            options = set(options1 + options2)
            if options:
                out += "\nOptions:\n"

            for o in options:
                out += textwrap.fill("%-20s %-7s %s%s" % (option_str(o), type_str(o), desc_str(o.description), default_str(o.default)),
                                     width=width, initial_indent = "\t", subsequent_indent="\t\t\t\t\t")
                out += "\n"

            if self.commands:
                out += "\nSub Commands:\n"

            for a in self.commands.values():
                out += textwrap.fill("%-20s %s" % (a.name, desc_str(a.description)),
                                     width=width, initial_indent = "\t", subsequent_indent="\t\t\t\t\t")
                out += "\n"

            if self.groups:
                out += "\nSub Groups:\n"

            for a in self.groups.values():
                out += textwrap.fill("%-20s %s" % (a.name, desc_str(a.description)),
                                     width=width, initial_indent = "\t", subsequent_indent="\t\t")
                out += "\n"

            return out

        def add_command(self, name, description=None, help=_defhelpfn, ctx=None):
            """
            Add a new command to the current group.
            :param name: The name of the command for parsing and as the namespace target.
            :param description: used for help/usage screens.
            :return: The new argument object.
            """
            return self.__add_command(MultiLevelCliBase.CommandType(name, parent=self, description=description, helpfn=help, ctx=ctx))

        def __add_command(self, cmd):
            assert isinstance(cmd, MultiLevelCliBase.CommandType)
            assert cmd.name not in self.commands
            assert cmd.name not in self.groups
            self.commands[cmd.name] = cmd
            return cmd

        def add_group(self, name, description=None, defaultfn=usage_and_exit, help=_defhelpfn):
            """
            Add a new sub group to the current group.
            :param name: The name of the command for parsing and as the namespace target.
            :param description: used for help/usage screens.
            :param defaultfn: triggered if no command is found during the parsing (see __init__)
            :return: the new group object.
            """
            return self.__add_group(MultiLevelCliBase.GroupType(name, self, description=description, defaultfn=defaultfn, helpfn=help))

        def __add_group(self, group):
            assert isinstance(group, MultiLevelCliBase.GroupType)
            assert group.name not in self.groups
            assert group.name not in self.commands
            self.groups[group.name] = group
            return group

        def show_tree(self, tab=0):
            """
            Helper function: omit a formatted group/command tree.
            :param tab: tab level.
            :return:
            """
            self.show(tab)
            for cmd in self.commands:
                self.commands[cmd].show(tab+1)
            for group in self.groups:
                self.groups[group].show_tree(tab+1)

        def show(self, tab=0):
            """
            Omit a description line with the group name and description.
            :param tab: tab level.
            :return:
            """
            print ("\t" * tab + "[%s]    %s" % (self.name, "- %s" % self.description if self.description else ""))

        def _parse(self, cli, tokens):
            assert isinstance(cli, CliResult)
            assert isinstance(tokens, list)
            # posix parsing - all options are before commands in every level
            cli.set_group(self)
            self.set_defaults(cli)
            i = 0
            while i < len(tokens):
                t = tokens[i]
                assert isinstance(t, (str,unicode))
                if t.startswith("--"):
                    i += self.parse_option(cli, t[2:], tokens[i:], long=True)
                elif t.startswith("-"):
                    i += self.parse_option(cli, t[1:], tokens[i:], long=False)
                    # expect group name or command by that order
                elif t in self.groups:
                    i += self.groups[t]._parse(cli, tokens[i + 1:])
                    continue
                elif t in self.commands:
                    i += self.commands[t]._parse(cli, tokens[i + 1:])
                    continue
                else:
                    cli.set_unparsed_tokens(tokens[i:])
                    raise UnknownToken("Parse error at %s token '%s'" % (self.full_name("."), t))
            return 1 + i # one token for the group token

    class CommandType(ParseBase):
        """
        A (sub) command. Generated by group.add_command()
        """
        def __init__(self, name, parent, description=None, helpfn=None, ctx=None):
            assert isinstance(name, (str,unicode))
            assert isinstance(parent, MultiLevelCliBase.GroupType)
            MultiLevelCliBase.ParseBase.__init__(self, name, parent, description, helpfn=helpfn if help else defhelpfn)
            self.__arguments = []
            self.__ctx = ctx    # user defined ctx

        def _add_argument(self, name, argtype=str, description=None):
            if type(argtype) is list:
                return self.__add_argument(
                    MultiLevelCliBase.ListType(name, self, argtype=argtype, description=description))
            if type(argtype) is dict:
                return self.__add_argument(MultiLevelCliBase.StructType(name, self, argtype=argtype, description=description))
            if type(argtype) is type:
                return self.__add_argument(MultiLevelCliBase.ArgType(name, self, type=argtype, description=description))
            raise ParseExecption("%s: unknown type: %s" % (self.full_name(),argtype))

        def add_argument(self, name, type=str, description=None):
            """
            Add a new (mandatory) argument for the current command.
            :param name: to be used as the namespace target.
            :param type: python type that converted from string.
            :param description: used by help/usage screeds.
            :return: The new argument.
            """
            return self._add_argument(name, argtype=type, description=description)

        def __add_argument(self, arg):
            assert isinstance(arg, MultiLevelCliBase.ArgType)
            assert not arg.name in [x.name for x in self.__arguments]
            self.__arguments.append(arg)
            return arg

        def show(self, tab=0):
            """
            Omit a description line with the argument name, type and description.
            :param tab: tab level.
            :return:
            """
            print ("\t" * tab + "%s %s" % (self.name, "- %s" % self.description if self.description else ""))

        def _parse(self, cli, tokens):
            assert isinstance(cli, CliResult)
            assert isinstance(tokens, list)
            self.set_defaults(cli)
            cli.set_command(self, self.__ctx)
            # posix parsing - all options are before commands in every level
            argnum = 0
            i = 0
            while i < len(tokens):
                consumed = 0
                t = tokens[i]
                assert isinstance(t, (str,unicode))
                if t.startswith("--"):
                    consumed += self.parse_option(cli, t[2:], tokens[i:], long=True)
                elif t.startswith("-"):
                    consumed += self.parse_option(cli, t[1:], tokens[i:], long=False)
                    # expect group name or command by that order
                elif argnum < len(self.__arguments):
                    arg = self.__arguments[argnum]
                    assert isinstance(arg, MultiLevelCliBase.ArgType)
                    consumed += arg._parse(cli, t)
                    argnum += 1
                else:
                    cli.set_unparsed_tokens(tokens[i:])
                    raise UnknownToken("Parse error at %s token '%s'" % (self.full_name("."), t))
                i += consumed

            # check that all arguments are provided!
            if argnum < len(self.__arguments):
                raise CommandMissingArguments("Command %s requires more arguments than provided (provided arguments - %d)" % (self.full_name("."), argnum))
            return 1 + i  # one for the command token itself

        def fill_description(self, name : str, type_str : str, desc : str, default_str: str):
            if not desc or not isinstance(desc, str):
                return ""
            lines = desc.splitlines()
            if default_str == None:     # an arg
                out = textwrap.fill("%-20s %-10s %s" % (name, type_str, lines[0]),
                                     width=MultiLevelCliBase.helpwidth, initial_indent="\t", subsequent_indent="\t\t\t\t\t") + "\n"
            else:                       # an option
                out = textwrap.fill("%-20s %-7s %s%s" % (name, type_str, lines[0], default_str),
                                     width=MultiLevelCliBase.helpwidth, initial_indent = "\t", subsequent_indent="\t\t\t\t\t") + "\n"
            # deal with the extra lines
            for l in lines[1:]:
                out += textwrap.fill(l, width=MultiLevelCliBase.helpwidth, initial_indent="\t\t", subsequent_indent="\t\t\t\t\t") + "\n"
            return out

        def usage(self):
            """
            Generate a default usage screen for the current command.
            :return:
            """
            def option_str(o):
                assert isinstance(o, MultiLevelCliBase.OptionType)
                if o.long and o.short:
                    return "-%s/--%s" % (o.short, o.long)
                if o.long:
                    return "--" + o.long
                return "-" + o.short
            def type_str(o):
                if isinstance(o, MultiLevelCliBase.ArgType):
                    return o.type_name()
                if o.argtype is not None and type(o.argtype) == type:
                    return " <%s>" % o.argtype.__name__
                return ""
            def desc_str(d):
                if d:
                    return "- %s" % d
                return ""
            def default_str(d):
                if d is None or not d:
                    return ""
                return ". Default '%s'" % str(d)

            width = MultiLevelCliBase.helpwidth
            s = "Usage: %s %s" % (MultiLevelCliBase.prog, self.full_name())
            for o in self.options.values():
                s += " [%s%s]" % (option_str(o), type_str(o))
            for a in self.__arguments:
                s += " <%s>" % a.name
            out = textwrap.fill(s, width=width, subsequent_indent="\t\t")
            out += "\n"

            if self.description:
                out += "\nDescription:\n"
                out += textwrap.fill(self.description, width=width, initial_indent = "\t", subsequent_indent="\t")
                out += "\n"

            if self.__arguments:
                out += "\nArguments:\n"

            for a in self.__arguments:
                #out += textwrap.fill("%-20s %-10s %s" % (a.name, type_str(a), desc_str(a.description)),
                #                     width=width, initial_indent = "\t", subsequent_indent="\t\t\t\t\t")
                out += self.fill_description(a.name, type_str(a), a.description, None)
                out += "\n"

            values1 = [ v for v in self.options.values() ]
            values2 = [ v for v in self.longoptions.values() ]
            options = set(values1 + values2)
            if options:
                out += "\nOptions:\n"

            for o in options:
                #out += textwrap.fill("%-20s %-7s %s%s" % (option_str(o), type_str(o), desc_str(o.description), default_str(o.default)),
                #                     width=width, initial_indent = "\t", subsequent_indent="\t\t\t\t\t")
                out += self.fill_description(option_str(o), type_str(o), desc_str(o.description), default_str(o.default))
                out += "\n"

            return out


class MultiLevelArgParse(MultiLevelCliBase.GroupType):
    """
    A Multi level command line parsing class.
    """
    def __init__(self, description=None, prog=None, help=None, defaultfn=None):
        """
        Initialize the root group of the CLI.
        :param description: General CLI description.
        :param prog: the program name. If not set, the argv[0] is used.
        :param help: The help function.
        :param defaultfn:
        """
        global defhelpfn
        if help:
            defhelpfn = help
        else:
            help = defhelpfn
        if not defaultfn:
            defaultfn = usage_and_exit
        MultiLevelCliBase.GroupType.__init__(self, name=sys.argv[0], description=description, helpfn=help, defaultfn=defaultfn)
        if not prog:
            prog = sys.argv[0]
        MultiLevelCliBase.prog = prog
        self.description = description
        self._non_parsed = None

    def parse(self, cmdline=None, partial=False):
        '''
        Parse the given cmdline.
        :param cmdline: the command line to parse. Can be string, arrays of string tokens, or None where the sys.argv is used.
        :param partial: if True, unknown tokens will not cause exception, but rather can be retrieved using cli.unparsed_tokens().
        :return: CliResut (see @CliResult)
        '''
        cli = CliResult()
        if cmdline == None:
            cmdline = " ".join(sys.argv[1:])
        if isinstance(cmdline, (str,unicode)):
            tokens = MultiLevelCliBase.tokenize(cmdline)
        elif isinstance(cmdline, list):
            tokens = cmdline

        try:
            consumed = self._parse(cli, tokens)
        except UnknownToken:
            if partial:
                pass
            else:
                raise

        if not cli.command():
            grp = cli.group()
            if grp.defaultfn:
                grp.defaultfn(grp)

        return cli


    def show_systax(self):
        print( """
        CLI syntax:
            group1-name group2-name command-name arg1 arg2 arg3
            
            For example:
            
            > cli vm instance show myvmid

        Options:
            options can be defined in any level and there are belong to the last defined group or command.
            
            For example - cli level options:
            
            > cli -v network show
            
            First level group options:
            
            > cli network -v show
            
            Command options:
            
            > cli network show --long --all

        Type checking:
            arguments and options types are checked against definition. Automatic conversion can take place in many
            cases. For example "4" can be parse into int 4. Values can be quoted and double quoted:
            
            > cli network rename net8 "network for prod"

        Complex types:
            List(Arrays) and Struct(Dictionaries) are supported for both args and options.
            List are denoted with [ item1, item2, ...].
            Struct are denoted as { key1 = val1, key2 = val2, ...}. Keys must be one of the predefined keys, but
            not all keys must be set. Values types much match the defined types.
            
            For example:
            
            > cli network set net8 --config { name = "new net", tag = test, ip = 10.0.0.1 } my-project-id
            
            > cli network set net8 --aliases [ "10.0.0.2", "10.0.0.8" ]
            
        Nested types:
            Arrays and structures can be nested.
            
            For example:
            
            > cli vm instance new mynewvm --config { name = "centos vm", tag = prod, networks = [ prod, test], disks = [ { type = ssd, size=5G }, { type = hdd, size= 1TB } ] }
            
        """)

#########################################################
# Unit test area
#
def simple_debug(s):
    print (s)


tests = {}
checks = {}
docheck=False
ignore_errors=False
def test_cmd(cli, cmd, expect=None, desc="", partial=False):
    assert expect is None or issubclass(expect, Exception)
    n = None
    print ("\n### Starting test %s:\n### cmdline '%s'" % (desc, cmd))
    try:
        n = cli.parse(cmd, partial=partial)
    except Exception as e:
        if expect and type(e) == expect:
            print("%s:\n\tFailed on %s as expected (%s)" % (str(cmd), expect.__name__, str(e)))
            print ("-" * 60)
            return None
        else:
            raise

    if expect:
        raise Exception("test_cmd expected %s but cmd succeeded!" % expect.__name__)

    #print("class list")
    #for i in n:
    #    print (i, n[i])
    out = []
    out.append("'%s':" % (str(cmd)))
    out.append("'\t%s" % (str(n)))
    out.append("\tArgs: %s" % str(n.args()))
    out.append("\tOpts: %s" % str(n.opt()))
    for i in range(0, len(n.levels())):
        out.append("\tLevel %d: %s" % (i, str(n.ns(i))))
    tests[cmd] = out
    try:
        if docheck:
            if cmd not in checks:
                raise Exception("Unknown test - please add to checks file")
            if tests[cmd] != checks[cmd]:
                import difflib
                diff = difflib.ndiff(checks[cmd], tests[cmd])
                raise Exception("\n\nTest '%s' FAILED!!!(-expected, +results)\n%s" % (cmd, ''.join(diff)))
        for l in out:
            print (l)
        print("\n" + "-" * 60)
    except Exception as e:
        if not ignore_errors:
            raise
        print(str(e))
    return n


def test_tokenize(s, expect=None):
    assert expect is None or issubclass(expect, Exception)
    try:
        print("test_tokenize: '%s': %s" % (s, "(negative)" if expect else ""))
        print("\t=>: '%s'" % ( MultiLevelCliBase.tokenize(s)))
    except Exception as e:
        if expect and isinstance(e, expect):
            print ("\t=> expected errror: %s" % str(e))
            return True
        raise
    return expect is None


def read_checks(checks_file):
    global checks
    import json
    checks = json.loads(open(checks_file).read())

def write_checks(checks_file):
    import json
    open(checks_file, "w").write(json.dumps(tests, indent=4))

def test_main():
    import argparse
    global debugfn, docheck, ignore_errors
    debugfn = simple_debug

    # Use argparse for test parameters. No, we are not going to use multilevelcli parsing - it is the tested object!
    parser = argparse.ArgumentParser()
    parser.add_argument("checks_file", help="file with results to check against! (new checks file if write checks option is used)")
    parser.add_argument("-w", "--write_checks", action="store_true", help="create new check-file")
    parser.add_argument("-i", "--ignore_errors", action="store_true", help="ignore errors")
    ns = parser.parse_args()
    print (ns)
    docheck = not ns.write_checks
    if not ns.write_checks:
        read_checks(ns.checks_file)
    ignore_errors = ns.ignore_errors

    # Test basic namespace handling
    n = Namespace()
    n.a = "hh"
    n.l = 8
    n.b = True
    n["t"] = 9
    n["l"] = 7
    assert n.a == "hh"
    assert n.l == 7
    assert n.b == True
    assert n["t"] == 9
    print (n.kkk)  # check non existent key
    for i in n:
        print (i, n[i])

    test_tokenize("one two -flag -9 opt -a arg")
    test_tokenize("one two -flag -9 [a,b,c] opt -a arg")
    test_tokenize("")
    test_tokenize("arg1 arg2 [{ a b c { d } } ] two {{sfsf}", ParseExecption)
    test_tokenize("one \"two tow-cont \" three")
    test_tokenize("one \"two 'two-cont blah' \" three")
    test_tokenize('one \"two "two-cont \"blah " \'three t3\'')
    test_tokenize('one \"two "two-cont \\"blah " \'three t3\'', ParseExecption)
    test_tokenize("arg1 'arg2 arg3' [{ a b c { d } } ] ']' two \"{\"{sfsf}")

    # Test cli definitions
    cli = MultiLevelArgParse("demo cli", defaultfn=usage_and_raise_no_command, help=usage_and_raise_help)
    assert isinstance(cli, MultiLevelArgParse)
    cli.add_option("t", "treelevels", type=int, default=7, description="max tree levels to process")
    cli.add_option("q", "quiet", description="do not emit messages")
    cli.add_command("list")
    cli.add_command("help")

    class_group = cli.add_group("class", defaultfn=usage_and_raise_no_command)
    class_group.add_option("t", "trim", description="trim the results")

    cmd = class_group.add_command("new", description="create a new service class")
    cmd.add_argument("name", description="The name of the new class")
    cmd.add_argument("capacity_unit", description="Size of capacity unit in GB")
    cmd.add_option("x", "max_units", type=int, description="Maximal number of capacity units", default=10)
    cmd.add_option("m", "min_units", type=int, description="Minimal number of capacity units", default=3)
    new = cmd

    cmd = class_group.add_command("list")
    cmd.add_option("l", description="use long listing format")  # only short
    cmd.add_option(None, "long", description="show additional attiributes")
    cmd.add_option("c", type=int, description="columes number")  # only short
    cmd.add_option(None, "format", type=str, description="use specificed format", default="def")
    lst = cmd

    class_group.add_command("info")
    class_group.add_command("delete")

    instance_group = cli.add_group("instance")
    cmd = instance_group.add_command("new")
    cmd.add_argument("name", description="The name of the new class")
    cmd.add_argument("type", description="The type of the new class")
    cmd.add_argument("size", type=int, description="The name of the new class")
    cmd.add_option("r", "random", description="set random instance")
    cmd.add_option("l", "log", type=int, description="log level", default=5)
    cmd.add_option("k", "key", type=str, description="security key")
    instance = cmd

    instance_group.add_command("list")

    cmd = instance_group.add_command("info")
    cmd.add_argument("item", description="list of instances ids", type=[str])
    cmd.add_option(None, "ids", description="force resize", type=[int])
    cmd.add_option(None, "cred", description="force cred", type=dict(password=str, user=str, userid=int))
    cmd.add_option(None, "complex", description="nested arrays", type=[[int]])
    cmd.add_option(None, "complexs", description="nested arrays", type=[[str]])
    cmd.add_option(None, "complexst", description="nested struct arrays", type=[{'key1' : str, 'key2' : int}])
    cmd.add_option(None, "complexstar", description="nested struct arrays", type=[{'key1' : str, 'key2' : int, 'key3' : [int]}])

    cmd = instance_group.add_command("check")
    cmd.add_argument("complexstar", description="nested struct arrays arg", type=[{'key1' : str, 'key2' : int, 'key3' : [int]}])

    cmd = instance_group.add_command("set")
    cmd.add_argument("cred", description="cred", type=dict(password=str, user=str, userid=int))

    cmd = instance_group.add_command("resize")
    cmd.add_option(None, "force", description="force resize")

    alpha_group = cli.add_group("alpha", help=usage_help_and_raise_nocommand)
    cmd = alpha_group.add_command("list", help=usage_help_and_raise_nocommand)
    cmd.add_option("l", description="use long listing format")  # only short
    cmd.add_option(None, "long", description="show additional attiributes")
    cmd.add_option("c", type=int, description="columns number")  # only short
    cmd.add_option(None, "format", type=str, description="use specified format", default="def")

    beta_group = cli.add_group("beta", help=None)
    beta_group.add_command("test", ctx="context")

    # Test help/usage generation
    cli.show_tree()
    print("")
    print (lst.usage())
    print("")
    print (new.usage())
    print("")
    print (instance.usage())
    print("")
    print (instance_group.usage())
    print("")
    print (cli.usage())
    print("")

    test_cmd(cli, "", NoCommand, "negative: usage (default handling) for empty cmdline")
    test_cmd(cli, "-q", NoCommand, desc="usage (default handling) for first level no command")
    test_cmd(cli, "-q --help", HelpRquired, desc="first level help generation")
    test_cmd(cli, "list", desc="first level command no args")
    test_cmd(cli, "-t 5 list", desc="first level opt with param and command")
    test_cmd(cli, "class list", desc="second level command no args")
    test_cmd(cli, "class list -l", desc="second level command opt parsing")
    test_cmd(cli, "class list -l -h", HelpRquired, desc="second level command opt")
    test_cmd(cli, "class -h list -l", HelpRquired, desc="second level option with second level command and option")
    test_cmd(cli, "class", NoCommand, "negative: usage (default handling) for no (second level) command")
    test_cmd(cli, "class new newclass", CommandMissingArguments, desc="negative: missing arguments for second level command")
    test_cmd(cli, "class new newclass 8", desc="second level command with 2 arguments")
    test_cmd(cli, "class new newclass --help", HelpRquired, desc="second level command help generation")
    test_cmd(cli, "class new newclass -x 9 10", desc="second level command with options and arguments")
    test_cmd(cli, "-q class new newclass -x 9 88", desc="root level option with second level option and argument")
    test_cmd(cli, "-q class -t new newclass -x 9 --max_units 13 --min_units 7 100",
             desc="root level option, first level option, second level command long and short options and arguments")

    test_cmd(cli, "alpha -h ", NoCommand, desc="group help override")
    test_cmd(cli, "alpha list -h ", NoCommand, desc="command help override")

    test_cmd(cli, "beta -h ", OptionNotFound, desc="group help disable")
    n = test_cmd(cli, "beta test", desc="check command ctx")
    if n.command_ctx() != "context":
        raise Exception("bad command context")

    test_cmd(cli, "instance new newclass -x 9 --max_units 13 --min_units 7", OptionNotFound, desc="negative: bad second level option")
    test_cmd(cli, "instance resize -h", HelpRquired, desc="generate help with option that is long only")
    test_cmd(cli, "instance resize --force", desc="second level command with option that is long only")
    test_cmd(cli, "instance new kuku def aa", ArgumentTypeError, desc="negative: bad second level command arguement type")
    test_cmd(cli, "instance new kuku def 7", desc="second level command arguments with int type")
    test_cmd(cli, "instance new kuku def 7 -h", HelpRquired, desc="help generation for second level command with arguments")
    test_cmd(cli, "instance -h new kuku def 7 -h", HelpRquired, desc="help generation for first level while second level help is requested too")
    test_cmd(cli, "--help instance -h new kuku def 7 -h", HelpRquired, desc="help generation for root level with first and second level help is requested too")
    test_cmd(cli, "instance new kuku def 7 8", UnknownToken, desc="negative: unknown token at end of second level command")
    n = test_cmd(cli, "instance new kuku def 7 8", partial=True, desc="partial second level parsing")
    print ("Unparsed tokens: %s" % (n.unparsed_tokens()))
    test_cmd(cli, "-q xxx new kuku def 7 8", NoCommand, partial=True, desc="negative: usage (default handling) for partial parsing and unknown command")

    # Test list/dict args
    test_cmd(cli, "instance info 1,2,3,4", ArgumentTypeError, desc="Negative bad list int arg")
    test_cmd(cli, "instance info [1,2,3,4]", desc="list int arg")
    test_cmd(cli, "instance info []", desc="list str arg")
    test_cmd(cli, "instance info [6, 9]", desc="list str arg")
    test_cmd(cli, "instance info [6, 9,    -1]", desc="list str arg")
    test_cmd(cli, "instance info [6, 4, \"999 jjj\", \"kuku\"]", desc="list str arg")
    test_cmd(cli, "instance info [6, 9] --ids [4, 5]", desc="list str arg and list int option")
    test_cmd(cli, "instance info [6, 9] --complex [4, 5]", ArgumentTypeError, desc="negative: define nested array but use non nested array")
    test_cmd(cli, "instance info [6, 9] --complex [[4, 5], [6,4,8], [4,5]]", desc="nested int arrays")
    test_cmd(cli, "instance info [6, 9] --complexs [[4, 5], [6,4,8, bobob], [4,5]]", desc="nested str arrays")
    test_cmd(cli, "instance info [6, 9] --complexst [ {key1 = bobo, key2 = 6 }, { key2 = 8} ]", desc="nested str arrays")
    test_cmd(cli, "instance info [6, 9] --complexstar [ {key1 = bobo, key2 = 6 }, { key2 = 8, key3 = [ 5, 67, 0] } ]", desc="nested str arrays")
    test_cmd(cli, "instance info [7] --cred { password = 'this is me', user = me, userid = 8}", desc="list str arg and struct option")
    test_cmd(cli, "instance info [7] --cred { password = 'this ,is me', user = \" me=me\", userid = 8}", desc="list str arg and struct option with problematic chars")
    test_cmd(cli, "instance info [7] --cred { password = 'this', user = me, userid = 8, stam=kuku}", ArgumentKeyError, desc="negative: unknown key")
    test_cmd(cli, "instance set { password = 'this is me', user = me, userid = 8}", desc="struct arg")

    test_cmd(cli, "instance check [ {key1 = bobo, key2 = 6 }, { key2 = 8, key3 = [ 5, 67, 0] } ]", desc="nested str arrays arg")

    if ns.write_checks:
        write_checks(ns.checks_file)
        print ("New checks validate file '%s' is written." % ns.checks_file)
    else:
        print ("### Validated vs. checks file '%s'" % ns.checks_file)

    #cli.show_systax()


if __name__ == "__main__":
    try:
        test_main()
    except Exception as e:
        #print(str(e))
        traceback.print_exc()
        sys.exit(1)
    print ("### Success!")
