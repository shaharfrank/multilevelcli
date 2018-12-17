#!/usr/bin/env python3
from pyswagger import App, Security, spec
from pyswagger.contrib.client.requests import Client
from urllib.parse import urlparse, urlunparse, urlsplit, urlunsplit

import json
import sys
import traceback
import logging
import multilevelcli
import re

log = None
classes = {}
instances = {}
namespaces = {}

def debug(msg, json_data = None):
    log.debug("%s: %s" % (msg, json.dumps(json_data, sort_keys=True, indent=4, default=str)))


def info(msg, json_data = None):
    if json_data:
        log.info("%s: %s" % (msg, json.dumps(json_data, sort_keys=True, indent=4, default=str)))
    else:
        log.info(msg)


def panic(msg, code = 1, trace=False):
    log.error("PANIC: %s" % msg)
    if trace:
        traceback.print_exc()
    sys.exit(code)


class ResultError(Exception):
    def __init__(self, op, status, raw):
        Exception.__init__(self)
        self.op = op
        self.status = status
        self.raw = raw

    def __str__(self):
        try:
            err = json.loads(self.raw)
            return "%s: Failed with status %s: %s" % (self.op, self.status, err["error"]["message"])
        except Exception as e:
            log.error("Error (non json) %s" % str(e))
        return "op %s: failed on status %d: '%s'" % (self.op, self.status, self.raw)


class RESTClient(object):
    def resolve(self, p):
        if not self.url:
            return p
        #<scheme>://<netloc>/<path>?<query>#<fragment>
        o = urlparse(p)
        if self.initial_load:
            new = urlunsplit(("file", '', self.schema, '', ''))
            self.initial_load = False
        else:
            new = urlunsplit((self.url.scheme, self.url.netloc, o.path, o.query, o.fragment))
        debug("------%s  : %s -> %s" % (str(o), self.url, new))
        return new

    def __init__(self, schema, security=None, url=None):
        log.info("### RESTClient using %s, server url='%s' security %s" % (schema, url, str(security)))
        # create a App with a local resource file

        if not schema:
            panic("No schema URL: please provide a URL or a local path")
        # load Swagger resource file into App object
        self.initial_load = False
        self.schema = schema
        if url:
            self.url = urlparse(url)
            if schema:
                self.initial_load = True
            self.app = App.load(url, url_load_hook=self.resolve if url else None)
        else:
            # Server url is not specified. In this case the server is taken from the schema.
            self.app = App.load(schema, url_load_hook=self.resolve if url else None)

        self.app.prepare(True)
        #self.serverapp = App(url_load_hook=self.resolve)
        #self.serverapp.prepare() = App(url_load_hook=self.resolve)

        # init Security for authorization
        auth = Security(self.app)
        #auth = Security(self.serverapp)
        if security:
            assert "auth_type" in security
            assert "params" in security
            auth.update_with(security["auth_type"], security["params"])
            #auth.update_with('simple_basic_auth', ('user', 'password'))  # basic auth
            #auth.update_with('api_key', '')  # api key
            #auth.update_with('simple_oauth2', '12334546556521123fsfss')  # oauth2

        # init the client
        self.client = Client(auth)

    def do_req(self, op, cmd, args, opts, expected=None):
        def arg_in(op, name):
            for p in op.parameters:
                if p.schema:
                    object_name = p.schema.ref_obj.name
                    o = self.app.resolve('#/definitions/%s' % object_name)
                    for pr in o.properties:
                        if pr == name:
                            return p.__getattribute__("in")   # the entire struct is in
                if p.name == name:
                    return p.__getattribute__("in")
            return False

        if expected is None:
            expected = [200, 201, 204]
        debug("post_req: %s %s %s" % (op, args, opts))
        resp = None
        out = None
        params = {}
        payload = {}

        for p in args:
            if args[p] == None:
                continue
            is_in = arg_in(op, p)
            if is_in in ["path","query"]:
                params[p] = args[p]
            elif is_in == "body":
                payload[p] = args[p]
            else:
                pass # ignore

        for p in opts:
            if opts[p] == None:
                continue
            is_in = arg_in(op, p)
            if is_in in ["path","query"]:
                params[p] = opts[p]
            elif is_in == "body":
                payload[p] = opts[p]
            else:
                pass # ignore

        if payload:
            params["payload"] = payload
            #print ("payload=='%s'" % payload)
        try:
            # try to making a request
            req, resp = op(**params)

            # prefer json as response
            req.produce('application/json')
            #print ("----> %s", req)
            reply = self.client.request((req, resp))
            out = reply.data
        except Exception as e:
            #info("post_req: op %s failed: %s" % (cmd.full_name("."), str(e)))
            raise
        if resp.status not in expected:
            raise ResultError(cmd.full_name("."), resp.status, resp.raw)
        if out is None:
            if 'application/json' in reply.header['Content-Type']:
                out = json.loads(reply.raw)
        debug(op, out)
        return out

    def get_object(self, object_name):
        '''
        Initialize an object from a OpenAPI model (schema).
        :param object_name: an object from a OpenAPI model (under #/definitions).
        :return:  a dictionary with all properties, set to the default or None.
        '''
        o = self.app.resolve('#/definitions/%s' % object_name).dump()
        assert o["type"] == "object"

        obj = {}

        for p in o["properties"]:
            d = o["properties"][p]
            if d.get("default", None):
                obj[p] = d["default"]
            elif p in o.get("required", []):
                obj[p] = None   # to be filled later!

        debug("get_object: '%s':" % (object_name), obj)
        return obj

    def models(self):
        for o in self.app.m:
            print(o)

    def ops(self):
        return self.app.op[:]
        for o in self.app.op:
            print(o)
            for p in self.app.op[o].parameters:
                print ("> %s %s : %s" % ( p.name, p.required, p.__getattribute__("$ref")))
        ##op = self.app.resolve('#/definitions/%s' % o).dump()
        #print op

