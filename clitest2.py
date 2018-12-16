#!/usr/bin/env python3

import multilevelcli
import traceback
import sys

if __name__ == "__main__":
    try:
        cli = multilevelcli.MultiLevelArgParse("testcli2")
        assert isinstance(cli, multilevelcli.MultiLevelArgParse)
        cli.add_option("t", "treelevels", type=int, default=7, description="max tree levels to process")
        cli.add_option(None, "quiet", description="do not emit messages")
        cli.add_option("f", None, description="do not emit messages", type=int, default=0)
        cli.add_option("d", None, name="debug", type=int, description="debug level", default=1)
        vms = cli.add_group("vms")
        networks = cli.add_group("networks")
        list_net_cmd = networks.add_command("list", description="list networks")

        cli.add_command("tree", description="show command tree")
        cli.add_command("syntax", description="show command line syntax")

        instances = vms.add_group("instances", description="commands on vm instances")
        list_cmd = instances.add_command("list", description="list instances")
        list_cmd.add_option("l", "long", description="use long listing")

        user_group = cli.add_group("user", description="user record commands")
        user_cmd = user_group.add_command("new", description="add user using parameters")
        user_cmd.add_argument('name', type=str)  # str is the default
        user_cmd.add_argument('age', type=int, description="in years")
        user_cmd.add_argument('weight', type=float, description="in KG")
        user_cmd.add_option('m', 'married')     # default boolean/flag option
        user_cmd.add_option(None, 'spouse', type=str)    # string value for option


        child_cmd = user_group.add_command("children", description="add children using array parameters and options")
        child_cmd.add_argument("number", type=int, description="number of children")
        child_cmd.add_argument("ages", type=[int], description="age list of children")   # array of int example
        child_cmd.add_option("names", type=[str], description="name list of children")   # array of str example

        person_cmd = user_group.add_command("person", description="add a person using a struct parameter")
        person_cmd.add_argument('record', type={"name": str, "age" : int}, description="a person record")  # struct example

        family_cmd = user_group.add_command("family", description="add a famility using a compound parameter")
        p = family_cmd.add_argument('members', type=[{"name": str, "age" : int,
                                                        "children" : [ { "name" : str, "age" : int}]}],
                                    description="member records")  # array of struct example
        ########
        ns = cli.parse()
        args = ns.args()

        command = ns.command_name()

        if command == "tree":
            cli.show_tree()
        elif command == "syntax":
            cli.show_systax()
        elif command in ["user.new", "user.person", "user.children"]:
            if not ns.quiet:
                print("%s is added. \n\t%s\n" % (command, args))
        elif command == 'user.family':
            if not ns.quiet:
                for m in ns.user.family.members:
                    print("Adding family member %s age %d" % (m['name'], m['age']))
                    if not m.children:
                        continue
                    for c in m.children:
                        print("\tChildren %s age %d" % (c['name'], c['age']))
        # other commands...

    except Exception as e:
        traceback.print_exc()
        print("Error: " + str(e))
        sys.exit(1)

    print ("\n### Success! namespace='%s'" % str(ns))
    print ("ns: %s" % ns.ns())
    print ("group: %s" % ns.group())
    print ("command: '%s'" % ns.command())
    print ("args: %s" % ns.args())
    print ("opt: %s" % ns.opt())
    for n in ns.levels():
        print ("NS %s" % (str(n)))