def exec_command(rest, cli_result):
    debug("CLI result: %s" % str(cli_result))
    assert isinstance(rest, RESTClient)
    assert isinstance(cli_result, multilevelcli.CliResult)
    op = cli_result.command_ctx()
    assert isinstance(op, spec.v2_0.objects.Operation)
    debug("CLI exec: cmd %s args %s opt %s" % (cli_result.command(), cli_result.args(), cli_result.opt()))
    out = rest.do_req(op, cli_result.command(), cli_result.args(), cli_result.opt())

    #print (json.loads(str(out)).dump(indent=4))
    print (json.dumps(out, sort_keys=True, indent=4, default=str))


def noop(ent):
    assert isinstance(ent, multilevelcli.MultiLevelCliBase.ParseBase)
    #print (ent.usage())
    #sys.exit(1)


class CliParser(object):
    maxlevels = 5

    class CmdParam(object):
        def __init__(self, cmd, name, t, desc, default, required):
            self.cmd = cmd
            self.name = name
            self.type = t
            self.desc = desc
            self.default = default
            self.required = required

    def resolve_desc_hint(self, desc):
        return None, None
        a = desc.split("|")

        # "group|command" or "group|group|...|group|command" is expected
        if not a:
            return None, None
        if len(a) < 2:
            return None, a[-1]

        groups = a[:-2]
        command = self.sanitize(a[-1])
        return groups, command

    def resolve_command_from_url(self, url, method):
        log.info("Resolve '%s' %s" % (url, method))
        a = url.split("/")
        if not a:
            return None, None

        groups = []
        param_index = -1
        i = 0
        for part in a:
            token = str(part)
            assert isinstance(token, str)
            name = re.sub("{.*}", "", token).strip()
            if name:
                groups.append(token)
            if name != token:
                param_index = i
            i += 1

        item = False    # no item is selected
        if param_index == len(a) - 1:
            item = True # last url item assumes to be an item selector

        command = None
        if method == "post":
            command = "update" if item else "new"
        elif method == "delete":
            command = "delete"
        elif method == "get":
            command = "info" if item else "list"
        elif method == "put":
            command = "update" if item else "new"

        return groups, command

    def sanitize(self, name):
        name = str(name)
        name = name.replace(".", "_")
        return name

    def process_groups(self, groups):
        """
        Validate that all groups are defined (define them if not) and return the last group
        :param groups:
        :return:
        """
        parent = self.cli
        if not groups:
            return parent

        for l in range(0, len(groups)):
            name = self.sanitize(groups[l])
            if l > self.maxlevels:
                log.error("skip command due to too many groups'", groups)
                return None
            if name in parent:
                parent = parent[name]
            else:
                # add new group
                log.info("Adding new group '%s' level %d" % (name, l))
                parent = parent.add_group(name)
        return parent

    def get_object(self, object_name):
        '''
        Initialize an object from a OpenAPI model (schema).
        :param object_name: an object from a OpenAPI model (under #/definitions).
        :return:  a dictionary with all properties, set to the default or None.
        '''
        o = self.app.resolve('#/definitions/%s' % object_name).dump()
        assert o["type"] == "object"

        obj = {}

        for p in o["properties"]:
            d = o["properties"][p]
            if d.get("default", None):
                obj[p] = d["default"]
            elif p in o.get("required", []):
                obj[p] = None   # to be filled later!

        debug("get_object: '%s':" % (object_name), obj)
        return obj

    def add_arg(self, c):
        assert isinstance(c, self.CmdParam)
        return self.add_arg(c.cmd, c.name, c.type, c.desc)

    def add_arg(self, cmd, name, atype, desc):
        log.info("Adding argument for command '%s':'%s' type %s" % (cmd.full_name("."), name, atype))
        cmd.add_argument(name, type=atype, description=desc)

    def add_opt(self, c):
        assert isinstance(c, self.CmdParam)
        return self.add_opt(c.cmd, c.name, c.type, c.desc, c.default)

    def add_opt(self, cmd, name, otype, desc, default):
        log.info("Adding option for command '%s':'%s' type %s" % (cmd.full_name("."), name, otype))
        cmd.add_option(None, name, type=otype, description=desc, default=(otype)(default) if default else None)

    def resolve_struct(self, cmd, ref) -> (dict, str):
        out = {}
        dict_desc = ""
        o = self.app.resolve(ref).dump()
        for p in o["properties"]:
            d = o["properties"][p]
            desc = d.get("description")
            ref = d.get("$ref")
            t = self.resolve_type(d.get("type"), ref)
            format = d.get("format")
            default =  d.get("default", None)
            required = p in o.get("required", [])
            dict_desc += "\n* %s (%s) \t%s %s %s " % (p, t.__name__, desc, "Default is %s" % default if default else "", "[required]" if required else "")
            ndesc = ""
            if t == object:
                t, ndesc = self.resolve_struct(cmd, ref)
            elif t == list:
                t, ndesc = self.resolve_array(cmd, p, d)
            out[p] = t
            dict_desc += ndesc
        return out, dict_desc

    def add_ref(self, cmd, ref, plist, prefix=""):
        o = self.app.resolve(ref).dump()
        for p in o["properties"]:
            d = o["properties"][p]
            desc = d.get("description", "")
            ref = d.get("$ref")
            t = self.resolve_type(d.get("type"), ref)
            format = d.get("format")
            default =  d.get("default", None)
            required = p in o.get("required", [])
            ndesc = ""
            if t == object:
                t, ndesc = self.resolve_struct(cmd, ref)
            elif t == list:
                t, ndesc = self.resolve_array(cmd, p, d)
            name = p if not prefix else prefix + "_" + p
            plist.append(self.CmdParam(cmd, name, t, desc + ndesc, default, required))

        #print cmd.usage()

    def add_struct(self, cmd, schema, plist):
        if not schema.ref_obj or not schema.ref_obj.properties:
            return
        #props = schema.ref_obj.properties
        object_name = schema.ref_obj.name
        ref = '#/definitions/%s' % object_name
        self.add_ref(cmd, ref, plist)

    def resolve_array(self, cmd, name, array) -> (list, str):
        '''
        Arrays are encoded as follows:
        # simple typed:
        "regions": {
                    "type": "array",
                    "description": "blah, blah",
                    "default": [],
                    "items": {
                        "type": "string"
                    }
                },
        # nested:
        "accessors": {
                    "type": "array",
                    "description": "bla bla",
                    "items": {
                        "$ref": "#/definitions/accessors"
                    }
                },

        :return: array type def (compound) and description of array content
        '''
        if not 'items' in array:
            log.info("Skipping array var for command '%s':'%s' - not items" % (cmd.full_name("."), name))
            return  [], "" # can't handle that - hope that it is not that important....
        p = array['items']
        desc = array.get("description", "")
        if not isinstance(p, dict):
            log.info("Skipping array var for command '%s':'%s' = items not a dict" % (cmd.full_name("."), name))
            return  [], "" # can't handle that - hope that it is not that important....

        ref = p.get("$ref", None)
        t = None
        ndesc = ""
        if "type" in p:
            t = self.resolve_type(p["type"])
        elif ref:
            t, ndesc = self.resolve_struct(cmd, ref)
        elif t == list:
            t, ndesc = self.resolve_array(cmd, name, p)
        return [ t ], desc + ndesc

    def resolve_type(self, otype, ref=None):
        if ref:
            return object
        if otype is None:
            return str
        if otype == "string":
            return str
        if otype == "number":
            return float
        if otype == "integer":
            return int
        if otype == "array":
            return list
        return str

    def add_plist(self, plist):
        plist.sort(key=lambda x: x.name)
        for p in plist:
            assert isinstance(p, self.CmdParam)
            if p.required:
                self.add_arg(p.cmd, p.name, p.type, p.desc)
            else:
                self.add_opt(p.cmd, p.name, p.type, p.desc, p.default)

    def process_command(self, op, parent, command, summary):
        assert isinstance(op, spec.v2_0.objects.Operation)
        assert isinstance(parent, multilevelcli.MultiLevelCliBase.GroupType)
        assert isinstance(command, str)
        log.info("Adding new command '%s':'%s' opid %s" % (str(parent), str(command), op.operationId))
        cmd = parent.add_command(command, description=str(summary), ctx=op)
        self.commands[op.operationId] = cmd

        # first handle path params
        plist = []
        for p in op.parameters:
            assert isinstance(p, spec.v2_0.objects.Parameter)
            if str(p.__getattribute__("in")) != "path":
                continue
            t = self.resolve_type(p.type)
            plist.append(self.CmdParam(cmd, p.name, t, p.description, p.default, p.required))

        self.add_plist(plist)
        plist = []

        for p in op.parameters:
            assert isinstance(p, spec.v2_0.objects.Parameter)
            #print("adding path param %s" % p.name)
            if str(p.__getattribute__("in")) == "path":
                continue
            t = self.resolve_type(p.type)
            desc = p.description if p.description else ""
            ndesc = ""
            if p.schema:
                self.add_struct(cmd, p.schema, plist)
            elif t == list:
                t, ndesc = self.resolve_array(cmd, p.name, p)
            else:
                plist.append(self.CmdParam(cmd, p.name, t, desc + ndesc, p.default, p.required))

        self.add_plist(plist)

    def resolve_cmd(self, op):
        assert isinstance(op, spec.v2_0.objects.Operation)
        groups, command = self.resolve_desc_hint(op.description)
        if not command:
            groups, command = self.resolve_command_from_url(op.path, op.method)

        if not groups and not command:
            log.error("skip op command %s %s can't resolve groups/command", op.path, op.operationId)
            return

        parent = self.process_groups(groups)
        if not parent:
            return

        self.process_command(op, parent, command, op.summary)

    def parse(self, cmdline):
        return self.cli.parse(cmdline)

    def __init__(self, rest_srv, args, unparsed=None, show_tree=False):
        # new parser for rest of cmdline (unparsed)
        self.commands = {}
        self.rest = rest_srv
        self.app = rest_srv.app

        self.cli = multilevelcli.MultiLevelArgParse(description='FaaS REST schema', defaultfn=noop if show_tree else None)

        # prepare the commands and sub commands
        for o in rest.app.op:
            self.resolve_cmd(rest.app.op[o])

        if show_tree:
            self.cli.show_tree()
            sys.exit(3)


def init_cmdline_parser():
    cli = multilevelcli.MultiLevelArgParse(description='Swagger REST CLI', defaultfn=noop)
    cli.add_option("S", "server", type=str, description="override server url with the provided one")
    cli.add_option('s', 'schema', type=str, default="schema.json", description='URI to the service OpenAPI schema, e.g. http://localhost:8888/api/schema.json')
    cli.add_option('L', 'logfile', type=str, default="swagger_cli.log", description='set the log file')
    cli.add_option("l", 'loglevel', type=str, default="INFO",
                   description='set log level to [DEBUG, INFO, WARNING, ERROR, CRITICAL]')
    cli.add_option("u", 'urllib_loglevel', type=str, default="ERROR",
                   description='set log level of urllib to [DEBUG, INFO, WARNING, ERROR, CRITICAL]')
    cli.add_option("g", 'swagger_loglevel', type=str, default="ERROR",
                   description='set swagger log level to [DEBUG, INFO, WARNING, ERROR, CRITICAL]')
    cli.add_option('c', 'console', description="dump logs also to console")
    cli.add_option('T', 'tree', description="show command tree and exit")
    cli.add_option('K', 'key', type=str, default="", description="use api_key auth with the provided key")
    return cli


def setup_logging(loglevel, swaggerdebug, urllog, logfile, copy_console):
    global _logfile
    _logfile = logfile
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    swaggerdebug_level = getattr(logging, swaggerdebug.upper(), None)
    if not isinstance(swaggerdebug_level, int):
        raise ValueError('Invalid log level: %s' % swaggerdebug)

    logger = logging.getLogger('pyswagger')
    logger.setLevel(swaggerdebug_level)

    logging.basicConfig(filename=logfile, level=numeric_level, format='%(asctime)s - %(name)s %(levelname)s:%(message)s')

    log = logging.getLogger()
    log.setLevel(numeric_level)

    urllog_level = getattr(logging, urllog.upper(), None)
    if not isinstance(urllog_level, int):
        raise ValueError('Invalid log level: %s' % urllog_level)
    if urllog_level == logging.DEBUG:
        # These two lines enable debugging at httplib level (requests->urllib3->http.client)
        # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
        # The only thing missing will be the response.body which is not logged.
        try:
            import http.client as http_client
        except ImportError:
            # Python 2
            import httplib as http_client
        http_client.HTTPConnection.debuglevel = 1
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(urllog_level)
    requests_log.propagate = True

    if copy_console:
        console = logging.StreamHandler()
        console.setLevel(numeric_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console.setFormatter(formatter)
        log.addHandler(console)

    return log


if __name__ == "__main__":
    cli = init_cmdline_parser()

    result = cli.parse(partial=True)
    args = result.ns(0)

    log = setup_logging(args.loglevel, args.swagger_loglevel, args.urllib_loglevel, args.logfile, args.console)
    unparsed = result.unparsed_tokens()
    info("UN: %s %s args %s" % (result, args, unparsed))

    show_tree = args.tree

    # if show tree is requsted we want to continue and get the schema to show
    if not unparsed and not show_tree:
        print (cli.usage())
        sys.exit(1)

    security = None if not args.key else dict(auth_type="api_key", params=args.key)
    rest = RESTClient(args.schema, security=security, url=args.server)

    try:
        parser = CliParser(rest, args, result.unparsed_tokens(), args.tree)
        cli_out = parser.parse(result.unparsed_tokens())
    except multilevelcli.ParseExecption as e:
        print (str(e))
        sys.exit(2)

    try:
        exec_command(rest, cli_out)
    except ResultError as e:
        print (str(e))
        sys.exit(1)



